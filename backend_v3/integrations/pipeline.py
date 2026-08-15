"""
The ingestion pipeline every source flows through:

    SOURCE -> INGESTION -> NORMALIZATION -> IDENTITY MATCHING
           -> CUSTOMER MODEL -> NEO4J -> QDRANT

Connectors own SOURCE/INGESTION/NORMALIZATION (they return the dataclasses
in models.py). This module owns everything downstream, so identity
matching and provenance are applied identically no matter which system
the data came from.

Writes reuse the node shapes synthetic_data.py already seeds, which is
why imported customers appear in Customer 360, My Day, and briefings with
no changes to the Stage 1 retrieval code.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.integrations.models import (
    NormalizedContact,
    NormalizedCustomer,
    NormalizedInteraction,
    NormalizedMeeting,
    NormalizedPolicy,
    Provenance,
)
from backend_v3.integrations.timeutil import local_date


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _customer_id_for(external_id: str, source_system: str) -> str:
    """Imported customers get a namespaced ID so they never collide with
    seeded cust_XXXXX identifiers."""
    safe = "".join(ch if ch.isalnum() else "_" for ch in external_id).strip("_").lower()
    return f"{source_system}_{safe}"


def upsert_customer(customer: NormalizedCustomer) -> dict[str, Any]:
    """CUSTOMER MODEL -> NEO4J. Resolves identity first so a re-import
    updates the existing customer instead of duplicating them."""
    from backend_v3.graph_store.neo4j_client import run_write
    from backend_v3.integrations.identity import register_identity, resolve_identity

    provenance = customer.provenance or Provenance(
        source_system="unknown", source_id=customer.external_id, original_reference=customer.external_id
    )

    match = resolve_identity(
        external_id=customer.external_id,
        email=customer.email,
        phone=customer.phone,
        name=customer.full_name,
        source_system=provenance.source_system,
    )

    if match.resolved and match.customer_id:
        customer_id = match.customer_id
        created = False
    else:
        customer_id = _customer_id_for(customer.external_id, provenance.source_system)
        created = True

    provenance.customer_id = customer_id
    props = provenance.as_properties()

    run_write(
        "MERGE (c:Customer {customer_id: $customer_id}) "
        "SET c.name = $name, "
        "    c.life_stage = coalesce($life_stage, c.life_stage), "
        "    c.advisor_name = coalesce($advisor_name, c.advisor_name), "
        "    c.email = coalesce($email, c.email), "
        "    c.phone = coalesce($phone, c.phone), "
        "    c.source_system = $source_system, c.source_id = $source_id, "
        "    c.original_reference = $original_reference, c.imported_at = $imported_at",
        {
            "customer_id": customer_id,
            "name": customer.full_name,
            "life_stage": customer.life_stage,
            "advisor_name": customer.advisor_name,
            "email": customer.email,
            "phone": customer.phone,
            **props,
        },
    )

    # Every identifier we just learned becomes deterministic for next time.
    register_identity(customer_id, "external_id", customer.external_id, provenance.source_system)
    if customer.email:
        register_identity(customer_id, "email", customer.email, provenance.source_system)
    if customer.phone:
        register_identity(customer_id, "phone", customer.phone, provenance.source_system)

    return {"customer_id": customer_id, "created": created, "matched_on": match.matched_on}


def _resolve_external(external_id: str, source_system: str) -> str | None:
    from backend_v3.integrations.identity import resolve_identity

    match = resolve_identity(external_id=external_id, source_system=source_system)
    if match.resolved:
        return match.customer_id
    # Fall back to the deterministic ID this pipeline would have minted.
    from backend_v3.graph_store.neo4j_client import run_query

    candidate = _customer_id_for(external_id, source_system)
    rows = run_query(
        "MATCH (c:Customer {customer_id: $customer_id}) RETURN c.customer_id AS customer_id",
        {"customer_id": candidate},
    )
    return rows[0]["customer_id"] if rows else None


def upsert_contact(contact: NormalizedContact) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_write

    provenance = contact.provenance or Provenance("unknown", contact.full_name, contact.full_name)
    customer_id = _resolve_external(contact.customer_external_id, provenance.source_system)
    if not customer_id:
        return {"written": False, "reason": "customer_not_found"}

    # Must match synthetic_data.py's seed pattern exactly (:FamilyMember
    # label, :HAS_FAMILY_MEMBER relationship, relationship type stored on
    # the node) — retrieval.get_customer_graph() reads that exact shape,
    # so drifting from it here would make imported family silently
    # invisible in Customer 360 despite a successful-looking import.
    run_write(
        "MATCH (c:Customer {customer_id: $customer_id}) "
        "MERGE (f:FamilyMember {name: $name, customer_id: $customer_id}) "
        "SET f.relationship = $relationship, f.email = coalesce($email, f.email), "
        "    f.phone = coalesce($phone, f.phone) "
        "MERGE (c)-[r:HAS_FAMILY_MEMBER]->(f) "
        "SET r.source = $source, r.confidence = 1.0, "
        "    r.created_at = $now, r.source_system = $source_system, r.source_id = $source_id, "
        "    r.original_reference = $original_reference, r.imported_at = $imported_at",
        {
            "customer_id": customer_id,
            "name": contact.full_name,
            "email": contact.email,
            "phone": contact.phone,
            "relationship": contact.relationship,
            "now": _now(),
            **provenance.as_properties(),
        },
    )
    return {"written": True, "customer_id": customer_id}


def upsert_policy(policy: NormalizedPolicy) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_write

    provenance = policy.provenance or Provenance("unknown", policy.policy_id, policy.policy_id)
    customer_id = _resolve_external(policy.customer_external_id, provenance.source_system)
    if not customer_id:
        return {"written": False, "reason": "customer_not_found"}

    # Must match synthetic_data.py's :OWNS relationship — retrieval.py's
    # get_portfolio() only discovers a policy_id by traversing OWNS, so a
    # different relationship type here would make an imported policy
    # invisible in Customer 360 despite writing real data.
    run_write(
        "MATCH (c:Customer {customer_id: $customer_id}) "
        "MERGE (p:Policy {policy_id: $policy_id}) "
        "SET p.product_name = $product_name, p.line_of_business = $line_of_business, "
        "    p.annual_premium = $annual_premium, p.policy_status = $policy_status, "
        "    p.customer_id = $customer_id "
        "MERGE (c)-[r:OWNS]->(p) "
        "SET r.source = $source, r.confidence = 1.0, r.created_at = $now, "
        "    r.source_system = $source_system, r.source_id = $source_id, "
        "    r.original_reference = $original_reference, r.imported_at = $imported_at",
        {
            "customer_id": customer_id,
            "policy_id": policy.policy_id,
            "product_name": policy.product_name,
            "line_of_business": policy.line_of_business,
            "annual_premium": policy.annual_premium,
            "policy_status": policy.policy_status,
            "now": _now(),
            **provenance.as_properties(),
        },
    )
    return {"written": True, "customer_id": customer_id}


def upsert_interaction(interaction: NormalizedInteraction, embed: bool = True) -> dict[str, Any]:
    """NEO4J for the record, QDRANT for the semantic representation."""
    from backend_v3.graph_store.neo4j_client import run_write

    provenance = interaction.provenance or Provenance(
        "unknown", interaction.occurred_at, interaction.summary[:80]
    )
    customer_id = _resolve_external(interaction.customer_external_id, provenance.source_system)
    if not customer_id:
        return {"written": False, "reason": "customer_not_found"}

    conversation_id = f"{provenance.source_system}_{provenance.source_id}"
    body = interaction.body or interaction.summary
    excerpt = body[:500] + ("…" if len(body) > 500 else "")

    run_write(
        "MATCH (c:Customer {customer_id: $customer_id}) "
        "MERGE (conv:Conversation {conversation_id: $conversation_id}) "
        "SET conv.date = $date, conv.summary = $summary, conv.transcript_excerpt = $excerpt, "
        "    conv.interaction_type = $interaction_type, "
        "    conv.source_system = $source_system, conv.source_id = $source_id, "
        "    conv.original_reference = $original_reference, conv.imported_at = $imported_at "
        "MERGE (c)-[r:HAD_CONVERSATION]->(conv) "
        "SET r.source = $source, r.confidence = 1.0, r.created_at = $now",
        {
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "date": str(interaction.occurred_at)[:10],
            "summary": interaction.summary,
            "excerpt": excerpt,
            "interaction_type": interaction.interaction_type,
            "now": _now(),
            **provenance.as_properties(),
        },
    )

    chunks = 0
    if embed and interaction.body:
        try:
            from backend_v3.advisor.semantic_memory_service import store_transcript_chunks

            chunks = store_transcript_chunks(customer_id, conversation_id, interaction.body)
        except Exception:
            # Qdrant being unavailable must not lose the graph record that
            # already committed above.
            chunks = 0

    return {"written": True, "customer_id": customer_id, "chunks_stored": chunks}


def upsert_meeting(meeting: NormalizedMeeting) -> dict[str, Any]:
    """Store a calendar meeting and attempt attendee->customer matching.

    An unmatched meeting is still stored. It surfaces in My Day flagged
    "Customer match required." rather than being dropped or guessed at.
    """
    from backend_v3.graph_store.neo4j_client import run_write
    from backend_v3.integrations.identity import resolve_identity

    provenance = meeting.provenance or Provenance("calendar", meeting.external_id, meeting.title)

    matched_customer_id: str | None = None
    matched_on = "none"
    candidates: list[dict[str, Any]] = []
    organizer_normalized = (meeting.organizer or "").strip().lower()

    for attendee in meeting.attendees:
        # Attendees may arrive as "Name <email>" (calendar_sources keeps
        # the CN so a customer with no email on file can still produce a
        # name candidate) — extract the address for the organizer check
        # and the direct-email lookup rather than comparing the raw string.
        attendee_email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", attendee)
        attendee_email = attendee_email_match.group(0).lower() if attendee_email_match else attendee.strip().lower()

        # The advisor is on their own meetings; they are not the customer.
        if organizer_normalized and attendee_email == organizer_normalized:
            continue
        match = resolve_identity(
            calendar_attendee=attendee,
            email=attendee_email if attendee_email_match else None,
            source_system=provenance.source_system,
        )
        if match.resolved and match.customer_id:
            matched_customer_id = match.customer_id
            matched_on = f"attendee:{match.matched_on}"
            break
        candidates.extend(c.__dict__ for c in match.candidates)

    if not matched_customer_id:
        # Some calendars carry the customer only in the title.
        match = resolve_identity(name=meeting.title, source_system=provenance.source_system)
        candidates.extend(c.__dict__ for c in match.candidates)

    provenance.customer_id = matched_customer_id
    # The :CalendarEvent label separates ingested calendar entries from the
    # seeded :Meeting history nodes, which carry no meeting_id and would
    # otherwise be swept up by any plain MATCH (m:Meeting).
    run_write(
        "MERGE (m:Meeting {meeting_id: $meeting_id}) "
        "SET m:CalendarEvent, "
        "    m.title = $title, m.starts_at = $starts_at, m.ends_at = $ends_at, "
        "    m.meeting_date = $meeting_date, m.meeting_link = $meeting_link, "
        "    m.location = $location, m.status = $status, m.organizer = $organizer, "
        "    m.attendees = $attendees, m.customer_id = $customer_id, "
        "    m.match_status = $match_status, m.matched_on = $matched_on, "
        "    m.source_system = $source_system, m.source_id = $source_id, "
        "    m.original_reference = $original_reference, m.imported_at = $imported_at",
        {
            "meeting_id": f"{provenance.source_system}_{meeting.external_id}",
            "title": meeting.title,
            "starts_at": meeting.starts_at,
            "ends_at": meeting.ends_at,
            # The advisor's local date, so an early-morning meeting is not
            # filed under the previous UTC day.
            "meeting_date": local_date(meeting.starts_at),
            "meeting_link": meeting.meeting_link,
            "location": meeting.location,
            "status": meeting.status,
            "organizer": meeting.organizer,
            "attendees": meeting.attendees,
            "customer_id": matched_customer_id,
            "match_status": "matched" if matched_customer_id else "match_required",
            "matched_on": matched_on,
            **provenance.as_properties(),
        },
    )

    if matched_customer_id:
        run_write(
            "MATCH (c:Customer {customer_id: $customer_id}), (m:Meeting {meeting_id: $meeting_id}) "
            "MERGE (c)-[r:HAS_MEETING]->(m) "
            "SET r.source = $source, r.confidence = 1.0, r.created_at = $now",
            {
                "customer_id": matched_customer_id,
                "meeting_id": f"{provenance.source_system}_{meeting.external_id}",
                "source": f"{provenance.source_system}_{provenance.source_id}",
                "now": _now(),
            },
        )

    return {
        "meeting_id": f"{provenance.source_system}_{meeting.external_id}",
        "customer_id": matched_customer_id,
        "match_status": "matched" if matched_customer_id else "match_required",
        "matched_on": matched_on,
        "candidates": candidates[:5],
    }


def ingest(
    *,
    source_system: str,
    customers: list[NormalizedCustomer] | None = None,
    contacts: list[NormalizedContact] | None = None,
    policies: list[NormalizedPolicy] | None = None,
    interactions: list[NormalizedInteraction] | None = None,
    meetings: list[NormalizedMeeting] | None = None,
) -> dict[str, Any]:
    """Run a full pipeline pass and record the sync against the provider.

    Customers are written before dependent objects so contacts, policies,
    and interactions in the same batch can resolve to them.
    """
    from backend_v3.integrations.connection_store import record_sync

    counts = {"customers": 0, "contacts": 0, "policies": 0, "interactions": 0, "meetings": 0}
    errors: list[str] = []
    meeting_results: list[dict[str, Any]] = []

    for customer in customers or []:
        try:
            upsert_customer(customer)
            counts["customers"] += 1
        except Exception as exc:
            errors.append(f"customer {customer.external_id}: {exc}")

    for contact in contacts or []:
        try:
            if upsert_contact(contact).get("written"):
                counts["contacts"] += 1
            else:
                errors.append(f"contact {contact.full_name}: customer {contact.customer_external_id} not found")
        except Exception as exc:
            errors.append(f"contact {contact.full_name}: {exc}")

    for policy in policies or []:
        try:
            if upsert_policy(policy).get("written"):
                counts["policies"] += 1
            else:
                errors.append(f"policy {policy.policy_id}: customer {policy.customer_external_id} not found")
        except Exception as exc:
            errors.append(f"policy {policy.policy_id}: {exc}")

    for interaction in interactions or []:
        try:
            if upsert_interaction(interaction).get("written"):
                counts["interactions"] += 1
            else:
                errors.append(f"interaction: customer {interaction.customer_external_id} not found")
        except Exception as exc:
            errors.append(f"interaction: {exc}")

    for meeting in meetings or []:
        try:
            result = upsert_meeting(meeting)
            meeting_results.append(result)
            counts["meetings"] += 1
        except Exception as exc:
            errors.append(f"meeting {meeting.external_id}: {exc}")

    written = {k: v for k, v in counts.items() if v}
    if written:
        record_sync(source_system, written)

    return {
        "source_system": source_system,
        "counts": counts,
        "errors": errors,
        "meetings": meeting_results,
        "unmatched_meetings": [m for m in meeting_results if m["match_status"] == "match_required"],
    }

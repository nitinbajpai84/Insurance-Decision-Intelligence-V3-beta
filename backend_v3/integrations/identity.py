"""
Customer identity resolution.

The same person arrives as a CRM ID, an email address, a phone number, a
calendar attendee, or a WhatsApp contact. This module is what decides
they are one customer.

Design rules:

1. Deterministic first. An exact match on a normalized identifier is the
   only thing that resolves automatically at full confidence, because it
   is the only thing that is actually certain.
2. Name matching proposes, it does not decide. A name-only hit comes back
   as a *candidate* with confidence < 1.0 so the caller can require
   review ("Customer match required.") rather than silently binding a
   meeting to the wrong person.
3. Gemini assists, and only on the ambiguous middle: it ranks existing
   candidates. It cannot invent a customer, and its answer is still a
   proposal — `resolved` stays False unless a deterministic key matched
   or the advisor confirms.

Identifiers live as (:CustomerIdentity {kind, value_normalized}) nodes
linked to (:Customer), so a confirmed match becomes deterministic for
every future import.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

IDENTITY_KINDS = ("crm_id", "email", "phone", "calendar_attendee", "whatsapp", "external_id")

# A name-only match is never treated as certain.
NAME_MATCH_CONFIDENCE = 0.6
EXACT_MATCH_CONFIDENCE = 1.0


@dataclass
class MatchCandidate:
    customer_id: str
    name: str
    confidence: float
    matched_on: str


@dataclass
class MatchResult:
    """`resolved` means safe to bind without asking. Everything else is a
    proposal the UI must surface as "Customer match required."."""

    resolved: bool
    customer_id: str | None = None
    confidence: float = 0.0
    matched_on: str = "none"
    candidates: list[MatchCandidate] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolved": self.resolved,
            "customer_id": self.customer_id,
            "confidence": self.confidence,
            "matched_on": self.matched_on,
            "reason": self.reason,
            "candidates": [
                {"customer_id": c.customer_id, "name": c.name, "confidence": c.confidence, "matched_on": c.matched_on}
                for c in self.candidates
            ],
        }


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def normalize_phone(value: str) -> str:
    """Keep digits only, and drop a country-code prefix's leading zeros so
    '+65 9123 4567' and '6591234567' converge."""
    digits = re.sub(r"\D", "", value or "")
    return digits.lstrip("0")


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def normalize_value(kind: str, value: str) -> str:
    if kind == "email":
        return normalize_email(value)
    if kind in ("phone", "whatsapp"):
        return normalize_phone(value)
    if kind == "calendar_attendee":
        # Calendar attendees are email addresses in practice; mailto: is common.
        return normalize_email(re.sub(r"^mailto:", "", (value or "").strip(), flags=re.I))
    return (value or "").strip().lower()


def _extract_email(value: str) -> str | None:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", value or "")
    return normalize_email(match.group(0)) if match else None


def register_identity(customer_id: str, kind: str, value: str, source_system: str, confidence: float = EXACT_MATCH_CONFIDENCE) -> None:
    """Bind an identifier to a customer so future imports resolve
    deterministically. Idempotent."""
    if kind not in IDENTITY_KINDS:
        raise ValueError(f"Unknown identity kind '{kind}'")
    normalized = normalize_value(kind, value)
    if not normalized:
        return

    from datetime import datetime, timezone

    from backend_v3.graph_store.neo4j_client import run_write

    run_write(
        "MATCH (c:Customer {customer_id: $customer_id}) "
        "MERGE (i:CustomerIdentity {kind: $kind, value_normalized: $normalized}) "
        "SET i.value_raw = $raw, i.customer_id = $customer_id "
        "MERGE (c)-[r:HAS_IDENTITY]->(i) "
        "SET r.source = $source_system, r.confidence = $confidence, r.created_at = $now",
        {
            "customer_id": customer_id,
            "kind": kind,
            "normalized": normalized,
            "raw": value,
            "source_system": source_system,
            "confidence": confidence,
            "now": datetime.now(timezone.utc).isoformat(),
        },
    )


def _lookup_identity(kind: str, value: str) -> dict[str, Any] | None:
    normalized = normalize_value(kind, value)
    if not normalized:
        return None
    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        "MATCH (c:Customer)-[:HAS_IDENTITY]->(i:CustomerIdentity {kind: $kind, value_normalized: $normalized}) "
        "RETURN c.customer_id AS customer_id, c.name AS name LIMIT 1",
        {"kind": kind, "normalized": normalized},
    )
    return rows[0] if rows else None


def _lookup_customer_property(field_name: str, value: str) -> dict[str, Any] | None:
    """Customers seeded before Stage 2 may carry email/phone directly on
    the node rather than as a CustomerIdentity."""
    if not value:
        return None
    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        f"MATCH (c:Customer) WHERE c.{field_name} IS NOT NULL AND toLower(toString(c.{field_name})) = $value "
        "RETURN c.customer_id AS customer_id, c.name AS name LIMIT 1",
        {"value": value},
    )
    return rows[0] if rows else None


def _lookup_by_name(name: str) -> list[dict[str, Any]]:
    normalized = normalize_name(name)
    if not normalized:
        return []
    from backend_v3.graph_store.neo4j_client import run_query

    return run_query(
        "MATCH (c:Customer) WHERE toLower(trim(c.name)) = $name "
        "RETURN c.customer_id AS customer_id, c.name AS name LIMIT 5",
        {"name": normalized},
    )


def resolve_identity(
    *,
    external_id: str | None = None,
    crm_id: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    name: str | None = None,
    calendar_attendee: str | None = None,
    whatsapp: str | None = None,
    source_system: str = "unknown",
    use_ai_assist: bool = False,
) -> MatchResult:
    """Resolve one identity across every signal available for it.

    Deterministic keys are tried in descending order of how uniquely they
    identify a person. Only those produce `resolved=True`.
    """
    deterministic: list[tuple[str, str | None]] = [
        ("crm_id", crm_id),
        ("external_id", external_id),
        ("email", email),
        ("calendar_attendee", calendar_attendee),
        ("whatsapp", whatsapp),
        ("phone", phone),
    ]

    for kind, value in deterministic:
        if not value:
            continue
        hit = _lookup_identity(kind, value)
        if hit:
            return MatchResult(
                resolved=True,
                customer_id=hit["customer_id"],
                confidence=EXACT_MATCH_CONFIDENCE,
                matched_on=kind,
                reason=f"Exact match on {kind}",
            )

    # A calendar attendee is an email address; try it as one, and fall
    # back to any email embedded in a "Name <addr>" style string.
    email_like = normalize_email(email or "") or normalize_value("calendar_attendee", calendar_attendee or "")
    if not email_like:
        email_like = _extract_email(calendar_attendee or "") or ""
    if email_like:
        hit = _lookup_identity("email", email_like) or _lookup_customer_property("email", email_like)
        if hit:
            return MatchResult(
                resolved=True,
                customer_id=hit["customer_id"],
                confidence=EXACT_MATCH_CONFIDENCE,
                matched_on="email",
                reason="Exact match on email address",
            )

    phone_like = normalize_phone(phone or "") or normalize_phone(whatsapp or "")
    if phone_like:
        hit = _lookup_customer_property("phone", phone_like)
        if hit:
            return MatchResult(
                resolved=True,
                customer_id=hit["customer_id"],
                confidence=EXACT_MATCH_CONFIDENCE,
                matched_on="phone",
                reason="Exact match on phone number",
            )

    # Nothing deterministic matched. Names only ever produce candidates.
    display_name = name or ""
    if not display_name and calendar_attendee and "<" in calendar_attendee:
        display_name = calendar_attendee.split("<", 1)[0].strip()

    candidates = [
        MatchCandidate(
            customer_id=row["customer_id"],
            name=row["name"],
            confidence=NAME_MATCH_CONFIDENCE,
            matched_on="name",
        )
        for row in _lookup_by_name(display_name)
    ]

    if len(candidates) == 1:
        return MatchResult(
            resolved=False,
            customer_id=None,
            confidence=NAME_MATCH_CONFIDENCE,
            matched_on="name",
            candidates=candidates,
            reason="Name matched a single customer, but no unique identifier confirmed it. Customer match required.",
        )

    if len(candidates) > 1:
        if use_ai_assist:
            ranked = _ai_rank_candidates(display_name, email_like, candidates)
            if ranked:
                candidates = ranked
        return MatchResult(
            resolved=False,
            confidence=0.0,
            matched_on="ambiguous",
            candidates=candidates,
            reason="Several customers share this name. Customer match required.",
        )

    return MatchResult(
        resolved=False,
        confidence=0.0,
        matched_on="none",
        reason="No existing customer matched. Customer match required.",
    )


def _ai_rank_candidates(name: str, email: str, candidates: list[MatchCandidate]) -> list[MatchCandidate]:
    """Gemini reorders existing candidates when a name is ambiguous.

    It is given a closed list and may only rank it — it cannot introduce a
    customer_id, and its output never sets resolved=True. If it fails for
    any reason the original ordering stands.
    """
    try:
        from backend_v3.advisor.ai_service import generate_json

        result = generate_json(
            contents=(
                f"Incoming contact: name={name!r}, email={email!r}.\n"
                "Existing customers:\n"
                + "\n".join(f"- {c.customer_id}: {c.name}" for c in candidates)
                + "\nRank the existing customers by how likely each is the incoming contact."
            ),
            system_instruction=(
                "You assist with customer identity matching. Rank ONLY the customer_ids given to you. "
                "Never invent a customer_id. Express genuine uncertainty in the score — if the evidence "
                "is just a shared name, the score must stay below 0.7."
            ),
            response_schema={
                "type": "object",
                "properties": {
                    "ranking": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "customer_id": {"type": "string"},
                                "score": {"type": "number"},
                            },
                            "required": ["customer_id", "score"],
                        },
                    }
                },
                "required": ["ranking"],
            },
        )
    except Exception:
        return candidates

    known = {c.customer_id: c for c in candidates}
    ranked: list[MatchCandidate] = []
    for item in result.get("ranking", []):
        candidate = known.get(item.get("customer_id"))
        if candidate is None:
            continue  # Gemini named something outside the closed list — drop it.
        ranked.append(
            MatchCandidate(
                customer_id=candidate.customer_id,
                name=candidate.name,
                # Cap AI influence: it may reorder, never certify.
                confidence=min(float(item.get("score", 0.0)), NAME_MATCH_CONFIDENCE),
                matched_on="name+ai_assist",
            )
        )
    for candidate in candidates:
        if all(r.customer_id != candidate.customer_id for r in ranked):
            ranked.append(candidate)
    return ranked


def list_identities(customer_id: str) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    return run_query(
        "MATCH (c:Customer {customer_id: $customer_id})-[r:HAS_IDENTITY]->(i:CustomerIdentity) "
        "RETURN i.kind AS kind, i.value_raw AS value, r.source AS source, r.confidence AS confidence "
        "ORDER BY i.kind",
        {"customer_id": customer_id},
    )

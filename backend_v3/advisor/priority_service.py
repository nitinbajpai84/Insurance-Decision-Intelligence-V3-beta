"""
Transparent customer priority scoring — Stage 4.

The spec is explicit: "Do NOT create an unexplained black-box score.
Always show WHY a customer is prioritized." Every signal this module
weighs is one already visible elsewhere in the product (a life event, a
concern, a follow-up, a stale-contact flag) — nothing here is a learned
weight or an opaque AI judgment. The output is always a reason list an
advisor can check against the customer's own record.

Seven signals, matching the spec's list exactly:

  1. upcoming life events        — recent EXPERIENCED events (recency proxy;
                                    there is no forward-looking calendar of
                                    life events, so "recent" stands in for
                                    "upcoming" the same way prioritization.py
                                    already treats it)
  2. unresolved needs             — HAS_NEED facts with no policy in the same
                                    line_of_business covering them
  3. recent customer concerns     — CONCERNED_ABOUT facts
  4. stale customer information   — no contact within STALE_CONTACT_DAYS
  5. pending follow-ups           — open :FollowUp nodes
  6. recent interaction           — days since last meeting (inverse signal:
                                    very recent contact softens urgency)
  7. customer engagement          — conversation count as a proxy for how
                                    much the relationship is actively
                                    generating signal to act on

No signal here is itself an AI judgment — Gemini is not consulted for
scoring. See ai_service.py's briefing/extraction paths for where Gemini
is actually used (synthesis over already-approved facts, or proposing
memories that still require approval).

Two entry points, same scoring logic, different data-fetch cost:

  score_customer()      one customer's authoritative view, via
                         assemble_customer_context() (Neo4j + Qdrant +
                         DuckDB) — what Customer 360 shows.
  score_all_customers()  every customer via a handful of bulk Cypher
                         queries instead of N calls to score_customer(),
                         which would mean N Qdrant searches for a page
                         that only needs a fleet-wide ranking, not each
                         customer's semantically-ranked conversations.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.advisor.prioritization import RECENT_EVENT_DAYS, STALE_CONTACT_DAYS

# Point weights are additive and each tied to a stated reason — the total
# is a transparent sum, not a fitted/opaque model.
_WEIGHTS = {
    "recent_life_event": 30,
    "unresolved_need": 15,
    "concern": 12,
    "stale": 25,
    "pending_followup": 15,
    "no_recent_interaction": 10,
    "low_engagement": 8,
}


def _needs_without_matching_policy(needs: list[dict], covered_categories: set[str]) -> list[dict]:
    """A need counts as unresolved if no owned policy shares its category.
    Simple and explainable on purpose — the same category-match approach
    conflict detection already uses in memory_model.py."""
    return [n for n in needs if (n.get("category") or "").lower() not in covered_categories]


def _build_score(
    *,
    customer_id: str,
    name: str,
    base: dict[str, Any],
    unresolved_needs: list[dict],
    concerns: list[dict],
    open_followups: list[dict],
    conversation_count: int,
) -> dict[str, Any]:
    """The one place the reason list and score are assembled, so
    score_customer() and score_all_customers() can never silently
    disagree about how a score is built."""
    reasons: list[dict[str, Any]] = []
    score = 0

    if base["most_recent_life_event"] and base["most_recent_life_event_days_ago"] is not None \
            and base["most_recent_life_event_days_ago"] <= RECENT_EVENT_DAYS:
        score += _WEIGHTS["recent_life_event"]
        reasons.append({
            "signal": "recent_life_event",
            "label": f"{base['most_recent_life_event']} ({base['most_recent_life_event_days_ago']}d ago)",
            "weight": _WEIGHTS["recent_life_event"],
        })

    for need in unresolved_needs[:3]:
        score += _WEIGHTS["unresolved_need"]
        reasons.append({
            "signal": "unresolved_need",
            "label": f"Unresolved need: {need['description']}",
            "weight": _WEIGHTS["unresolved_need"],
        })

    for concern in concerns[:3]:
        score += _WEIGHTS["concern"]
        reasons.append({
            "signal": "concern",
            "label": f"Concern raised: {concern['topic']}",
            "weight": _WEIGHTS["concern"],
        })

    if base["is_stale"]:
        score += _WEIGHTS["stale"]
        reasons.append({
            "signal": "stale",
            "label": f"No contact in {base['days_since_contact']} days — information may be stale",
            "weight": _WEIGHTS["stale"],
        })

    for followup in open_followups[:3]:
        score += _WEIGHTS["pending_followup"]
        reasons.append({
            "signal": "pending_followup",
            "label": f"Follow-up pending: {followup['title']}",
            "weight": _WEIGHTS["pending_followup"],
        })

    days_since_contact = base["days_since_contact"]
    if days_since_contact is not None and RECENT_EVENT_DAYS < days_since_contact < STALE_CONTACT_DAYS:
        # Between "recently seen" and "stale" — not urgent on its own, but
        # tips borderline cases without double-counting the stale signal.
        score += _WEIGHTS["no_recent_interaction"]
        reasons.append({
            "signal": "no_recent_interaction",
            "label": f"No meeting in {days_since_contact} days",
            "weight": _WEIGHTS["no_recent_interaction"],
        })

    if conversation_count == 0:
        score += _WEIGHTS["low_engagement"]
        reasons.append({
            "signal": "low_engagement",
            "label": "No captured conversations on record",
            "weight": _WEIGHTS["low_engagement"],
        })

    if score >= 50:
        priority = "high"
    elif score >= 20:
        priority = "medium"
    else:
        priority = "low"

    if not reasons:
        reasons.append({"signal": "none", "label": "No urgent signals — routine priority", "weight": 0})

    return {
        "customer_id": customer_id,
        "name": name,
        "priority": priority,
        "score": score,
        "reasons": reasons,
        "unresolved_needs_count": len(unresolved_needs),
        "open_concerns_count": len(concerns),
        "pending_followups_count": len(open_followups),
        "days_since_contact": days_since_contact,
        "is_stale": base["is_stale"],
        "conversation_count": conversation_count,
    }


def score_customer(customer_id: str) -> dict[str, Any]:
    """Full transparent priority breakdown for one customer, using the
    authoritative context (including Qdrant-ranked conversations) —
    what Customer 360 shows."""
    from backend_v3.advisor.followups import list_followups
    from backend_v3.advisor.prioritization import compute_priority
    from backend_v3.advisor.retrieval import assemble_customer_context

    ctx = assemble_customer_context(customer_id)
    if ctx is None:
        return None

    base = compute_priority(ctx["life_events"], ctx["concerns"], ctx["meetings"])
    covered = {(p.get("line_of_business") or "").lower() for p in ctx["portfolio"]}
    unresolved_needs = _needs_without_matching_policy(ctx["needs"], covered)
    open_followups = list_followups(customer_id=customer_id, status="open")
    conversation_count = len(ctx.get("relevant_conversations") or [])

    return _build_score(
        customer_id=customer_id,
        name=ctx["name"],
        base=base,
        unresolved_needs=unresolved_needs,
        concerns=ctx["concerns"],
        open_followups=open_followups,
        conversation_count=conversation_count,
    )


def score_all_customers() -> list[dict[str, Any]]:
    """Every customer's score via a handful of bulk queries instead of N
    calls to score_customer() — which would mean N sequential Qdrant
    searches to rank a fleet-wide list that only needs presence/absence
    signals, not each customer's semantically-ranked conversations."""
    from backend_v3.advisor.followups import list_followups
    from backend_v3.advisor.prioritization import compute_priority
    from backend_v3.advisor.retrieval import list_customers as list_customers_raw
    from backend_v3.advisor.semantic_memory_service import count_conversation_chunks_by_customer
    from backend_v3.graph_store.neo4j_client import run_query

    raw = list_customers_raw()  # one query: life_events/concerns/meetings per customer

    signal_rows = run_query(
        "MATCH (c:Customer) "
        "OPTIONAL MATCH (c)-[:HAS_NEED]->(n:Need) "
        "OPTIONAL MATCH (c)-[:OWNS]->(p:Policy) "
        "RETURN c.customer_id AS customer_id, "
        "collect(DISTINCT CASE WHEN n IS NOT NULL THEN {description: n.description, category: n.category} END) AS needs, "
        "collect(DISTINCT CASE WHEN p.line_of_business IS NOT NULL THEN toLower(p.line_of_business) END) AS covered_lobs",
        {},
    )
    signals_by_id = {row["customer_id"]: row for row in signal_rows}
    # Qdrant, not Neo4j: seeded demo customers have conversation memory
    # stored directly by synthetic_data.py with no matching Neo4j
    # :Conversation node, so counting HAD_CONVERSATION here would
    # wrongly flag them as low-engagement.
    conversation_counts = count_conversation_chunks_by_customer()

    open_followups_by_customer: dict[str, list[dict]] = {}
    for followup in list_followups(status="open"):
        open_followups_by_customer.setdefault(followup["customer_id"], []).append(followup)

    results = []
    for row in raw:
        customer_id = row["customer_id"]
        life_events = [e for e in row["life_events"] if e.get("description")]
        concerns = [c for c in row["concerns"] if c.get("topic")]
        meetings = [m for m in row["meetings"] if m.get("date")]
        base = compute_priority(life_events, concerns, meetings)

        signals = signals_by_id.get(customer_id, {})
        needs = [n for n in (signals.get("needs") or []) if n and n.get("description")]
        covered = {c for c in (signals.get("covered_lobs") or []) if c}
        unresolved_needs = _needs_without_matching_policy(needs, covered)

        results.append(
            _build_score(
                customer_id=customer_id,
                name=row["name"],
                base=base,
                unresolved_needs=unresolved_needs,
                concerns=concerns,
                open_followups=open_followups_by_customer.get(customer_id, []),
                conversation_count=conversation_counts.get(customer_id, 0),
            )
        )

    results.sort(key=lambda c: c["score"], reverse=True)
    return results

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
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.advisor.prioritization import RECENT_EVENT_DAYS, STALE_CONTACT_DAYS, TODAY

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


def _needs_without_matching_policy(needs: list[dict], portfolio: list[dict]) -> list[dict]:
    """A need counts as unresolved if no owned policy shares its category.
    Simple and explainable on purpose — the same category-match approach
    conflict detection already uses in memory_model.py."""
    covered_categories = {(p.get("line_of_business") or "").lower() for p in portfolio}
    return [n for n in needs if (n.get("category") or "").lower() not in covered_categories]


def score_customer(customer_id: str) -> dict[str, Any]:
    """Full transparent priority breakdown for one customer."""
    from backend_v3.advisor.followups import list_followups
    from backend_v3.advisor.prioritization import compute_priority
    from backend_v3.advisor.retrieval import assemble_customer_context

    ctx = assemble_customer_context(customer_id)
    if ctx is None:
        return None

    base = compute_priority(ctx["life_events"], ctx["concerns"], ctx["meetings"])
    unresolved_needs = _needs_without_matching_policy(ctx["needs"], ctx["portfolio"])
    open_followups = list_followups(customer_id=customer_id, status="open")
    conversation_count = len(ctx.get("relevant_conversations") or [])

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

    for concern in ctx["concerns"][:3]:
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
        "name": ctx["name"],
        "priority": priority,
        "score": score,
        "reasons": reasons,
        "unresolved_needs_count": len(unresolved_needs),
        "open_concerns_count": len(ctx["concerns"]),
        "pending_followups_count": len(open_followups),
        "days_since_contact": days_since_contact,
        "is_stale": base["is_stale"],
        "conversation_count": conversation_count,
    }


def score_all_customers() -> list[dict[str, Any]]:
    from backend_v3.advisor.customer_service import list_customer_summaries

    results = []
    for summary in list_customer_summaries():
        scored = score_customer(summary["customer_id"])
        if scored:
            results.append(scored)
    results.sort(key=lambda c: c["score"], reverse=True)
    return results

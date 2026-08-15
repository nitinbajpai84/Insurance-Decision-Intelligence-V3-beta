"""
Insights — Stage 4.

A cross-customer, rolling view rather than My Day's "today" scope:
customers requiring attention, new life events, emerging needs,
unresolved conversations, and follow-up opportunities. Reuses the same
deterministic signals My Day and priority_service already compute — this
is a different lens on the same real data, not a separate scoring system.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.advisor.prioritization import RECENT_EVENT_DAYS


def get_insights() -> dict[str, Any]:
    from backend_v3.advisor.customer_service import list_customer_summaries
    from backend_v3.advisor.followups import list_followups
    from backend_v3.advisor.memory_model import list_all_pending_memories
    from backend_v3.advisor.priority_service import score_all_customers

    customers = list_customer_summaries()

    customers_requiring_attention = [c for c in customers if c["priority"] == "high" or c["open_concerns_count"] > 0]

    new_life_events = [
        {
            "customer_id": c["customer_id"],
            "customer_name": c["name"],
            "description": c["most_recent_life_event"],
            "days_ago": c["most_recent_life_event_days_ago"],
        }
        for c in customers
        if c["most_recent_life_event_days_ago"] is not None and c["most_recent_life_event_days_ago"] <= RECENT_EVENT_DAYS
    ]
    new_life_events.sort(key=lambda e: e["days_ago"])

    emerging_needs = [
        m for m in list_all_pending_memories(limit=50) if m["memory_type"] == "need"
    ]

    unresolved_conversations = [
        m for m in list_all_pending_memories(limit=50)
    ]  # every pending proposal is, by definition, an unresolved conversation outcome

    followup_opportunities = list_followups(status="open")

    top_priority = score_all_customers()[:10]

    return {
        "customers_requiring_attention": customers_requiring_attention[:10],
        "new_life_events": new_life_events[:10],
        "emerging_needs": emerging_needs[:10],
        "unresolved_conversations": unresolved_conversations[:10],
        "followup_opportunities": followup_opportunities[:10],
        "top_priority_customers": top_priority,
        "summary": {
            "customers_requiring_attention": len(customers_requiring_attention),
            "new_life_events": len(new_life_events),
            "emerging_needs": len(emerging_needs),
            "unresolved_conversations": len(unresolved_conversations),
            "followup_opportunities": len(followup_opportunities),
        },
    }

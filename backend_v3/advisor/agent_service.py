"""
Agent Service boundary.

Builds advisor-facing daily work views from customer truth and deterministic
signals. No AI ranking is used for operational priority.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.advisor.prioritization import RECENT_EVENT_DAYS, STALE_CONTACT_DAYS, TODAY


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _customer_detail(customer_id: str) -> dict[str, Any] | None:
    from backend_v3.advisor.customer_service import get_customer_360

    return get_customer_360(customer_id)


def _attention_customers(customers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        c for c in customers
        if c["priority"] == "high" or c["is_stale"] or c["open_concerns_count"] > 0
    ]


def _build_followups(customers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today_iso = TODAY.isoformat()
    followups = []
    for c in _attention_customers(customers):
        reason = "Review recent customer change"
        if c["is_stale"]:
            reason = "Refresh stale customer information"
        elif c["open_concerns_count"]:
            reason = "Follow up on open concern"
        followups.append({
            "task_id": f"followup-{c['customer_id']}",
            "customer_id": c["customer_id"],
            "customer_name": c["name"],
            "title": reason,
            "due_date": today_iso,
            "status": "open",
            "priority": c["priority"],
            "source": "computed_from_customer_graph",
        })
    return followups


def _calendar_meetings() -> dict[str, list[dict[str, Any]]]:
    """Stage 2/3 calendar and meeting-lifecycle data. A calendar that is
    not connected simply contributes nothing — it must never break My Day."""
    try:
        from backend_v3.advisor.meeting_service import (
            list_completed_meetings_awaiting_processing,
            list_meetings_for_date,
            list_meetings_requiring_preparation,
            list_unmatched_meetings,
            list_upcoming_meetings,
        )

        return {
            "today": list_meetings_for_date(),
            "upcoming": list_upcoming_meetings(),
            "unmatched": list_unmatched_meetings(),
            "requiring_preparation": list_meetings_requiring_preparation(),
            "awaiting_processing": list_completed_meetings_awaiting_processing(),
        }
    except Exception:
        return {"today": [], "upcoming": [], "unmatched": [], "requiring_preparation": [], "awaiting_processing": []}


def _pending_memory_reviews(limit: int = 20) -> list[dict[str, Any]]:
    try:
        from backend_v3.advisor.memory_model import list_all_pending_memories

        return list_all_pending_memories(limit=limit)
    except Exception:
        return []


def _overdue_followups(limit: int = 20) -> list[dict[str, Any]]:
    try:
        from backend_v3.advisor.followups import list_followups

        return list_followups(overdue_only=True)[:limit]
    except Exception:
        return []


def get_my_day() -> dict[str, Any]:
    from backend_v3.advisor.customer_service import list_customer_summaries
    from backend_v3.advisor.customer_graph_service import list_customer_relationship_summaries

    customers = list_customer_summaries()
    relationship_rows = list_customer_relationship_summaries()
    today_iso = TODAY.isoformat()
    calendar = _calendar_meetings()

    meetings_today: list[dict[str, Any]] = []
    upcoming_meetings: list[dict[str, Any]] = []
    for row in relationship_rows:
        for meeting in [m for m in row["meetings"] if m.get("date")]:
            meeting_date = _parse_date(meeting.get("date"))
            if meeting_date is None:
                continue
            item = {
                "customer_id": row["customer_id"],
                "customer_name": row["name"],
                "date": str(meeting.get("date")),
                "summary": meeting.get("summary") or "Meeting",
            }
            if str(meeting.get("date")) == today_iso:
                meetings_today.append(item)
            if meeting_date >= TODAY:
                upcoming_meetings.append(item)

    attention = _attention_customers(customers)
    stale = [c for c in customers if c["is_stale"]]
    high_priority = [c for c in customers if c["priority"] == "high"]
    new_events = [
        c for c in customers
        if c["most_recent_life_event_days_ago"] is not None
        and c["most_recent_life_event_days_ago"] <= RECENT_EVENT_DAYS
    ]

    pending_followups = _build_followups(customers)

    # Calendar meetings lead the list — they are the actual schedule.
    # Each is given the Stage 1 keys as well as its calendar fields so
    # existing consumers keep working while new UI can use the extras.
    calendar_today = [
        {
            "customer_id": m["customer_id"],
            "customer_name": m["customer_name"],
            "date": m["date"],
            "summary": m["title"],
            **m,
        }
        for m in calendar["today"]
    ]
    calendar_upcoming = [
        {
            "customer_id": m["customer_id"],
            "customer_name": m["customer_name"],
            "date": m["date"],
            "summary": m["title"],
            **m,
        }
        for m in calendar["upcoming"]
    ]
    meetings_today = calendar_today + meetings_today
    upcoming_meetings = calendar_upcoming + upcoming_meetings
    matched_today = [m for m in calendar["today"] if m["match_status"] == "matched"]

    pending_memory_reviews = _pending_memory_reviews()
    overdue_followups = _overdue_followups()

    return {
        "today": today_iso,
        "calendar_meetings_today": calendar_today,
        "unmatched_meetings": calendar["unmatched"],
        # The success-test line. Counts meetings actually resolved to a
        # customer; an unmatched calendar entry is not yet one.
        "meetings_message": f"You have {len(matched_today)} customer meetings today.",
        # Stage 3: the before/during/after meeting lifecycle.
        "meetings_requiring_preparation": calendar["requiring_preparation"][:8],
        "meetings_awaiting_processing": calendar["awaiting_processing"][:8],
        "memory_updates_awaiting_approval": pending_memory_reviews[:8],
        "overdue_followups": overdue_followups[:8],
        "summary": {
            "customers": len(customers),
            "meetings_today": len(meetings_today),
            "customer_meetings_today": len(matched_today),
            "unmatched_meetings": len(calendar["unmatched"]),
            "upcoming_meetings": len(upcoming_meetings),
            "customers_requiring_attention": len(attention),
            "pending_followups": len(pending_followups),
            "new_customer_events": len(new_events),
            "stale_customer_information": len(stale),
            "high_priority_customers": len(high_priority),
            "meetings_requiring_preparation": len(calendar["requiring_preparation"]),
            "meetings_awaiting_processing": len(calendar["awaiting_processing"]),
            "memory_updates_awaiting_approval": len(pending_memory_reviews),
            "overdue_followups": len(overdue_followups),
        },
        "meetings_today": meetings_today,
        "upcoming_meetings": upcoming_meetings,
        "customers_requiring_attention": attention[:8],
        "pending_followups": pending_followups[:8],
        "new_customer_events": new_events[:8],
        "stale_customer_information": stale[:8],
        "high_priority_customers": high_priority[:8],
    }


def list_tasks() -> list[dict[str, Any]]:
    from backend_v3.advisor.customer_service import list_customer_summaries

    tasks = _build_followups(list_customer_summaries())
    for task in tasks:
        task["type"] = "follow_up"
        task["due_label"] = "Today"
    return tasks


def get_onboarding_result() -> dict[str, Any]:
    day = get_my_day()
    return {
        "customers": day["summary"]["customers"],
        "upcoming_meetings": day["summary"]["upcoming_meetings"],
        "message": f"You have {day['summary']['customers']} customers and {day['summary']['upcoming_meetings']} upcoming meetings.",
    }

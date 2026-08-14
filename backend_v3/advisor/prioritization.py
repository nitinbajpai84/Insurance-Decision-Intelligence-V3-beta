"""
Deterministic customer prioritization for Agent Home — no LLM involved,
just real signals from the graph: recency of life events, concern count,
and days since last contact. Transparent and re-derivable, unlike an
opaque AI-generated priority score would be.
"""
from __future__ import annotations

from datetime import date

TODAY = date(2026, 8, 15)
RECENT_EVENT_DAYS = 90
STALE_CONTACT_DAYS = 180


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def compute_priority(life_events: list[dict], concerns: list[dict], meetings: list[dict]) -> dict:
    most_recent_event = None
    most_recent_event_days = None
    for e in life_events:
        d = _parse_date(e.get("date"))
        if d and (most_recent_event is None or d > _parse_date(most_recent_event.get("date"))):
            most_recent_event = e
    if most_recent_event:
        d = _parse_date(most_recent_event["date"])
        most_recent_event_days = (TODAY - d).days if d else None

    last_meeting = None
    for m in meetings:
        d = _parse_date(m.get("date"))
        if d and (last_meeting is None or d > _parse_date(last_meeting.get("date"))):
            last_meeting = m
    days_since_contact = None
    if last_meeting:
        d = _parse_date(last_meeting["date"])
        days_since_contact = (TODAY - d).days if d else None

    is_recent_event = most_recent_event_days is not None and most_recent_event_days <= RECENT_EVENT_DAYS
    is_stale = days_since_contact is not None and days_since_contact >= STALE_CONTACT_DAYS
    concern_count = len(concerns)

    if is_recent_event or concern_count >= 2 or is_stale:
        priority = "high" if (is_recent_event or is_stale) else "medium"
    elif concern_count >= 1:
        priority = "medium"
    else:
        priority = "low"

    return {
        "priority": priority,
        "days_since_contact": days_since_contact,
        "last_contact_date": last_meeting["date"] if last_meeting else None,
        "is_stale": is_stale,
        "most_recent_life_event": most_recent_event["description"] if most_recent_event else None,
        "most_recent_life_event_days_ago": most_recent_event_days,
        "open_concerns_count": concern_count,
    }

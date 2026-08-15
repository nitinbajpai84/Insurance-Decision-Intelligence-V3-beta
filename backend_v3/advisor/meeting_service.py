"""
Calendar meetings for My Day.

Reads the Meeting nodes the ingestion pipeline wrote and presents them
with their customer match state. Two things this deliberately does not
do:

  - it does not guess a customer for an unmatched meeting. Those come
    back with match_status='match_required' and the UI says
    "Customer match required.";
  - it does not generate a briefing. Preparation stays an explicit
    advisor action, so opening My Day never fires a Gemini call.

"Today" comes from prioritization.TODAY, the same constant the rest of
the advisor surfaces use, so every panel agrees on the date.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.advisor.prioritization import TODAY


from backend_v3.integrations.timeutil import local_time_label as _format_time


def _row_to_meeting(row: dict[str, Any]) -> dict[str, Any]:
    matched = row.get("match_status") == "matched" and row.get("customer_id")
    return {
        "meeting_id": row["meeting_id"],
        "title": row.get("title") or "(no title)",
        "starts_at": row.get("starts_at"),
        "ends_at": row.get("ends_at"),
        "time_label": _format_time(row.get("starts_at")),
        "date": row.get("meeting_date"),
        "meeting_link": row.get("meeting_link"),
        "location": row.get("location"),
        "status": row.get("status") or "confirmed",
        "attendees": row.get("attendees") or [],
        "organizer": row.get("organizer"),
        "source_system": row.get("source_system"),
        "source_label": "Meeting detected from calendar",
        "customer_id": row.get("customer_id") if matched else None,
        "customer_name": row.get("customer_name") if matched else None,
        "match_status": "matched" if matched else "match_required",
        "matched_on": row.get("matched_on"),
        "match_label": (
            f"Customer match: {row.get('customer_name')}" if matched else "Customer match required."
        ),
    }


_SELECT = (
    "OPTIONAL MATCH (c:Customer {customer_id: m.customer_id}) "
    "RETURN m.meeting_id AS meeting_id, m.title AS title, m.starts_at AS starts_at, "
    "m.ends_at AS ends_at, m.meeting_date AS meeting_date, m.meeting_link AS meeting_link, "
    "m.location AS location, m.status AS status, m.attendees AS attendees, "
    "m.organizer AS organizer, m.customer_id AS customer_id, m.match_status AS match_status, "
    "m.matched_on AS matched_on, m.source_system AS source_system, c.name AS customer_name "
)


def list_meetings_for_date(target_date: str | None = None) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    date_iso = target_date or TODAY.isoformat()
    rows = run_query(
        "MATCH (m:CalendarEvent) WHERE m.meeting_date = $date AND coalesce(m.status,'confirmed') <> 'cancelled' "
        + _SELECT
        + "ORDER BY m.starts_at",
        {"date": date_iso},
    )
    return [_row_to_meeting(row) for row in rows]


def list_upcoming_meetings(limit: int = 20) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        "MATCH (m:CalendarEvent) WHERE m.meeting_date >= $date AND coalesce(m.status,'confirmed') <> 'cancelled' "
        + _SELECT
        + "ORDER BY m.starts_at LIMIT $limit",
        {"date": TODAY.isoformat(), "limit": limit},
    )
    return [_row_to_meeting(row) for row in rows]


def list_unmatched_meetings(limit: int = 20) -> list[dict[str, Any]]:
    """Meetings awaiting an advisor decision."""
    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        "MATCH (m:CalendarEvent) WHERE m.match_status = 'match_required' AND m.meeting_date >= $date "
        + _SELECT
        + "ORDER BY m.starts_at LIMIT $limit",
        {"date": TODAY.isoformat(), "limit": limit},
    )
    return [_row_to_meeting(row) for row in rows]


def today_summary() -> dict[str, Any]:
    """Backs the success-test line: 'You have N customer meetings today.'

    The count is meetings resolved to a customer — an unmatched calendar
    entry is not yet a customer meeting.
    """
    meetings = list_meetings_for_date()
    matched = [m for m in meetings if m["match_status"] == "matched"]
    unmatched = [m for m in meetings if m["match_status"] != "matched"]
    return {
        "date": TODAY.isoformat(),
        "total": len(meetings),
        "matched": len(matched),
        "unmatched": len(unmatched),
        "message": f"You have {len(matched)} customer meetings today.",
        "meetings": meetings,
    }

"""
Calendar ingestion — priorities 2 and 3 of Stage 2.

Three sources, all producing models.NormalizedMeeting:

  ics_import        parses a standard iCalendar export. Works today with
                    no third-party credential, because .ics is a file the
                    advisor already has from any calendar product.
  google_calendar   Google Calendar REST API.
  outlook_calendar  Microsoft Graph.

The two API connectors are real request code, not placeholders — they run
the moment OAuth credentials exist. Until then `fetch_*` raises
NotConnected and the provider reports not_connected, rather than
returning invented events.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.integrations.models import NormalizedMeeting, Provenance


class NotConnected(RuntimeError):
    """The provider has no usable credential, so there is nothing to read."""


# --------------------------------------------------------------------------
# iCalendar (.ics)
# --------------------------------------------------------------------------

def _unfold(text: str) -> list[str]:
    """RFC 5545 line folding: a line beginning with space/tab continues the
    previous one."""
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    return (
        value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
    )


def _parse_ics_datetime(value: str, params: dict[str, str]) -> str | None:
    """Return an ISO-8601 string. All-day events (VALUE=DATE) become midnight."""
    value = value.strip()
    if not value:
        return None
    try:
        if params.get("VALUE") == "DATE" or (len(value) == 8 and value.isdigit()):
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc).isoformat()
        if value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
        naive = datetime.strptime(value, "%Y%m%dT%H%M%S")
        # A TZID we cannot resolve is recorded as-is rather than silently
        # shifted into the wrong day.
        return naive.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


_MEETING_LINK = re.compile(
    r"https?://[^\s<>\"]*(?:zoom\.us|teams\.microsoft\.com|meet\.google\.com|webex\.com)[^\s<>\"]*",
    re.I,
)


def parse_ics(content: bytes | str, filename: str = "calendar.ics") -> list[NormalizedMeeting]:
    text = content.decode("utf-8-sig", errors="replace") if isinstance(content, bytes) else content
    meetings: list[NormalizedMeeting] = []
    current: dict[str, Any] | None = None

    for line in _unfold(text):
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            current = {"attendees": []}
            continue
        if stripped == "END:VEVENT":
            if current and current.get("starts_at"):
                uid = current.get("uid") or f"{current.get('summary','event')}-{current['starts_at']}"
                description = current.get("description", "")
                link = current.get("url") or ""
                if not link:
                    found = _MEETING_LINK.search(f"{description} {current.get('location', '')}")
                    link = found.group(0) if found else None
                meetings.append(
                    NormalizedMeeting(
                        external_id=uid,
                        title=current.get("summary") or "(no title)",
                        starts_at=current["starts_at"],
                        ends_at=current.get("ends_at"),
                        attendees=current["attendees"],
                        organizer=current.get("organizer"),
                        meeting_link=link or None,
                        location=current.get("location"),
                        status=(current.get("status") or "confirmed").lower(),
                        provenance=Provenance(
                            source_system="ics",
                            source_id=uid,
                            original_reference=f"{filename}:{uid}",
                        ),
                    )
                )
            current = None
            continue
        if current is None or ":" not in stripped:
            continue

        name_part, _, value = stripped.partition(":")
        pieces = name_part.split(";")
        name = pieces[0].upper()
        params = {}
        for piece in pieces[1:]:
            if "=" in piece:
                key, _, val = piece.partition("=")
                params[key.upper()] = val.strip('"')

        if name == "UID":
            current["uid"] = value.strip()
        elif name == "SUMMARY":
            current["summary"] = _unescape(value.strip())
        elif name == "DESCRIPTION":
            current["description"] = _unescape(value.strip())
        elif name == "LOCATION":
            current["location"] = _unescape(value.strip())
        elif name == "URL":
            current["url"] = value.strip()
        elif name == "STATUS":
            current["status"] = value.strip()
        elif name == "DTSTART":
            current["starts_at"] = _parse_ics_datetime(value, params)
        elif name == "DTEND":
            current["ends_at"] = _parse_ics_datetime(value, params)
        elif name == "ATTENDEE":
            address = re.sub(r"^mailto:", "", value.strip(), flags=re.I)
            if address:
                current["attendees"].append(address)
        elif name == "ORGANIZER":
            current["organizer"] = re.sub(r"^mailto:", "", value.strip(), flags=re.I)

    return meetings


# --------------------------------------------------------------------------
# Google Calendar
# --------------------------------------------------------------------------

def fetch_google_calendar(days_ahead: int = 30, days_back: int = 1) -> list[NormalizedMeeting]:
    import httpx

    from backend_v3.integrations.oauth import refresh_if_needed

    token = refresh_if_needed("google_calendar")
    if not token or not token.get("access_token"):
        raise NotConnected("Google Calendar is not connected.")

    now = datetime.now(timezone.utc)
    response = httpx.get(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        params={
            "timeMin": (now - timedelta(days=days_back)).isoformat(),
            "timeMax": (now + timedelta(days=days_ahead)).isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 250,
        },
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=30.0,
    )
    response.raise_for_status()

    meetings: list[NormalizedMeeting] = []
    for event in response.json().get("items", []):
        start = event.get("start", {})
        starts_at = start.get("dateTime") or start.get("date")
        if not starts_at:
            continue
        end = event.get("end", {})
        organizer = (event.get("organizer") or {}).get("email")
        meetings.append(
            NormalizedMeeting(
                external_id=event["id"],
                title=event.get("summary") or "(no title)",
                starts_at=starts_at,
                ends_at=end.get("dateTime") or end.get("date"),
                attendees=[a.get("email") for a in event.get("attendees", []) if a.get("email")],
                organizer=organizer,
                meeting_link=event.get("hangoutLink") or event.get("htmlLink"),
                location=event.get("location"),
                status=event.get("status", "confirmed"),
                provenance=Provenance(
                    source_system="google_calendar",
                    source_id=event["id"],
                    original_reference=event.get("htmlLink") or event["id"],
                ),
            )
        )
    return meetings


# --------------------------------------------------------------------------
# Microsoft Outlook (Graph)
# --------------------------------------------------------------------------

def fetch_outlook_calendar(days_ahead: int = 30, days_back: int = 1) -> list[NormalizedMeeting]:
    import httpx

    from backend_v3.integrations.oauth import refresh_if_needed

    token = refresh_if_needed("outlook_calendar")
    if not token or not token.get("access_token"):
        raise NotConnected("Microsoft Outlook is not connected.")

    now = datetime.now(timezone.utc)
    response = httpx.get(
        "https://graph.microsoft.com/v1.0/me/calendarView",
        params={
            "startDateTime": (now - timedelta(days=days_back)).isoformat(),
            "endDateTime": (now + timedelta(days=days_ahead)).isoformat(),
            "$orderby": "start/dateTime",
            "$top": 250,
        },
        headers={
            "Authorization": f"Bearer {token['access_token']}",
            "Prefer": 'outlook.timezone="UTC"',
        },
        timeout=30.0,
    )
    response.raise_for_status()

    meetings: list[NormalizedMeeting] = []
    for event in response.json().get("value", []):
        starts_at = (event.get("start") or {}).get("dateTime")
        if not starts_at:
            continue
        organizer = ((event.get("organizer") or {}).get("emailAddress") or {}).get("address")
        attendees = [
            (a.get("emailAddress") or {}).get("address")
            for a in event.get("attendees", [])
            if (a.get("emailAddress") or {}).get("address")
        ]
        meetings.append(
            NormalizedMeeting(
                external_id=event["id"],
                title=event.get("subject") or "(no title)",
                starts_at=starts_at,
                ends_at=(event.get("end") or {}).get("dateTime"),
                attendees=attendees,
                organizer=organizer,
                meeting_link=(event.get("onlineMeeting") or {}).get("joinUrl") or event.get("webLink"),
                location=(event.get("location") or {}).get("displayName"),
                status="cancelled" if event.get("isCancelled") else "confirmed",
                provenance=Provenance(
                    source_system="outlook_calendar",
                    source_id=event["id"],
                    original_reference=event.get("webLink") or event["id"],
                ),
            )
        )
    return meetings


FETCHERS = {
    "google_calendar": fetch_google_calendar,
    "outlook_calendar": fetch_outlook_calendar,
}


def sync_calendar(provider_key: str) -> dict[str, Any]:
    """Pull a calendar and run it through the ingestion pipeline."""
    from backend_v3.integrations.connection_store import record_error
    from backend_v3.integrations.pipeline import ingest

    fetcher = FETCHERS.get(provider_key)
    if fetcher is None:
        raise KeyError(f"No calendar fetcher for '{provider_key}'")

    try:
        meetings = fetcher()
    except NotConnected:
        raise
    except Exception as exc:
        record_error(provider_key, f"{type(exc).__name__}: {exc}")
        raise

    return ingest(source_system=provider_key, meetings=meetings)


def import_ics(content: bytes, filename: str) -> dict[str, Any]:
    from backend_v3.integrations.connection_store import mark_connected
    from backend_v3.integrations.pipeline import ingest

    meetings = parse_ics(content, filename)
    if not meetings:
        return {"counts": {"meetings": 0}, "errors": ["No VEVENT entries found in this file."], "meetings": []}

    outcome = ingest(source_system="ics", meetings=meetings)
    mark_connected("ics", account=filename)
    return outcome

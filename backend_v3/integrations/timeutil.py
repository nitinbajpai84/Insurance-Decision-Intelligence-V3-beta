"""
Shared calendar time handling.

Calendars deliver instants (UTC or an explicit offset); advisors think in
their own local day. Keeping the conversion in one place is what stops a
07:00 Singapore meeting — 23:00 UTC the previous day — from being filed
under yesterday.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def display_tz():
    """Advisor's local zone, falling back to UTC when the platform ships
    no tz database."""
    from backend_v3.config import DISPLAY_TIMEZONE

    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(DISPLAY_TIMEZONE)
    except Exception:
        return timezone.utc


def parse_instant(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def local_date(value: str | None) -> str | None:
    """ISO date in the advisor's zone."""
    parsed = parse_instant(value)
    if parsed is None:
        return str(value)[:10] if value else None
    return parsed.astimezone(display_tz()).date().isoformat()


def local_time_label(value: str | None) -> str:
    """'10:00 AM' in the advisor's zone."""
    parsed = parse_instant(value)
    if parsed is None:
        return ""
    return parsed.astimezone(display_tz()).strftime("%I:%M %p").lstrip("0")

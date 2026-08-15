"""
Microsoft 365 ingestion: Outlook mail, OneDrive, SharePoint, Teams.

All four run on the shared Microsoft account token, so one consent covers
them along with Outlook Calendar.

The same constraints as the Google side apply, for the same reasons:
mail is ingested only for threads that resolve to a customer, bodies past
the retention window are dropped, files are contextual sources, and Teams
transcripts are read only where Graph actually grants them.
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

from backend_v3.integrations.models import NormalizedInteraction, Provenance

GRAPH = "https://graph.microsoft.com/v1.0"
_PLAIN_SUFFIXES = (".txt", ".md", ".csv", ".json", ".htm", ".html")


def _headers() -> dict[str, str]:
    from backend_v3.integrations.account_oauth import bearer

    return {"Authorization": f"Bearer {bearer('microsoft')}"}


def _retention_cutoff() -> datetime:
    from backend_v3.config import COMMUNICATION_RETENTION_DAYS

    return datetime.now(timezone.utc) - timedelta(days=COMMUNICATION_RETENTION_DAYS)


def _parse(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


# --------------------------------------------------------------------------
# Outlook / Microsoft 365 mail
# --------------------------------------------------------------------------

def fetch_m365_mail(max_messages: int = 50, days_back: int = 90) -> dict[str, Any]:
    import httpx

    from backend_v3.integrations.identity import resolve_identity

    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    response = httpx.get(
        f"{GRAPH}/me/messages",
        params={
            "$filter": f"receivedDateTime ge {since}",
            "$select": "id,subject,receivedDateTime,from,toRecipients,ccRecipients,bodyPreview,body,webLink",
            "$orderby": "receivedDateTime desc",
            "$top": min(max_messages, 100),
        },
        headers=_headers(),
        timeout=30.0,
    )
    response.raise_for_status()

    interactions: list[NormalizedInteraction] = []
    skipped_not_customer = 0
    redacted = 0
    cutoff = _retention_cutoff()

    for message in response.json().get("value", []):
        participants: set[str] = set()
        sender = ((message.get("from") or {}).get("emailAddress") or {}).get("address")
        if sender:
            participants.add(sender)
        for field in ("toRecipients", "ccRecipients"):
            for entry in message.get(field) or []:
                address = (entry.get("emailAddress") or {}).get("address")
                if address:
                    participants.add(address)

        matched: str | None = None
        for address in participants:
            match = resolve_identity(email=address, source_system="m365_email")
            if match.resolved:
                matched = match.customer_id
                break

        if not matched:
            skipped_not_customer += 1
            continue

        occurred = _parse(message.get("receivedDateTime"))
        within_retention = occurred >= cutoff
        if not within_retention:
            redacted += 1

        body = ""
        if within_retention:
            content = (message.get("body") or {}).get("content") or message.get("bodyPreview") or ""
            body = re.sub(r"<[^>]+>", " ", content) if "<" in content else content

        interactions.append(
            NormalizedInteraction(
                customer_external_id=matched,
                interaction_type="email",
                occurred_at=occurred.isoformat(),
                summary=message.get("subject") or "(no subject)",
                body=body or None,
                provenance=Provenance(
                    source_system="m365_email",
                    source_id=message["id"],
                    original_reference=message.get("webLink") or message["id"],
                    customer_id=matched,
                ),
            )
        )

    return {
        "interactions": interactions,
        "skipped_not_customer": skipped_not_customer,
        "bodies_dropped_past_retention": redacted,
    }


def sync_m365_email() -> dict[str, Any]:
    from backend_v3.integrations.pipeline import ingest

    result = fetch_m365_mail()
    outcome = ingest(source_system="m365_email", interactions=result["interactions"])
    outcome["skipped_not_customer"] = result["skipped_not_customer"]
    outcome["bodies_dropped_past_retention"] = result["bodies_dropped_past_retention"]
    return outcome


# --------------------------------------------------------------------------
# OneDrive and SharePoint
# --------------------------------------------------------------------------

def _download_text(download_url: str) -> str:
    import httpx

    try:
        response = httpx.get(download_url, timeout=60.0, follow_redirects=True)
        if response.status_code >= 400:
            return ""
        return response.text
    except Exception:
        return ""


def _sync_drive_items(source_system: str, listing_url: str, limit: int) -> dict[str, Any]:
    import httpx

    from backend_v3.integrations.connection_store import record_sync
    from backend_v3.integrations.files import index_document

    response = httpx.get(
        listing_url, params={"$top": min(limit, 100)}, headers=_headers(), timeout=30.0
    )
    response.raise_for_status()

    indexed = 0
    skipped_unsupported = 0
    unmatched = 0

    for item in response.json().get("value", []):
        name = item.get("name") or ""
        if item.get("folder") or not name.lower().endswith(_PLAIN_SUFFIXES):
            # Binary office formats need an extraction step this connector
            # does not own; they are skipped rather than half-indexed.
            skipped_unsupported += 1
            continue

        download_url = item.get("@microsoft.graph.downloadUrl")
        text = _download_text(download_url) if download_url else ""
        if not text.strip():
            skipped_unsupported += 1
            continue

        result = index_document(
            source_system=source_system,
            source_id=item["id"],
            title=name,
            text=re.sub(r"<[^>]+>", " ", text) if name.lower().endswith((".htm", ".html")) else text,
            reference=item.get("webUrl") or item["id"],
            modified_at=item.get("lastModifiedDateTime"),
        )
        if result["indexed"]:
            indexed += 1
        else:
            unmatched += 1

    if indexed:
        record_sync(source_system, {"documents": indexed})
    return {
        "source_system": source_system,
        "counts": {"documents": indexed},
        "skipped_unsupported": skipped_unsupported,
        "unmatched_documents": unmatched,
        "errors": [],
    }


def sync_onedrive(limit: int = 25) -> dict[str, Any]:
    return _sync_drive_items("onedrive", f"{GRAPH}/me/drive/root/children", limit)


def sync_sharepoint(limit: int = 25) -> dict[str, Any]:
    """Index the root document library of the tenant's default site."""
    import httpx

    response = httpx.get(f"{GRAPH}/sites/root", headers=_headers(), timeout=30.0)
    response.raise_for_status()
    site_id = response.json().get("id")
    if not site_id:
        raise RuntimeError("Could not resolve the default SharePoint site for this tenant.")
    return _sync_drive_items("sharepoint", f"{GRAPH}/sites/{site_id}/drive/root/children", limit)


# --------------------------------------------------------------------------
# Teams
# --------------------------------------------------------------------------

def sync_teams(days_back: int = 30) -> dict[str, Any]:
    """Ingest transcripts for the advisor's own online meetings.

    Graph exposes transcripts only where the tenant has granted access and
    the meeting was actually transcribed. A meeting without one is skipped
    and counted — never filled in with generated text.
    """
    import httpx

    from backend_v3.integrations.identity import resolve_identity
    from backend_v3.integrations.pipeline import ingest

    headers = _headers()
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    events = httpx.get(
        f"{GRAPH}/me/events",
        params={
            "$filter": f"start/dateTime ge '{since}' and isOnlineMeeting eq true",
            "$select": "id,subject,start,attendees,onlineMeeting",
            "$top": 50,
        },
        headers=headers,
        timeout=30.0,
    )
    events.raise_for_status()

    interactions: list[NormalizedInteraction] = []
    no_transcript = 0
    unmatched = 0

    for event in events.json().get("value", []):
        join_url = (event.get("onlineMeeting") or {}).get("joinUrl")
        if not join_url:
            no_transcript += 1
            continue

        matched: str | None = None
        for attendee in event.get("attendees") or []:
            address = (attendee.get("emailAddress") or {}).get("address")
            if not address:
                continue
            match = resolve_identity(email=address, source_system="teams")
            if match.resolved:
                matched = match.customer_id
                break
        if not matched:
            unmatched += 1
            continue

        lookup = httpx.get(
            f"{GRAPH}/me/onlineMeetings",
            params={"$filter": f"JoinWebUrl eq '{join_url}'"},
            headers=headers,
            timeout=30.0,
        )
        if lookup.status_code >= 400 or not lookup.json().get("value"):
            no_transcript += 1
            continue
        meeting_id = lookup.json()["value"][0]["id"]

        listing = httpx.get(
            f"{GRAPH}/me/onlineMeetings/{meeting_id}/transcripts", headers=headers, timeout=30.0
        )
        if listing.status_code >= 400 or not listing.json().get("value"):
            no_transcript += 1
            continue

        transcript_id = listing.json()["value"][0]["id"]
        content = httpx.get(
            f"{GRAPH}/me/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content",
            params={"$format": "text/vtt"},
            headers=headers,
            timeout=60.0,
        )
        if content.status_code >= 400 or not content.text.strip():
            no_transcript += 1
            continue

        interactions.append(
            NormalizedInteraction(
                customer_external_id=matched,
                interaction_type="meeting",
                occurred_at=_parse((event.get("start") or {}).get("dateTime")).isoformat(),
                summary=event.get("subject") or "Teams meeting",
                body=content.text,
                provenance=Provenance(
                    source_system="teams",
                    source_id=event["id"],
                    original_reference=join_url,
                    customer_id=matched,
                ),
            )
        )

    outcome = ingest(source_system="teams", interactions=interactions)
    outcome["meetings_without_transcript"] = no_transcript
    outcome["meetings_without_customer_match"] = unmatched
    return outcome

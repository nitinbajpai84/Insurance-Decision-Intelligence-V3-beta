"""
Gmail and Google Drive ingestion.

Both run on the shared Google account token, so connecting Google once
enables them along with Calendar.

Gmail is the most invasive source in the product, so it is the most
constrained:

  - only threads whose participants resolve to a known customer are
    ingested. An advisor's unrelated mail is read to check the sender and
    then discarded, never stored;
  - message bodies older than COMMUNICATION_RETENTION_DAYS are dropped at
    ingestion, keeping the summary but not the original text;
  - the requested scope is gmail.readonly.

Drive files are contextual sources. A document is embedded so retrieval
can cite it; nothing in a file becomes customer truth without travelling
the normal proposal-and-approval path.
"""
from __future__ import annotations

import base64
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.integrations.models import NormalizedInteraction, Provenance

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
DRIVE_API = "https://www.googleapis.com/drive/v3"

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _headers(account_key: str = "google") -> dict[str, str]:
    from backend_v3.integrations.account_oauth import bearer

    return {"Authorization": f"Bearer {bearer(account_key)}"}


def _header_value(payload: dict[str, Any], name: str) -> str:
    for header in (payload.get("headers") or []):
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def _decode_part(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_body(payload: dict[str, Any]) -> str:
    """Prefer text/plain; fall back to stripping tags from text/html."""
    mime = payload.get("mimeType", "")
    body_data = (payload.get("body") or {}).get("data")

    if mime == "text/plain" and body_data:
        return _decode_part(body_data)

    parts = payload.get("parts") or []
    for part in parts:
        if part.get("mimeType") == "text/plain":
            text = _extract_body(part)
            if text:
                return text
    for part in parts:
        if part.get("mimeType", "").startswith("multipart/"):
            text = _extract_body(part)
            if text:
                return text
    for part in parts:
        if part.get("mimeType") == "text/html":
            html = _extract_body(part) or _decode_part((part.get("body") or {}).get("data", ""))
            if html:
                return re.sub(r"<[^>]+>", " ", html)

    if body_data:
        return _decode_part(body_data)
    return ""


def _retention_cutoff() -> datetime:
    from backend_v3.config import COMMUNICATION_RETENTION_DAYS

    return datetime.now(timezone.utc) - timedelta(days=COMMUNICATION_RETENTION_DAYS)


def fetch_gmail_interactions(max_threads: int = 50, days_back: int = 90) -> dict[str, Any]:
    """Customer email threads only."""
    import httpx

    from backend_v3.integrations.identity import resolve_identity

    headers = _headers()
    after = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y/%m/%d")

    listing = httpx.get(
        f"{GMAIL_API}/messages",
        params={"q": f"after:{after} -in:chats", "maxResults": max_threads},
        headers=headers,
        timeout=30.0,
    )
    listing.raise_for_status()

    interactions: list[NormalizedInteraction] = []
    skipped_not_customer = 0
    redacted = 0
    cutoff = _retention_cutoff()

    for stub in listing.json().get("messages", [])[:max_threads]:
        detail = httpx.get(
            f"{GMAIL_API}/messages/{stub['id']}",
            params={"format": "full"},
            headers=headers,
            timeout=30.0,
        )
        if detail.status_code >= 400:
            continue
        message = detail.json()
        payload = message.get("payload") or {}

        participants = set()
        for field in ("From", "To", "Cc"):
            participants.update(_EMAIL_RE.findall(_header_value(payload, field)))

        matched: str | None = None
        for address in participants:
            match = resolve_identity(email=address, source_system="gmail")
            if match.resolved:
                matched = match.customer_id
                break

        if not matched:
            # Not a customer thread — nothing about it is stored.
            skipped_not_customer += 1
            continue

        try:
            occurred = datetime.fromtimestamp(int(message.get("internalDate", 0)) / 1000, tz=timezone.utc)
        except (TypeError, ValueError):
            occurred = datetime.now(timezone.utc)

        subject = _header_value(payload, "Subject") or "(no subject)"
        within_retention = occurred >= cutoff
        if not within_retention:
            redacted += 1

        interactions.append(
            NormalizedInteraction(
                customer_external_id=matched,
                interaction_type="email",
                occurred_at=occurred.isoformat(),
                summary=subject,
                body=_extract_body(payload) if within_retention else None,
                provenance=Provenance(
                    source_system="gmail",
                    source_id=message["id"],
                    original_reference=f"https://mail.google.com/mail/u/0/#inbox/{message['id']}",
                    customer_id=matched,
                ),
            )
        )

    return {
        "interactions": interactions,
        "skipped_not_customer": skipped_not_customer,
        "bodies_dropped_past_retention": redacted,
    }


def sync_gmail() -> dict[str, Any]:
    from backend_v3.integrations.pipeline import ingest

    result = fetch_gmail_interactions()
    outcome = ingest(source_system="gmail", interactions=result["interactions"])
    outcome["skipped_not_customer"] = result["skipped_not_customer"]
    outcome["bodies_dropped_past_retention"] = result["bodies_dropped_past_retention"]
    return outcome


# --------------------------------------------------------------------------
# Google Drive
# --------------------------------------------------------------------------

# Google-native formats must be exported rather than downloaded.
_EXPORTABLE = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.presentation": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
}
_PLAIN = ("text/plain", "text/markdown", "text/csv")


def list_drive_files(limit: int = 50) -> list[dict[str, Any]]:
    import httpx

    response = httpx.get(
        f"{DRIVE_API}/files",
        params={
            "pageSize": min(limit, 100),
            "fields": "files(id,name,mimeType,modifiedTime,webViewLink,owners)",
            "q": "trashed = false",
            "orderBy": "modifiedTime desc",
        },
        headers=_headers(),
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json().get("files", [])


def fetch_drive_text(file_id: str, mime_type: str) -> str:
    import httpx

    headers = _headers()
    if mime_type in _EXPORTABLE:
        response = httpx.get(
            f"{DRIVE_API}/files/{file_id}/export",
            params={"mimeType": _EXPORTABLE[mime_type]},
            headers=headers,
            timeout=60.0,
        )
    elif mime_type in _PLAIN:
        response = httpx.get(
            f"{DRIVE_API}/files/{file_id}", params={"alt": "media"}, headers=headers, timeout=60.0
        )
    else:
        # Binary formats need an extraction step this connector does not own.
        return ""
    if response.status_code >= 400:
        return ""
    return response.text


def sync_google_drive(limit: int = 25) -> dict[str, Any]:
    """Index Drive documents as contextual sources."""
    from backend_v3.integrations.files import index_document

    indexed = 0
    skipped_unsupported = 0
    unmatched = 0

    for file in list_drive_files(limit):
        text = fetch_drive_text(file["id"], file.get("mimeType", ""))
        if not text.strip():
            skipped_unsupported += 1
            continue
        result = index_document(
            source_system="google_drive",
            source_id=file["id"],
            title=file.get("name") or "Untitled",
            text=text,
            reference=file.get("webViewLink") or file["id"],
            modified_at=file.get("modifiedTime"),
        )
        if result["indexed"]:
            indexed += 1
        else:
            unmatched += 1

    from backend_v3.integrations.connection_store import record_sync

    if indexed:
        record_sync("google_drive", {"documents": indexed})
    return {
        "source_system": "google_drive",
        "counts": {"documents": indexed},
        "skipped_unsupported": skipped_unsupported,
        "unmatched_documents": unmatched,
        "errors": [],
    }

"""
Stage 2 integration + ingestion API.

Connection Center, OAuth connect/callback/disconnect, on-demand sync,
CSV/Excel import (preview then commit), and calendar file import.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# main.py mounts these under /api/v3.
router = APIRouter(prefix="/integrations", tags=["integrations"])
import_router = APIRouter(prefix="/import", tags=["import"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class ManualMatchRequest(BaseModel):
    meeting_id: str
    customer_id: str


@router.get("")
def list_connection_center() -> list[dict[str, Any]]:
    from backend_v3.advisor.integration_service import connection_center

    try:
        return connection_center()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not read connection state: {exc}") from None


@router.get("/audit")
def list_audit(subject_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    from backend_v3.integrations.audit import list_events

    try:
        return list_events(subject_id=subject_id, limit=min(limit, 200))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.post("/{provider_key}/connect")
def connect(provider_key: str) -> dict[str, Any]:
    from backend_v3.advisor.integration_service import start_connect

    try:
        return start_connect(provider_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_key}'") from None
    except RuntimeError as exc:
        # Not an error condition — the provider genuinely cannot connect yet.
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.get("/{provider_key}/callback", response_class=HTMLResponse)
def oauth_callback(provider_key: str, code: str = "", state: str = "", error: str = "") -> HTMLResponse:
    """OAuth redirect target. Returns a small page rather than JSON because
    a browser lands here directly."""
    from backend_v3.integrations.connection_store import mark_connected
    from backend_v3.integrations.oauth import consume_state, exchange_code

    def page(title: str, detail: str, ok: bool) -> HTMLResponse:
        color = "#0f766e" if ok else "#be123c"
        return HTMLResponse(
            f"<!doctype html><meta charset='utf-8'><title>{title}</title>"
            f"<body style=\"font-family:system-ui;padding:2.5rem;max-width:40rem\">"
            f"<h1 style='color:{color};font-size:1.25rem'>{title}</h1>"
            f"<p style='color:#334155'>{detail}</p>"
            f"<p><a href='/advisor/connections'>Return to Connections</a></p></body>",
            status_code=200 if ok else 400,
        )

    if error:
        return page("Authorization declined", f"The provider reported: {error}", False)
    if not code or not consume_state(state, provider_key):
        return page("Authorization failed", "The authorization state was missing, expired, or already used.", False)

    try:
        result = exchange_code(provider_key, code)
        mark_connected(provider_key, account=result.get("account") or "connected account")
        return page("Connected", f"{provider_key} is now connected. You can run a sync from Connections.", True)
    except Exception as exc:
        return page("Connection failed", f"{type(exc).__name__}: {exc}", False)


@router.post("/{provider_key}/disconnect")
def disconnect(provider_key: str) -> dict[str, Any]:
    from backend_v3.advisor.integration_service import disconnect_provider

    try:
        return disconnect_provider(provider_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_key}'") from None
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from None


@router.post("/{provider_key}/sync")
def sync(provider_key: str) -> dict[str, Any]:
    from backend_v3.advisor.integration_service import sync_provider
    from backend_v3.integrations.calendar_sources import NotConnected

    try:
        return sync_provider(provider_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_key}'") from None
    except NotConnected as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sync failed: {exc}") from None


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB upload limit.")
    return content


@import_router.post("/csv/preview")
async def csv_preview(file: UploadFile = File(...), dataset: str = Form("customers")) -> dict[str, Any]:
    from backend_v3.integrations.csv_import import ImportError_, preview

    content = await _read_upload(file)
    try:
        return preview(content, file.filename or "upload.csv", dataset)
    except ImportError_ as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read the file: {exc}") from None


@import_router.post("/csv/commit")
async def csv_commit(file: UploadFile = File(...), dataset: str = Form("customers")) -> dict[str, Any]:
    from backend_v3.integrations.csv_import import ImportError_, commit

    content = await _read_upload(file)
    try:
        return commit(content, file.filename or "upload.csv", dataset)
    except ImportError_ as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from None


@import_router.post("/calendar/ics")
async def calendar_ics(file: UploadFile = File(...)) -> dict[str, Any]:
    from backend_v3.integrations.calendar_sources import import_ics

    content = await _read_upload(file)
    try:
        return import_ics(content, file.filename or "calendar.ics")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Calendar import failed: {exc}") from None


@import_router.post("/meetings/match")
def match_meeting(payload: ManualMatchRequest) -> dict[str, Any]:
    """Advisor resolves a "Customer match required." meeting by hand.

    The confirmed attendee address is registered as an identity, so every
    future meeting with that person matches deterministically.
    """
    from backend_v3.graph_store.neo4j_client import run_query, run_write
    from backend_v3.integrations.audit import audit
    from backend_v3.integrations.identity import register_identity

    rows = run_query(
        "MATCH (m:Meeting {meeting_id: $meeting_id}) "
        "RETURN m.attendees AS attendees, m.organizer AS organizer, m.source_system AS source_system",
        {"meeting_id": payload.meeting_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Meeting '{payload.meeting_id}' not found")

    customer = run_query(
        "MATCH (c:Customer {customer_id: $customer_id}) RETURN c.name AS name",
        {"customer_id": payload.customer_id},
    )
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer '{payload.customer_id}' not found")

    run_write(
        "MATCH (m:Meeting {meeting_id: $meeting_id}), (c:Customer {customer_id: $customer_id}) "
        "SET m.customer_id = $customer_id, m.match_status = 'matched', m.matched_on = 'advisor_confirmed' "
        "MERGE (c)-[r:HAS_MEETING]->(m) "
        "SET r.source = 'advisor_confirmed', r.confidence = 1.0",
        {"meeting_id": payload.meeting_id, "customer_id": payload.customer_id},
    )

    organizer = (rows[0].get("organizer") or "").strip().lower()
    learned = []
    for attendee in rows[0].get("attendees") or []:
        if attendee and attendee.strip().lower() != organizer:
            register_identity(
                payload.customer_id, "calendar_attendee", attendee,
                rows[0].get("source_system") or "calendar",
            )
            learned.append(attendee)

    audit(
        "meeting.matched",
        subject_id=payload.meeting_id,
        metadata={"customer_id": payload.customer_id, "identities_learned": learned},
    )
    return {
        "meeting_id": payload.meeting_id,
        "customer_id": payload.customer_id,
        "customer_name": customer[0]["name"],
        "match_status": "matched",
        "identities_learned": learned,
    }

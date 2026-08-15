"""
Account connection API.

One account (Google / Microsoft / WhatsApp Business) owns one credential
and one consent, unlocking several capabilities. These endpoints cover
the whole setup path an advisor walks: read the requirements, save the
credentials, authorize, sync, disconnect.

Credential values are write-only across this API. Nothing here ever
returns a stored secret — `credential_status` yields presence and masked
hints only.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# main.py mounts this under /api/v3.
router = APIRouter(prefix="/integrations", tags=["accounts"])


class CredentialPayload(BaseModel):
    values: dict[str, str]


class ConnectPayload(BaseModel):
    capabilities: list[str] | None = None


def _result_page(title: str, detail: str, ok: bool) -> HTMLResponse:
    color = "#0f766e" if ok else "#be123c"
    return HTMLResponse(
        f"<!doctype html><meta charset='utf-8'><title>{title}</title>"
        f"<body style=\"font-family:system-ui;padding:2.5rem;max-width:40rem\">"
        f"<h1 style='color:{color};font-size:1.25rem'>{title}</h1>"
        f"<p style='color:#334155;line-height:1.6'>{detail}</p>"
        f"<p><a href='/advisor/connections'>Return to Connections</a></p></body>",
        status_code=200 if ok else 400,
    )


@router.get("/accounts")
def list_accounts() -> list[dict[str, Any]]:
    from backend_v3.integrations.accounts import describe_account, list_accounts as accounts

    return [describe_account(account) for account in accounts()]


@router.get("/accounts/{account_key}")
def get_account_detail(account_key: str) -> dict[str, Any]:
    from backend_v3.integrations.accounts import describe_account, get_account

    try:
        return describe_account(get_account(account_key))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown account '{account_key}'") from None


@router.put("/accounts/{account_key}/credentials")
def save_account_credentials(account_key: str, payload: CredentialPayload) -> dict[str, Any]:
    from backend_v3.integrations.credentials import save_credentials
    from backend_v3.integrations.token_store import EncryptionUnavailable

    try:
        return save_credentials(account_key, payload.values)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown account '{account_key}'") from None
    except EncryptionUnavailable as exc:
        # Refusing is correct: storing a client secret in plaintext would
        # be worse than failing to connect.
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.delete("/accounts/{account_key}/credentials")
def remove_account_credentials(account_key: str) -> dict[str, Any]:
    from backend_v3.integrations.credentials import delete_credentials

    try:
        return delete_credentials(account_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown account '{account_key}'") from None


@router.post("/accounts/{account_key}/connect")
def connect_account(account_key: str, payload: ConnectPayload | None = None) -> dict[str, Any]:
    """Start the account's connect flow.

    OAuth accounts return an authorization URL for the browser to follow.
    WhatsApp validates its token against Meta and connects immediately,
    since it has no consent screen.
    """
    from backend_v3.integrations.accounts import get_account

    try:
        account = get_account(account_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown account '{account_key}'") from None

    if account.auth_kind == "api_token":
        from backend_v3.integrations.whatsapp import connect as whatsapp_connect

        try:
            return {"mode": "api_token", **whatsapp_connect()}
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach Meta: {exc}") from None

    from backend_v3.integrations.account_oauth import build_authorization_url

    try:
        return {"mode": "oauth2", **build_authorization_url(account_key, (payload.capabilities if payload else None))}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.get("/accounts/{account_key}/callback", response_class=HTMLResponse)
def account_callback(account_key: str, code: str = "", state: str = "", error: str = "", error_description: str = "") -> HTMLResponse:
    from backend_v3.integrations.account_oauth import consume_state, exchange_code

    if error:
        return _result_page("Authorization declined", error_description or error, False)

    consumed = consume_state(state, account_key)
    if not code or consumed is None:
        return _result_page(
            "Authorization failed",
            "The authorization state was missing, expired, or already used. Start the connection again.",
            False,
        )

    try:
        result = exchange_code(account_key, code, consumed["capabilities"])
    except Exception as exc:
        return _result_page("Connection failed", f"{type(exc).__name__}: {exc}", False)

    enabled = ", ".join(result["capabilities"]) or "no capabilities"
    return _result_page(
        "Connected",
        f"Signed in as {result['account_label'] or 'your account'}. Enabled: {enabled}. "
        "You can run a sync from the Connections page.",
        True,
    )


@router.post("/accounts/{account_key}/disconnect")
def disconnect_account_route(account_key: str) -> dict[str, Any]:
    from backend_v3.integrations.account_oauth import disconnect_account
    from backend_v3.integrations.accounts import get_account

    try:
        account = get_account(account_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown account '{account_key}'") from None

    if account.auth_kind == "api_token":
        from backend_v3.integrations.connection_store import disconnect
        from backend_v3.integrations.credentials import delete_credentials

        for capability in account.capabilities:
            disconnect(capability)
        delete_credentials(account_key)
        return {"account": account_key, "capabilities_disconnected": list(account.capabilities)}

    return disconnect_account(account_key)


# --------------------------------------------------------------------------
# WhatsApp webhook
# --------------------------------------------------------------------------

@router.get("/whatsapp/webhook", response_class=PlainTextResponse)
def whatsapp_verify(
    hub_mode: str = "",
    hub_verify_token: str = "",
    hub_challenge: str = "",
    request: Request = None,  # type: ignore[assignment]
) -> PlainTextResponse:
    """Meta's subscription handshake.

    Meta sends hub.mode / hub.verify_token / hub.challenge — names FastAPI
    cannot bind directly, so they are read from the raw query string.
    """
    params = dict(request.query_params) if request is not None else {}
    mode = params.get("hub.mode", hub_mode)
    token = params.get("hub.verify_token", hub_verify_token)
    challenge = params.get("hub.challenge", hub_challenge)

    from backend_v3.integrations.whatsapp import verify_webhook

    result = verify_webhook(mode, token, challenge)
    if result is None:
        raise HTTPException(status_code=403, detail="Webhook verification failed.")
    return PlainTextResponse(result)


@router.post("/whatsapp/webhook")
async def whatsapp_receive(request: Request) -> dict[str, Any]:
    from backend_v3.integrations.whatsapp import handle_webhook

    payload = await request.json()
    try:
        return handle_webhook(payload)
    except Exception as exc:
        # Meta retries on non-2xx, so a persistent bug would loop. Report
        # the failure in the body instead.
        return {"received": True, "ingested": False, "error": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------
# CRM
# --------------------------------------------------------------------------

@router.get("/crm")
def list_crm() -> list[dict[str, Any]]:
    from backend_v3.integrations.crm_sources import describe_vendor, list_vendors

    return [describe_vendor(vendor) for vendor in list_vendors()]


@router.put("/crm/{vendor_key}/credentials")
def save_crm_credentials(vendor_key: str, payload: CredentialPayload) -> dict[str, Any]:
    from backend_v3.integrations.credentials import save_credentials
    from backend_v3.integrations.crm_sources import get_vendor
    from backend_v3.integrations.token_store import EncryptionUnavailable

    try:
        get_vendor(vendor_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown CRM '{vendor_key}'") from None

    try:
        return save_credentials(f"crm_{vendor_key}", payload.values)
    except EncryptionUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/crm/{vendor_key}/connect")
def connect_crm(vendor_key: str) -> dict[str, Any]:
    """Salesforce redirects to OAuth; token-based CRMs validate and connect."""
    from backend_v3.integrations.crm_sources import get_vendor

    try:
        vendor = get_vendor(vendor_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown CRM '{vendor_key}'") from None

    if vendor_key == "salesforce":
        from backend_v3.integrations.crm_sources import salesforce_authorization_url

        try:
            return {"mode": "oauth2", **salesforce_authorization_url()}
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    if vendor_key == "hubspot":
        from backend_v3.integrations.connection_store import mark_connected
        from backend_v3.integrations.crm_sources import hubspot_verify

        try:
            hubspot_verify()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach HubSpot: {exc}") from None
        mark_connected("crm_hubspot", account="HubSpot private app")
        return {"mode": "api_token", "provider": "crm_hubspot", "connected": True}

    # Partner-gated vendors: credentials alone are not proof of access, so
    # a sync attempt is what establishes the connection.
    from backend_v3.integrations.credentials import credential_status

    status = credential_status(f"crm_{vendor_key}")
    if not status["configured"]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{vendor.name} needs its API base URL and token, both issued by {vendor.name} "
                f"with your API agreement. Until then, import a CSV export ({vendor.csv_export_hint})."
            ),
        )
    return {"mode": "api_token", "provider": f"crm_{vendor_key}", "connected": False, "next": "run_sync"}


@router.get("/crm/salesforce/callback", response_class=HTMLResponse)
def salesforce_callback(code: str = "", error: str = "") -> HTMLResponse:
    from backend_v3.integrations.crm_sources import salesforce_exchange_code

    if error or not code:
        return _result_page("Authorization failed", error or "No authorization code was returned.", False)
    try:
        result = salesforce_exchange_code(code)
    except Exception as exc:
        return _result_page("Connection failed", f"{type(exc).__name__}: {exc}", False)
    return _result_page(
        "Salesforce connected",
        f"Connected to {result.get('instance_url')}. Run a sync from the Connections page.",
        True,
    )

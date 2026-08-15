"""
Account-level OAuth: one consent, many capabilities.

Stage 2 ran a separate authorization-code flow per provider, so an
advisor wanting Calendar, Gmail, and Drive faced three consent screens
and three stored tokens for the same Google account. This module runs one
flow per account provider, requesting the union of scopes for whichever
capabilities the advisor enabled, and stores a single token the whole
group shares.

Every capability under an account therefore connects, refreshes, and
revokes together — which is what actually matches the credential.
"""
from __future__ import annotations

import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STATE_TTL_MINUTES = 10

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v2/userinfo"
GRAPH_ME = "https://graph.microsoft.com/v1.0/me"


def _microsoft_base(tenant: str) -> str:
    return f"https://login.microsoftonline.com/{tenant or 'common'}/oauth2/v2.0"


def _endpoints(account_key: str) -> tuple[str, str]:
    from backend_v3.integrations.credentials import get_credentials

    if account_key == "google":
        return GOOGLE_AUTH, GOOGLE_TOKEN
    if account_key == "microsoft":
        tenant = get_credentials("microsoft").get("tenant") or "common"
        base = _microsoft_base(tenant)
        return f"{base}/authorize", f"{base}/token"
    raise KeyError(f"'{account_key}' is not an OAuth authorization-code account")


def _issue_state(account_key: str, capabilities: list[str]) -> str:
    from backend_v3.graph_store.neo4j_client import run_write

    state = secrets.token_urlsafe(32)
    run_write(
        "CREATE (s:OAuthState {state: $state, account: $account, capabilities: $capabilities, expires_at: $expires})",
        {
            "state": state,
            "account": account_key,
            "capabilities": capabilities,
            "expires": (datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)).isoformat(),
        },
    )
    return state


def consume_state(state: str, account_key: str) -> dict[str, Any] | None:
    """Single-use: deleted whether or not it was still valid."""
    from backend_v3.graph_store.neo4j_client import run_write

    rows = run_write(
        "MATCH (s:OAuthState {state: $state, account: $account}) "
        "WITH s, s.expires_at AS expires_at, s.capabilities AS capabilities "
        "DELETE s RETURN expires_at, capabilities",
        {"state": state, "account": account_key},
    )
    if not rows:
        return None
    try:
        if datetime.fromisoformat(rows[0]["expires_at"]) <= datetime.now(timezone.utc):
            return None
    except (TypeError, ValueError):
        return None
    return {"capabilities": rows[0].get("capabilities") or []}


def build_authorization_url(account_key: str, capabilities: list[str] | None = None) -> dict[str, Any]:
    from backend_v3.integrations.accounts import get_account, scopes_for
    from backend_v3.integrations.credentials import credential_status, get_credentials

    account = get_account(account_key)
    if account.auth_kind != "oauth2_authorization_code":
        raise RuntimeError(f"{account.name} does not use an OAuth sign-in flow.")

    status = credential_status(account_key)
    if not status["configured"]:
        raise RuntimeError(
            f"{account.name} needs its OAuth client credentials first. "
            f"Add them on the {account.name} setup screen."
        )

    selected = [c for c in (capabilities or list(account.capabilities)) if c in account.capabilities]
    if not selected:
        selected = list(account.capabilities)

    scopes = scopes_for(account, selected)
    creds = get_credentials(account_key)
    auth_endpoint, _ = _endpoints(account_key)

    params = {
        "client_id": creds["client_id"],
        "redirect_uri": account.redirect_uri(),
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": _issue_state(account_key, selected),
    }
    if account_key == "google":
        # Required for a refresh token on Google's consent flow.
        params["access_type"] = "offline"
        params["prompt"] = "consent"
        params["include_granted_scopes"] = "true"
    else:
        params["response_mode"] = "query"

    return {
        "account": account_key,
        "authorization_url": f"{auth_endpoint}?{urlencode(params)}",
        "scopes": scopes,
        "capabilities": selected,
        "redirect_uri": account.redirect_uri(),
    }


def exchange_code(account_key: str, code: str, capabilities: list[str]) -> dict[str, Any]:
    """Trade the code for tokens, store once, mark each capability connected."""
    import httpx

    from backend_v3.integrations.accounts import get_account
    from backend_v3.integrations.connection_store import mark_connected
    from backend_v3.integrations.credentials import get_credentials
    from backend_v3.integrations.token_store import save_token

    account = get_account(account_key)
    creds = get_credentials(account_key)
    _, token_endpoint = _endpoints(account_key)

    response = httpx.post(
        token_endpoint,
        data={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": account.redirect_uri(),
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("expires_in"):
        payload["expires_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=int(payload["expires_in"]))
        ).isoformat()

    account_label = _fetch_account_label(account_key, payload.get("access_token", ""))
    payload["granted_capabilities"] = capabilities

    # One token for the account; connectors resolve it via account_token().
    save_token(f"account:{account_key}", account_label, payload)

    for capability in capabilities:
        mark_connected(capability, account=account_label or account.name)

    return {"account": account_key, "account_label": account_label, "capabilities": capabilities}


def account_token(account_key: str) -> dict[str, Any] | None:
    """Usable access token for the account, refreshed if expired."""
    import httpx

    from backend_v3.integrations.credentials import get_credentials
    from backend_v3.integrations.token_store import load_token, save_token

    token = load_token(f"account:{account_key}")
    if not token:
        return None

    expires_at = token.get("expires_at")
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at) > datetime.now(timezone.utc) + timedelta(seconds=60):
                return token
        except ValueError:
            pass

    refresh = token.get("refresh_token")
    if not refresh:
        return token

    creds = get_credentials(account_key)
    _, token_endpoint = _endpoints(account_key)
    response = httpx.post(
        token_endpoint,
        data={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    refreshed = response.json()
    # Refresh responses usually omit these; carry them forward.
    refreshed.setdefault("refresh_token", refresh)
    refreshed.setdefault("granted_capabilities", token.get("granted_capabilities", []))
    if refreshed.get("expires_in"):
        refreshed["expires_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=int(refreshed["expires_in"]))
        ).isoformat()

    from backend_v3.integrations.connection_store import get_connection

    label = (get_connection(list(refreshed.get("granted_capabilities") or ["" ])[0]) or {}).get("account") or ""
    save_token(f"account:{account_key}", label, refreshed)
    return refreshed


def bearer(account_key: str) -> str:
    """Access token for a connected account, or raise NotConnected."""
    from backend_v3.integrations.calendar_sources import NotConnected

    token = account_token(account_key)
    if not token or not token.get("access_token"):
        from backend_v3.integrations.accounts import get_account

        raise NotConnected(f"{get_account(account_key).name} is not connected.")
    return token["access_token"]


def disconnect_account(account_key: str) -> dict[str, Any]:
    """Revoke upstream where supported, then destroy the local credential
    and every capability connection under this account."""
    import httpx

    from backend_v3.integrations.accounts import get_account
    from backend_v3.integrations.audit import audit
    from backend_v3.integrations.connection_store import disconnect
    from backend_v3.integrations.token_store import load_token, revoke_token

    account = get_account(account_key)
    upstream = "not_supported"

    try:
        token = load_token(f"account:{account_key}")
    except Exception:
        token = None

    if token and account_key == "google":
        try:
            response = httpx.post(
                GOOGLE_REVOKE, data={"token": token.get("access_token", "")}, timeout=20.0
            )
            upstream = "revoked" if response.status_code < 400 else f"failed_{response.status_code}"
        except Exception as exc:
            upstream = f"failed_{type(exc).__name__}"

    # Local removal happens regardless: a failed remote revoke must not
    # leave a working token behind.
    removed = revoke_token(f"account:{account_key}")
    for capability in account.capabilities:
        disconnect(capability)

    audit("integration.account_disconnected", subject_id=account_key, metadata={"upstream": upstream})
    return {
        "account": account_key,
        "upstream_revocation": upstream,
        "local_credentials_removed": removed,
        "capabilities_disconnected": list(account.capabilities),
    }


def _fetch_account_label(account_key: str, access_token: str) -> str:
    if not access_token:
        return ""
    import httpx

    url = GRAPH_ME if account_key == "microsoft" else GOOGLE_USERINFO
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=20.0)
        response.raise_for_status()
        data = response.json()
        return data.get("mail") or data.get("userPrincipalName") or data.get("email") or ""
    except Exception:
        return ""

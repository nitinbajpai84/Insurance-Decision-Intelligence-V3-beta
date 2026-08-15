"""
OAuth 2.0 authorization-code framework shared by every credentialed
provider.

Least privilege is enforced structurally: the scopes requested are the
ones declared on the provider in registry.py, and nothing may pass extra
scopes through. Read-only scopes are what those declarations contain.

State parameters are single-use and expire, which is what stops a
cross-site request from completing a connection on the advisor's behalf.
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

AUTH_ENDPOINTS = {
    "google_calendar": "https://accounts.google.com/o/oauth2/v2/auth",
    "gmail": "https://accounts.google.com/o/oauth2/v2/auth",
    "google_drive": "https://accounts.google.com/o/oauth2/v2/auth",
    "google_meet": "https://accounts.google.com/o/oauth2/v2/auth",
}
TOKEN_ENDPOINTS = {
    "google_calendar": "https://oauth2.googleapis.com/token",
    "gmail": "https://oauth2.googleapis.com/token",
    "google_drive": "https://oauth2.googleapis.com/token",
    "google_meet": "https://oauth2.googleapis.com/token",
}
REVOKE_ENDPOINTS = {
    "google_calendar": "https://oauth2.googleapis.com/revoke",
    "gmail": "https://oauth2.googleapis.com/revoke",
    "google_drive": "https://oauth2.googleapis.com/revoke",
    "google_meet": "https://oauth2.googleapis.com/revoke",
}

_MICROSOFT_PROVIDERS = {"outlook_calendar", "m365_email", "teams", "onedrive", "sharepoint"}


def _microsoft_base() -> str:
    from backend_v3.config import MS_OAUTH_TENANT

    return f"https://login.microsoftonline.com/{MS_OAUTH_TENANT}/oauth2/v2.0"


def _client_credentials(provider: str) -> tuple[str, str]:
    from backend_v3 import config

    if provider in _MICROSOFT_PROVIDERS:
        return config.MS_OAUTH_CLIENT_ID, config.MS_OAUTH_CLIENT_SECRET
    return config.GOOGLE_OAUTH_CLIENT_ID, config.GOOGLE_OAUTH_CLIENT_SECRET


def _auth_endpoint(provider: str) -> str:
    if provider in _MICROSOFT_PROVIDERS:
        return f"{_microsoft_base()}/authorize"
    if provider in AUTH_ENDPOINTS:
        return AUTH_ENDPOINTS[provider]
    raise KeyError(f"No OAuth authorize endpoint registered for '{provider}'")


def _token_endpoint(provider: str) -> str:
    if provider in _MICROSOFT_PROVIDERS:
        return f"{_microsoft_base()}/token"
    if provider in TOKEN_ENDPOINTS:
        return TOKEN_ENDPOINTS[provider]
    raise KeyError(f"No OAuth token endpoint registered for '{provider}'")


def redirect_uri(provider: str) -> str:
    from backend_v3.config import OAUTH_REDIRECT_BASE

    return f"{OAUTH_REDIRECT_BASE.rstrip('/')}/api/v3/integrations/{provider}/callback"


def _issue_state(provider: str) -> str:
    from backend_v3.graph_store.neo4j_client import run_write

    state = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)
    run_write(
        "CREATE (s:OAuthState {state: $state, provider: $provider, expires_at: $expires})",
        {"state": state, "provider": provider, "expires": expires.isoformat()},
    )
    return state


def consume_state(state: str, provider: str) -> bool:
    """Single-use: the state is deleted whether or not it was still valid."""
    from backend_v3.graph_store.neo4j_client import run_write

    rows = run_write(
        "MATCH (s:OAuthState {state: $state, provider: $provider}) "
        "WITH s, s.expires_at AS expires_at DELETE s RETURN expires_at",
        {"state": state, "provider": provider},
    )
    if not rows:
        return False
    try:
        return datetime.fromisoformat(rows[0]["expires_at"]) > datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return False


def build_authorization_url(provider_key: str) -> dict[str, Any]:
    """Start an authorization-code flow using only the provider's declared
    scopes."""
    from backend_v3.integrations.registry import get_provider

    provider = get_provider(provider_key)
    missing = provider.missing_config()
    if missing:
        raise RuntimeError(
            f"{provider.name} cannot be connected yet: {', '.join(missing)} not set. "
            "Register an OAuth client with the provider and add the credentials to .env."
        )

    client_id, _ = _client_credentials(provider_key)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri(provider_key),
        "response_type": "code",
        "scope": " ".join(provider.scopes),
        "state": _issue_state(provider_key),
    }
    if provider_key in _MICROSOFT_PROVIDERS:
        params["response_mode"] = "query"
    else:
        # Needed for a refresh token on Google's consent flow.
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    return {
        "authorization_url": f"{_auth_endpoint(provider_key)}?{urlencode(params)}",
        "scopes": list(provider.scopes),
        "redirect_uri": params["redirect_uri"],
    }


def exchange_code(provider_key: str, code: str) -> dict[str, Any]:
    """Trade an authorization code for tokens, then store them encrypted."""
    import httpx

    from backend_v3.integrations import token_store

    client_id, client_secret = _client_credentials(provider_key)
    response = httpx.post(
        _token_endpoint(provider_key),
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri(provider_key),
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("expires_in"):
        payload["expires_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=int(payload["expires_in"]))
        ).isoformat()

    account = _fetch_account_label(provider_key, payload.get("access_token", ""))
    token_store.save_token(provider_key, account, payload)
    return {"account": account, "scopes": payload.get("scope", "")}


def refresh_if_needed(provider_key: str) -> dict[str, Any] | None:
    """Return a usable token bundle, refreshing when expired."""
    import httpx

    from backend_v3.integrations import token_store

    token = token_store.load_token(provider_key)
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

    client_id, client_secret = _client_credentials(provider_key)
    response = httpx.post(
        _token_endpoint(provider_key),
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    refreshed = response.json()
    # A refresh response usually omits refresh_token; keep the existing one.
    refreshed.setdefault("refresh_token", refresh)
    if refreshed.get("expires_in"):
        refreshed["expires_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=int(refreshed["expires_in"]))
        ).isoformat()

    from backend_v3.integrations.connection_store import get_connection

    existing = get_connection(provider_key)
    token_store.save_token(provider_key, (existing or {}).get("account") or "", refreshed)
    return refreshed


def revoke(provider_key: str) -> dict[str, Any]:
    """Revoke upstream where the provider supports it, then destroy the
    local credential regardless — a disconnect must not leave a usable
    token behind just because the remote call failed."""
    import httpx

    from backend_v3.integrations import token_store

    upstream = "not_supported"
    try:
        token = token_store.load_token(provider_key)
    except Exception:
        token = None

    if token and provider_key in REVOKE_ENDPOINTS:
        try:
            response = httpx.post(
                REVOKE_ENDPOINTS[provider_key],
                data={"token": token.get("access_token", "")},
                timeout=20.0,
            )
            upstream = "revoked" if response.status_code < 400 else f"failed_{response.status_code}"
        except Exception as exc:
            upstream = f"failed_{type(exc).__name__}"

    removed = token_store.revoke_token(provider_key)
    return {"upstream_revocation": upstream, "local_credentials_removed": removed}


def _fetch_account_label(provider_key: str, access_token: str) -> str:
    """Best-effort display label for the connected account."""
    if not access_token:
        return ""
    import httpx

    url = (
        "https://graph.microsoft.com/v1.0/me"
        if provider_key in _MICROSOFT_PROVIDERS
        else "https://www.googleapis.com/oauth2/v2/userinfo"
    )
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=20.0)
        response.raise_for_status()
        data = response.json()
        return data.get("mail") or data.get("userPrincipalName") or data.get("email") or ""
    except Exception:
        return ""

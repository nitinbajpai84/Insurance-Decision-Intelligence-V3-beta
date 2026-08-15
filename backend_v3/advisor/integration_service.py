"""
Integration Service boundary.

Stage 2 turns this from a static list into the Connection Center's data
source. Every row is the registry's declaration of a provider joined to
its *real* connection record — a provider reads "connected" only when
connection_store holds a record saying so.

Stage 1's list_connections() is kept intact so nothing that already
consumes it breaks.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


CONNECTION_CATEGORIES: list[dict[str, Any]] = [
    {"category": "Customer Data", "providers": ["CRM", "CSV/Excel"]},
    {"category": "Calendar", "providers": ["Google Calendar", "Microsoft Outlook"]},
    {"category": "Communication", "providers": ["Microsoft 365/Outlook", "Gmail", "WhatsApp Business"]},
    {"category": "Meetings", "providers": ["Microsoft Teams", "Zoom", "Google Meet"]},
    {"category": "Files", "providers": ["OneDrive", "SharePoint", "Google Drive"]},
]


def _connection_rows() -> dict[str, dict[str, Any]]:
    """Real connection state, or empty when the graph is unreachable —
    an outage must not make a provider look connected."""
    try:
        from backend_v3.integrations.connection_store import list_connections as stored

        return stored()
    except Exception:
        return {}


def list_connections() -> list[dict[str, Any]]:
    """Stage 1 shape: category -> providers with status/sync_status/last_sync."""
    from backend_v3.integrations.registry import PROVIDERS, CATEGORY_ORDER
    from backend_v3.integrations.connection_store import (
        STATUS_NOT_CONNECTED,
        SYNC_NOT_CONFIGURED,
    )

    stored = _connection_rows()
    grouped: dict[str, list[dict[str, Any]]] = {category: [] for category in CATEGORY_ORDER}

    for provider in PROVIDERS:
        record = stored.get(provider.key) or {}
        grouped.setdefault(provider.category, []).append(
            {
                "provider": provider.name,
                "provider_key": provider.key,
                "status": record.get("status") or STATUS_NOT_CONNECTED,
                "sync_status": record.get("sync_status") or SYNC_NOT_CONFIGURED,
                "last_sync": record.get("last_sync"),
            }
        )

    return [
        {"category": category, "providers": grouped[category]}
        for category in CATEGORY_ORDER
        if grouped.get(category)
    ]


def connection_center() -> list[dict[str, Any]]:
    """Full Connection Center rows: integration, status, account, last sync,
    data synchronized, and which actions are actually available."""
    from backend_v3.integrations.registry import PROVIDERS, CATEGORY_ORDER, describe
    from backend_v3.integrations.connection_store import STATUS_NOT_CONNECTED, SYNC_NOT_CONFIGURED
    from backend_v3.integrations.token_store import encryption_available

    stored = _connection_rows()
    encryption_ok = encryption_available()
    grouped: dict[str, list[dict[str, Any]]] = {}

    for provider in PROVIDERS:
        record = stored.get(provider.key) or {}
        info = describe(provider)
        connected = (record.get("status") or STATUS_NOT_CONNECTED) == "connected"

        blocked_reason = ""
        if provider.implementation == "architecture":
            blocked_reason = "Connector architecture defined; ingestion not implemented yet."
        elif info["missing_config"]:
            blocked_reason = f"Awaiting configuration: {', '.join(info['missing_config'])}."
        elif provider.auth == "oauth2" and not encryption_ok:
            blocked_reason = "Set INTEGRATION_ENCRYPTION_KEY before connecting an OAuth provider."

        grouped.setdefault(provider.category, []).append(
            {
                **info,
                "status": record.get("status") or STATUS_NOT_CONNECTED,
                "account": record.get("account") or None,
                "last_sync": record.get("last_sync"),
                "sync_status": record.get("sync_status") or SYNC_NOT_CONFIGURED,
                "data_synchronized": record.get("data_synchronized") or {},
                "last_error": record.get("last_error"),
                "connected": connected,
                "blocked_reason": blocked_reason,
                # Actions the UI may offer. `can_connect` already accounts
                # for implementation status and missing credentials.
                "actions": {
                    "connect": (not connected) and info["can_connect"] and not blocked_reason,
                    "disconnect": connected,
                    "sync_now": connected and provider.implementation != "architecture",
                    "upload": provider.auth == "file_upload",
                },
            }
        )

    return [
        {"category": category, "providers": grouped[category]}
        for category in CATEGORY_ORDER
        if grouped.get(category)
    ]


def start_connect(provider_key: str) -> dict[str, Any]:
    """Begin a connection.

    Most providers belong to an account (Google/Microsoft/Meta), so the
    caller is redirected to that account's flow rather than starting a
    second consent for the same credential.
    """
    from backend_v3.integrations.accounts import account_for_capability
    from backend_v3.integrations.registry import get_provider

    provider = get_provider(provider_key)

    if provider.auth == "file_upload":
        return {
            "provider": provider_key,
            "mode": "file_upload",
            "message": f"{provider.name} connects by uploading a file.",
        }

    if provider.implementation == "architecture":
        raise RuntimeError(
            f"{provider.name} has a defined connector contract but no ingestion implementation yet, "
            "so it cannot be connected."
        )

    account = account_for_capability(provider_key)
    if account is not None:
        return {
            "provider": provider_key,
            "mode": "account",
            "account": account.key,
            "message": f"{provider.name} is enabled by connecting your {account.name} account.",
        }

    if provider_key.startswith("crm_"):
        return {"provider": provider_key, "mode": "crm", "vendor": provider_key.replace("crm_", "", 1)}

    raise RuntimeError(f"{provider.name} has no connect flow.")


def disconnect_provider(provider_key: str) -> dict[str, Any]:
    """Drop a single capability's connection record.

    Credentials are owned by the account, so disconnecting one capability
    does not destroy a token its siblings still use — disconnecting the
    account does that.
    """
    from backend_v3.integrations.connection_store import disconnect
    from backend_v3.integrations.registry import get_provider

    get_provider(provider_key)
    disconnect(provider_key)

    if provider_key.startswith("crm_"):
        from backend_v3.integrations.token_store import revoke_token

        try:
            revoke_token(provider_key)
        except Exception:
            pass

    return {"provider": provider_key, "status": "not_connected"}


# provider key -> the function that actually pulls its data.
_SYNC_ROUTES: dict[str, str] = {
    "google_calendar": "calendar",
    "outlook_calendar": "calendar",
    "gmail": "gmail",
    "google_drive": "google_drive",
    "m365_email": "m365_email",
    "onedrive": "onedrive",
    "sharepoint": "sharepoint",
    "teams": "teams",
}


def sync_provider(provider_key: str) -> dict[str, Any]:
    """Run a real sync for providers that support one."""
    from backend_v3.integrations.registry import get_provider

    provider = get_provider(provider_key)
    route = _SYNC_ROUTES.get(provider_key)

    if route == "calendar":
        from backend_v3.integrations.calendar_sources import sync_calendar

        return sync_calendar(provider_key)
    if route == "gmail":
        from backend_v3.integrations.google_sources import sync_gmail

        return sync_gmail()
    if route == "google_drive":
        from backend_v3.integrations.google_sources import sync_google_drive

        return sync_google_drive()
    if route == "m365_email":
        from backend_v3.integrations.microsoft_sources import sync_m365_email

        return sync_m365_email()
    if route == "onedrive":
        from backend_v3.integrations.microsoft_sources import sync_onedrive

        return sync_onedrive()
    if route == "sharepoint":
        from backend_v3.integrations.microsoft_sources import sync_sharepoint

        return sync_sharepoint()
    if route == "teams":
        from backend_v3.integrations.microsoft_sources import sync_teams

        return sync_teams()

    if provider_key.startswith("crm_"):
        from backend_v3.integrations.crm_sources import sync_crm

        return sync_crm(provider_key)

    if provider.auth == "file_upload":
        raise RuntimeError(f"{provider.name} syncs by uploading a new file rather than on demand.")

    raise RuntimeError(
        f"{provider.name} has no ingestion implementation yet, so there is nothing to sync."
    )

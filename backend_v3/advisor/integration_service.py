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
    """Begin a connection. OAuth providers return an authorization URL;
    file providers are told to upload instead."""
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

    from backend_v3.integrations.oauth import build_authorization_url

    return {"provider": provider_key, "mode": "oauth2", **build_authorization_url(provider_key)}


def disconnect_provider(provider_key: str) -> dict[str, Any]:
    """Revoke credentials and drop the connection record together."""
    from backend_v3.integrations.connection_store import disconnect
    from backend_v3.integrations.registry import get_provider

    provider = get_provider(provider_key)
    revocation: dict[str, Any] = {"upstream_revocation": "not_applicable", "local_credentials_removed": False}

    if provider.auth == "oauth2":
        from backend_v3.integrations.oauth import revoke

        try:
            revocation = revoke(provider_key)
        except Exception as exc:
            revocation = {"upstream_revocation": f"failed_{type(exc).__name__}", "local_credentials_removed": False}

    disconnect(provider_key)
    return {"provider": provider_key, "status": "not_connected", **revocation}


def sync_provider(provider_key: str) -> dict[str, Any]:
    """Run a real sync for providers that support one."""
    from backend_v3.integrations.registry import get_provider

    provider = get_provider(provider_key)

    if provider_key in ("google_calendar", "outlook_calendar"):
        from backend_v3.integrations.calendar_sources import sync_calendar

        return sync_calendar(provider_key)

    if provider.auth == "file_upload":
        raise RuntimeError(f"{provider.name} syncs by uploading a new file rather than on demand.")

    raise RuntimeError(
        f"{provider.name} has no ingestion implementation yet, so there is nothing to sync."
    )

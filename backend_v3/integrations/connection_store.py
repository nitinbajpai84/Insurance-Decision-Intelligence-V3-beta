"""
Connection state for the Connection Center.

A provider is "connected" if and only if a Connection node exists for it
with status='connected'. That record is written by a real connect flow
(OAuth callback, or a completed file import), never by the UI asking
nicely and never inferred from the registry.

`data_synchronized` accumulates real counts from real syncs, so an
advisor can tell at a glance whether a connection has actually delivered
anything.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STATUS_CONNECTED = "connected"
STATUS_NOT_CONNECTED = "not_connected"
STATUS_ERROR = "error"

SYNC_NOT_CONFIGURED = "not_configured"
SYNC_NEVER_SYNCED = "never_synced"
SYNC_SYNCED = "synced"
SYNC_ERROR = "error"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection(provider: str) -> dict[str, Any] | None:
    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        "MATCH (c:Connection {provider: $provider}) "
        "RETURN c.provider AS provider, c.status AS status, c.account AS account, "
        "c.last_sync AS last_sync, c.sync_status AS sync_status, "
        "c.data_synchronized AS data_synchronized, c.connected_at AS connected_at, "
        "c.last_error AS last_error",
        {"provider": provider},
    )
    if not rows:
        return None
    row = dict(rows[0])
    row["data_synchronized"] = json.loads(row.get("data_synchronized") or "{}")
    return row


def list_connections() -> dict[str, dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        "MATCH (c:Connection) "
        "RETURN c.provider AS provider, c.status AS status, c.account AS account, "
        "c.last_sync AS last_sync, c.sync_status AS sync_status, "
        "c.data_synchronized AS data_synchronized, c.connected_at AS connected_at, "
        "c.last_error AS last_error",
        {},
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        record = dict(row)
        record["data_synchronized"] = json.loads(record.get("data_synchronized") or "{}")
        out[record["provider"]] = record
    return out


def mark_connected(provider: str, account: str, sync_status: str = SYNC_NEVER_SYNCED) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_write

    run_write(
        "MERGE (c:Connection {provider: $provider}) "
        "SET c.status = $status, c.account = $account, c.sync_status = $sync_status, "
        "    c.connected_at = coalesce(c.connected_at, $now), c.last_error = null, "
        "    c.data_synchronized = coalesce(c.data_synchronized, '{}')",
        {
            "provider": provider,
            "status": STATUS_CONNECTED,
            "account": account,
            "sync_status": sync_status,
            "now": _now(),
        },
    )
    from backend_v3.integrations.audit import audit

    audit("integration.connected", subject_id=provider, metadata={"account": account})
    return get_connection(provider) or {}


def record_sync(provider: str, counts: dict[str, int]) -> dict[str, Any]:
    """Record a completed sync.

    Counts describe the most recent sync rather than a running total.
    Writes are idempotent MERGEs, so re-importing the same file would make
    an accumulating total claim far more records than actually exist.
    """
    from backend_v3.graph_store.neo4j_client import run_write

    totals = {key: int(value) for key, value in counts.items()}

    run_write(
        "MERGE (c:Connection {provider: $provider}) "
        "SET c.last_sync = $now, c.sync_status = $sync_status, c.last_error = null, "
        "    c.data_synchronized = $totals, c.status = coalesce(c.status, $connected)",
        {
            "provider": provider,
            "now": _now(),
            "sync_status": SYNC_SYNCED,
            "totals": json.dumps(totals),
            "connected": STATUS_CONNECTED,
        },
    )
    from backend_v3.integrations.audit import audit

    audit("integration.synced", subject_id=provider, metadata={"counts": counts})
    return get_connection(provider) or {}


def record_error(provider: str, message: str) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_write

    run_write(
        "MERGE (c:Connection {provider: $provider}) "
        "SET c.sync_status = $sync_status, c.last_error = $message",
        {"provider": provider, "sync_status": SYNC_ERROR, "message": message[:500]},
    )
    from backend_v3.integrations.audit import audit

    audit("integration.sync_failed", subject_id=provider, metadata={"error": message[:500]})
    return get_connection(provider) or {}


def disconnect(provider: str) -> dict[str, Any]:
    """Remove the connection record. Credential destruction is the
    caller's job (integration_service.disconnect_provider) so that both
    always happen together."""
    from backend_v3.graph_store.neo4j_client import run_write

    run_write("MATCH (c:Connection {provider: $provider}) DETACH DELETE c", {"provider": provider})
    from backend_v3.integrations.audit import audit

    audit("integration.disconnected", subject_id=provider)
    return {"provider": provider, "status": STATUS_NOT_CONNECTED}

"""
Persisted audit log.

Stage 1's advisor/audit_service.py builds the event shape; this module is
what actually stores it, so connect/disconnect/sync/import/match events
survive a restart and can be shown back to the advisor.

Audit writes must never break the operation they describe — a failure to
log is reported through the returned record, not raised.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_ACTOR = "advisor"


def audit(event_type: str, subject_id: str, actor: str = DEFAULT_ACTOR, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend_v3.advisor.audit_service import audit_event

    event = audit_event(event_type, actor, subject_id, metadata)
    try:
        from backend_v3.graph_store.neo4j_client import run_write

        run_write(
            "CREATE (a:AuditEvent {event_type: $event_type, actor: $actor, subject_id: $subject_id, "
            "metadata: $metadata, created_at: $created_at})",
            {
                "event_type": event["event_type"],
                "actor": event["actor"],
                "subject_id": event["subject_id"],
                "metadata": json.dumps(event["metadata"]),
                "created_at": event["created_at"],
            },
        )
        event["persisted"] = True
    except Exception as exc:
        event["persisted"] = False
        event["persist_error"] = f"{type(exc).__name__}: {exc}"
    return event


def list_events(subject_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    cypher = (
        "MATCH (a:AuditEvent) "
        + ("WHERE a.subject_id = $subject_id " if subject_id else "")
        + "RETURN a.event_type AS event_type, a.actor AS actor, a.subject_id AS subject_id, "
        "a.metadata AS metadata, a.created_at AS created_at "
        "ORDER BY a.created_at DESC LIMIT $limit"
    )
    rows = run_query(cypher, {"subject_id": subject_id, "limit": limit})
    for row in rows:
        try:
            row["metadata"] = json.loads(row.get("metadata") or "{}")
        except (TypeError, ValueError):
            row["metadata"] = {}
    return rows

"""
Follow-up lifecycle — Stage 3.

memory_model.py already extracts memory_type="follow_up" items from a
conversation, but Milestone 2 never gave them anywhere to go: they were
PendingMemory-only, with no due date, no assignment, and no way to mark
one done. This module is that missing promotion target.

A follow-up still goes through the same approve/reject gate as every
other memory type — Gemini proposing a follow-up is not the same as it
existing. Approval promotes it into a real :FollowUp node the advisor can
then edit, assign, date, and complete.

This is deliberately a different lifecycle from agent_service's
deterministic "pending_followups" (stale-data / open-concern nudges
computed fresh on every request). A FollowUp here is a specific
commitment extracted from a specific conversation, with its own
provenance and its own completion state.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DUE_DAYS = 5  # a business-week-ish default; the advisor can change it


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_due_date() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=DEFAULT_DUE_DAYS)).date().isoformat()


def create_followup(
    customer_id: str,
    title: str,
    source: str,
    evidence: str | None = None,
    confidence: float = 1.0,
    due_date: str | None = None,
    assigned_to: str = "advisor",
) -> dict[str, Any]:
    """Promote an approved follow_up memory (or create one directly) into
    a real, actionable FollowUp node."""
    from backend_v3.graph_store.neo4j_client import run_write

    followup_id = str(uuid.uuid4())
    now = _now()
    run_write(
        "MATCH (c:Customer {customer_id: $customer_id}) "
        "CREATE (f:FollowUp {"
        "  followup_id: $followup_id, customer_id: $customer_id, title: $title, "
        "  evidence: $evidence, confidence: $confidence, due_date: $due_date, "
        "  assigned_to: $assigned_to, status: 'open', "
        "  source: $source, created_at: $now, completed_at: null"
        "}) "
        "MERGE (c)-[r:HAS_FOLLOWUP]->(f) "
        "SET r.source = $source, r.confidence = $confidence, r.created_at = $now",
        {
            "customer_id": customer_id,
            "followup_id": followup_id,
            "title": title,
            "evidence": evidence,
            "confidence": confidence,
            "due_date": due_date or _default_due_date(),
            "assigned_to": assigned_to,
            "source": source,
            "now": now,
        },
    )
    return get_followup(followup_id)


def get_followup(followup_id: str) -> dict[str, Any] | None:
    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        "MATCH (c:Customer)-[:HAS_FOLLOWUP]->(f:FollowUp {followup_id: $followup_id}) "
        "RETURN f.followup_id AS followup_id, f.customer_id AS customer_id, c.name AS customer_name, "
        "f.title AS title, f.evidence AS evidence, f.confidence AS confidence, "
        "f.due_date AS due_date, f.assigned_to AS assigned_to, f.status AS status, "
        "f.source AS source, f.created_at AS created_at, f.completed_at AS completed_at",
        {"followup_id": followup_id},
    )
    return rows[0] if rows else None


def list_followups(
    customer_id: str | None = None,
    status: str | None = None,
    overdue_only: bool = False,
) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    today = datetime.now(timezone.utc).date().isoformat()
    clauses = []
    params: dict[str, Any] = {"today": today}

    if customer_id:
        clauses.append("f.customer_id = $customer_id")
        params["customer_id"] = customer_id
    if status:
        clauses.append("f.status = $status")
        params["status"] = status
    if overdue_only:
        clauses.append("f.status = 'open' AND f.due_date < $today")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = run_query(
        "MATCH (c:Customer)-[:HAS_FOLLOWUP]->(f:FollowUp) "
        f"{where} "
        "RETURN f.followup_id AS followup_id, f.customer_id AS customer_id, c.name AS customer_name, "
        "f.title AS title, f.evidence AS evidence, f.confidence AS confidence, "
        "f.due_date AS due_date, f.assigned_to AS assigned_to, f.status AS status, "
        "f.source AS source, f.created_at AS created_at, f.completed_at AS completed_at "
        "ORDER BY f.due_date ASC",
        params,
    )
    return rows


def update_followup(
    followup_id: str,
    title: str | None = None,
    due_date: str | None = None,
    assigned_to: str | None = None,
) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_write

    existing = get_followup(followup_id)
    if existing is None:
        raise ValueError(f"Follow-up {followup_id} not found")

    run_write(
        "MATCH (f:FollowUp {followup_id: $followup_id}) "
        "SET f.title = coalesce($title, f.title), "
        "    f.due_date = coalesce($due_date, f.due_date), "
        "    f.assigned_to = coalesce($assigned_to, f.assigned_to)",
        {"followup_id": followup_id, "title": title, "due_date": due_date, "assigned_to": assigned_to},
    )
    return get_followup(followup_id)


def complete_followup(followup_id: str) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_write

    if get_followup(followup_id) is None:
        raise ValueError(f"Follow-up {followup_id} not found")

    run_write(
        "MATCH (f:FollowUp {followup_id: $followup_id}) SET f.status = 'completed', f.completed_at = $now",
        {"followup_id": followup_id, "now": _now()},
    )
    return get_followup(followup_id)


def reopen_followup(followup_id: str) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_write

    if get_followup(followup_id) is None:
        raise ValueError(f"Follow-up {followup_id} not found")

    run_write(
        "MATCH (f:FollowUp {followup_id: $followup_id}) SET f.status = 'open', f.completed_at = null",
        {"followup_id": followup_id},
    )
    return get_followup(followup_id)

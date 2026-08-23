"""
Append-only underwriting decision log.

This is the Event Store from the Intelligence Warehouse architecture, pointed
at risk decisions. Nothing here updates; every state change is a new event, so
the sequence for an application reconstructs exactly how a decision was reached
-- what the model scored, which rule versions fired, whether it went straight
through or to a human, and whether a human overrode it.

Model governance and regulatory defensibility both reduce to being able to
answer "why was this accepted, on what basis, under whose authority" years
later. That answer lives here.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from backend_v3.structured_store.duckdb_client import get_connection

# Ordered by where they fall in a decision's life, not alphabetically.
EVENT_TYPES = (
    "scored",
    "auto_approved",
    "referred",
    "underwriter_decision",
    "overridden",
)

_SELECT = """
select log_id, application_id, event_seq, event_type, decided_at, decision,
       risk_score, rules_fired, actor, actor_type, is_override, override_reason
from uw_decision_log
"""


def _row_to_event(row: tuple) -> dict[str, Any]:
    rules = row[7]
    if isinstance(rules, str):
        try:
            rules = json.loads(rules)
        except (ValueError, TypeError):
            rules = []
    return {
        "log_id": row[0],
        "application_id": row[1],
        "event_seq": row[2],
        "event_type": row[3],
        "decided_at": row[4].isoformat() if row[4] else None,
        "decision": row[5],
        "risk_score": row[6],
        "rules_fired": rules or [],
        "actor": row[8],
        "actor_type": row[9],
        "is_override": bool(row[10]) if row[10] is not None else False,
        "override_reason": row[11],
    }


def decision_trail(application_id: str) -> list[dict[str, Any]]:
    """Every event for one application, in the order it happened."""
    con = get_connection()
    try:
        rows = con.execute(
            _SELECT + " where application_id = ? order by event_seq", [application_id]
        ).fetchall()
        return [_row_to_event(r) for r in rows]
    finally:
        con.close()


def append_event(
    application_id: str,
    event_type: str,
    *,
    decision: str | None = None,
    risk_score: float | None = None,
    rules_fired: list[str] | None = None,
    actor: str = "risk_engine",
    actor_type: str = "system",
    is_override: bool = False,
    override_reason: str | None = None,
) -> dict[str, Any]:
    """
    Append one event to an application's trail.

    `event_seq` is derived from what is already recorded rather than passed in,
    so callers cannot accidentally reorder or overwrite history.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type {event_type!r}; expected one of {EVENT_TYPES}")
    if is_override and not override_reason:
        raise ValueError("an override must carry a reason -- that is the point of recording it")

    now = datetime.now(timezone.utc)
    con = get_connection(read_only=False)
    try:
        next_seq = (
            con.execute(
                "select coalesce(max(event_seq), 0) + 1 from uw_decision_log where application_id = ?",
                [application_id],
            ).fetchone()[0]
        )
        log_id = f"log_{uuid.uuid4().hex[:16]}"
        con.execute(
            "insert into uw_decision_log values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                log_id, application_id, next_seq, event_type, now, decision, risk_score,
                json.dumps(rules_fired or []), actor, actor_type, is_override,
                override_reason, now,
            ],
        )
        con.commit()
    finally:
        con.close()

    return {
        "log_id": log_id,
        "application_id": application_id,
        "event_seq": next_seq,
        "event_type": event_type,
        "decided_at": now.isoformat(),
        "decision": decision,
        "risk_score": risk_score,
        "rules_fired": rules_fired or [],
        "actor": actor,
        "actor_type": actor_type,
        "is_override": is_override,
        "override_reason": override_reason,
    }


def override_stats() -> dict[str, Any]:
    """
    How often underwriters disagree with the machine.

    A straight-through rate with no override rate beside it is not a governance
    metric -- it just says how often nobody looked.
    """
    con = get_connection()
    try:
        row = con.execute(
            """
            select
              count(*) filter (where event_type = 'auto_approved')        as auto_approved,
              count(*) filter (where event_type = 'referred')             as referred,
              count(*) filter (where event_type = 'underwriter_decision') as underwriter_decisions,
              count(*) filter (where is_override)                         as overrides,
              count(distinct application_id)                              as applications
            from uw_decision_log
            """
        ).fetchone()
        auto, referred, uw_dec, overrides, apps = row
        return {
            "applications": apps,
            "auto_approved": auto,
            "referred": referred,
            "underwriter_decisions": uw_dec,
            "overrides": overrides,
            "straight_through_rate": round(auto / apps, 4) if apps else None,
            "override_rate": round(overrides / uw_dec, 4) if uw_dec else None,
        }
    finally:
        con.close()

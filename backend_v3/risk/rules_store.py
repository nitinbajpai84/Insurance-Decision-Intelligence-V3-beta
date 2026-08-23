"""
Versioned underwriting rules store.

A rule is not a row that gets edited in place -- it is a series of versions,
each with the window it was in force. That distinction is the whole point: an
underwriting decision made in March 2024 has to be explainable against the rule
text that applied in March 2024, not against whatever the rule says today.

This is the Rules & Logic Store from the Intelligence Warehouse architecture,
and the reinsurance analogue of a configurable underwriting rules engine.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from backend_v3.structured_store.duckdb_client import get_connection

_SELECT = """
select rule_id, rule_key, version, name, description, condition_json,
       action, effective_from, effective_to, status
from uw_rules
"""


def _row_to_rule(row: tuple) -> dict[str, Any]:
    condition = row[5]
    if isinstance(condition, str):
        try:
            condition = json.loads(condition)
        except (ValueError, TypeError):
            pass
    return {
        "rule_id": row[0],
        "rule_key": row[1],
        "version": row[2],
        "name": row[3],
        "description": row[4],
        "condition": condition,
        "action": row[6],
        "effective_from": row[7].isoformat() if row[7] else None,
        "effective_to": row[8].isoformat() if row[8] else None,
        "status": row[9],
    }


def list_rules(active_only: bool = False) -> list[dict[str, Any]]:
    """Every rule version, newest key/version first."""
    sql = _SELECT + (" where status = 'active'" if active_only else "")
    sql += " order by rule_key, version desc"
    con = get_connection()
    try:
        return [_row_to_rule(r) for r in con.execute(sql).fetchall()]
    finally:
        con.close()


def rule_in_force(rule_key: str, on: date) -> dict[str, Any] | None:
    """
    The version of `rule_key` that governed decisions on a given date.

    `effective_to IS NULL` means still in force, so it is treated as an open
    upper bound rather than excluded.
    """
    con = get_connection()
    try:
        row = con.execute(
            _SELECT + """
            where rule_key = ?
              and effective_from <= ?
              and (effective_to is null or effective_to >= ?)
            order by version desc limit 1
            """,
            [rule_key, on, on],
        ).fetchone()
        return _row_to_rule(row) if row else None
    finally:
        con.close()


def rule_versions(rule_key: str) -> list[dict[str, Any]]:
    """Full version history for one rule key, oldest first."""
    con = get_connection()
    try:
        rows = con.execute(
            _SELECT + " where rule_key = ? order by version", [rule_key]
        ).fetchall()
        return [_row_to_rule(r) for r in rows]
    finally:
        con.close()


def get_rule(rule_id: str) -> dict[str, Any] | None:
    con = get_connection()
    try:
        row = con.execute(_SELECT + " where rule_id = ?", [rule_id]).fetchone()
        return _row_to_rule(row) if row else None
    finally:
        con.close()

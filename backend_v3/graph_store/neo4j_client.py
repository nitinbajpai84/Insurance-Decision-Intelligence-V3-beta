"""
Thin Neo4j driver wrapper — the ONLY module that imports the neo4j SDK
directly (see docs/ARCHITECTURE.md's "client wrapper convention"). Every
other module calls run_query()/run_write() instead of touching the driver.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.config import require_neo4j

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        from neo4j import GraphDatabase

        uri, user, password = require_neo4j()
        _driver = GraphDatabase.driver(uri, auth=(user, password))
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def run_query(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Read query — runs in a read transaction, returns a list of row dicts."""
    from backend_v3.config import NEO4J_DATABASE

    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(cypher, params or {})
        return [dict(record) for record in result]


def run_write(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Write query (MERGE/CREATE/SET/DELETE) — runs in a write transaction."""
    from backend_v3.config import NEO4J_DATABASE

    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.execute_write(lambda tx: list(tx.run(cypher, params or {})))
        return [dict(record) for record in result]


def health_check() -> dict[str, Any]:
    try:
        rows = run_query("RETURN 1 AS ok")
        node_count = run_query("MATCH (n) RETURN count(n) AS c")[0]["c"]
        return {"status": "ok", "node_count": node_count}
    except Exception as exc:
        return {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}

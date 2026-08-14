"""
Insurance PoC V2.0 — reusable DuckDB connection module.

Resolution order for the database path (DUCKDB_PATH):
  1. OS environment variable DUCKDB_PATH
  2. database\\.env  (DUCKDB_PATH=...)
  3. project-root .env (DUCKDB_PATH=...)
  4. default: database\\insurance_v2.duckdb

Usage:
    from database.db_connection import read_connection, execute_query, health_check

    rows, cols = execute_query("SELECT count(*) AS n FROM policies")
    schema = get_table_schema("policies")
    catalog = get_all_tables()
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import duckdb

_PROJECT_ROOT_FOR_IMPORT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT_FOR_IMPORT))

# Single source of truth for DuckDB config — see backend_v2/config.py's
# DUCKDB_CONFIG docstring for why every connect() call in the app must use
# the exact same dict (DuckDB caches one instance per file per process,
# keyed by configuration; mismatched configs raise ConnectionException).
from backend_v2.config import DUCKDB_CONFIG as _DUCKDB_CONFIG

logger = logging.getLogger("insurance_v2.db")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(os.environ.get("DB_LOG_LEVEL", "INFO").upper())

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_DB_PATH = SCRIPT_DIR / "insurance_v2.duckdb"


def _read_env_file(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    except OSError:
        return None
    return None


def get_duckdb_path() -> str:
    """Resolve DUCKDB_PATH (env var -> database\\.env -> root .env -> default)."""
    value = os.environ.get("DUCKDB_PATH", "").strip()
    if value:
        return value
    for env_file in (SCRIPT_DIR / ".env", PROJECT_ROOT / ".env"):
        found = _read_env_file(env_file, "DUCKDB_PATH")
        if found:
            return found
    return str(DEFAULT_DB_PATH)


def read_connection() -> duckdb.DuckDBPyConnection:
    """Read-only connection — safe for the SQL agent / analytics paths."""
    path = get_duckdb_path()
    logger.debug("Opening read-only connection: %s", path)
    return duckdb.connect(path, read_only=True, config=_DUCKDB_CONFIG)


def write_connection() -> duckdb.DuckDBPyConnection:
    """Read-write connection — for seeding, logging, and cache writes.

    Note: DuckDB allows one writer at a time; keep write connections short-lived.
    """
    path = get_duckdb_path()
    logger.debug("Opening write connection: %s", path)
    return duckdb.connect(path, read_only=False, config=_DUCKDB_CONFIG)


def execute_query(
    sql: str,
    params: list[Any] | tuple[Any, ...] | None = None,
    *,
    read_only: bool = True,
) -> tuple[list[tuple], list[str]]:
    """Execute SQL and return (rows, column_names) with logging + error handling.

    Raises RuntimeError with a concise message on failure (original exception chained).
    """
    started = time.perf_counter()
    conn = read_connection() if read_only else write_connection()
    try:
        cursor = conn.execute(sql, params or [])
        columns = [d[0] for d in (cursor.description or [])]
        rows = cursor.fetchall() if columns else []
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info("Query OK rows=%d cols=%d duration_ms=%d", len(rows), len(columns), elapsed_ms)
        return rows, columns
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error("Query FAILED duration_ms=%d error=%s sql=%s", elapsed_ms, exc, sql[:300])
        raise RuntimeError(f"DuckDB query failed: {type(exc).__name__}: {exc}") from exc
    finally:
        conn.close()


def health_check() -> dict[str, Any]:
    """Connectivity + basic catalog health. Never raises."""
    path = get_duckdb_path()
    result: dict[str, Any] = {"status": "ok", "duckdb_path": path, "exists": Path(path).exists()}
    try:
        started = time.perf_counter()
        conn = duckdb.connect(path, read_only=True, config=_DUCKDB_CONFIG)
        try:
            conn.execute("SELECT 1").fetchone()
            result["table_count"] = conn.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchone()[0]
            result["duckdb_version"] = conn.execute("SELECT version()").fetchone()[0]
        finally:
            conn.close()
        result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def get_table_schema(table_name: str) -> list[dict[str, Any]]:
    """Columns + types for one table — consumed by the SQL agent.

    Returns [] if the table does not exist (no exception), so callers can
    treat an unknown table as 'no schema' rather than a hard failure.
    """
    sql = (
        "SELECT column_name, data_type, is_nullable "
        "FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? "
        "ORDER BY ordinal_position"
    )
    try:
        rows, _ = execute_query(sql, [table_name])
    except RuntimeError:
        return []
    return [
        {"column_name": r[0], "data_type": r[1], "nullable": r[2] == "YES"}
        for r in rows
    ]


def get_all_tables() -> dict[str, list[dict[str, Any]]]:
    """Full schema catalog {table_name: [column dicts]} for LLM context building."""
    sql = (
        "SELECT table_name, column_name, data_type, is_nullable "
        "FROM information_schema.columns "
        "WHERE table_schema = 'main' "
        "ORDER BY table_name, ordinal_position"
    )
    rows, _ = execute_query(sql)
    catalog: dict[str, list[dict[str, Any]]] = {}
    for table_name, column_name, data_type, is_nullable in rows:
        catalog.setdefault(table_name, []).append(
            {"column_name": column_name, "data_type": data_type, "nullable": is_nullable == "YES"}
        )
    return catalog


if __name__ == "__main__":
    import json

    print(json.dumps(health_check(), indent=2))

"""
Thin DuckDB connection helper for V3's structured business data (policies,
customers, claims) — unchanged from V2's role, per docs/ARCHITECTURE.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import duckdb

from backend_v3.config import DUCKDB_CONFIG, DUCKDB_PATH


def get_connection(read_only: bool = True):
    return duckdb.connect(DUCKDB_PATH, read_only=read_only, config=DUCKDB_CONFIG)

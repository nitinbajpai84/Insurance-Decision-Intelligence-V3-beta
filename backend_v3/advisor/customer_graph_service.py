"""
Customer Graph Service boundary.

Neo4j represents customer relationships and approved customer truth: family,
goals, needs, life events, concerns, meetings, and owned policy links. This
boundary gives higher-level services a named place to depend on graph facts.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_customer_relationships(customer_id: str) -> dict[str, Any] | None:
    from backend_v3.advisor.retrieval import get_customer_graph

    return get_customer_graph(customer_id)


def list_customer_relationship_summaries() -> list[dict[str, Any]]:
    from backend_v3.advisor.retrieval import list_customers

    return list_customers()

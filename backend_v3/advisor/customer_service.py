"""
Customer Service boundary for the advisor product.

This module owns customer-facing application shapes. It deliberately delegates
relationship traversal to retrieval/customer_graph_service and prioritization to
prioritization.py so the API routes stay thin.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def list_customer_summaries() -> list[dict[str, Any]]:
    from backend_v3.advisor.prioritization import compute_priority
    from backend_v3.advisor.retrieval import list_customers as _list

    out = []
    for row in _list():
        life_events = [e for e in row["life_events"] if e.get("description")]
        concerns = [c for c in row["concerns"] if c.get("topic")]
        meetings = [m for m in row["meetings"] if m.get("date")]
        out.append({
            "customer_id": row["customer_id"],
            "name": row["name"],
            "life_stage": row["life_stage"],
            **compute_priority(life_events, concerns, meetings),
        })

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda c: priority_rank.get(c["priority"], 3))
    return out


def get_customer_360(customer_id: str) -> dict[str, Any] | None:
    from backend_v3.advisor.prioritization import compute_priority
    from backend_v3.advisor.retrieval import assemble_customer_context

    ctx = assemble_customer_context(customer_id)
    if ctx is None:
        return None
    priority_info = compute_priority(ctx["life_events"], ctx["concerns"], ctx["meetings"])
    return {**ctx, **priority_info}

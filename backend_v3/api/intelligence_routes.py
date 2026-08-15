"""
Stage 4 API: transparent priority, Next Best Action, knowledge
coverage/freshness, Insights, per-customer knowledge graph, KPI
dashboard, and AI auditability.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# main.py mounts this under /api/v3.
router = APIRouter(prefix="/advisor", tags=["intelligence"])


class DecideActionIn(BaseModel):
    accept: bool
    due_date: str | None = None


@router.get("/customers/{customer_id}/priority")
def customer_priority(customer_id: str) -> dict[str, Any]:
    from backend_v3.advisor.priority_service import score_customer

    result = score_customer(customer_id)
    if result is None:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return result


@router.get("/priority")
def all_priority() -> list[dict[str, Any]]:
    from backend_v3.advisor.priority_service import score_all_customers

    try:
        return score_all_customers()
    except Exception as exc:
        raise HTTPException(503, f"Could not compute priority: {type(exc).__name__}: {exc}")


@router.post("/customers/{customer_id}/next-best-actions")
def generate_actions(customer_id: str) -> dict[str, Any]:
    from backend_v3.advisor.next_best_action import generate_next_best_actions

    try:
        result = generate_next_best_actions(customer_id)
    except Exception as exc:
        raise HTTPException(503, f"Could not generate actions: {type(exc).__name__}: {exc}")
    if result is None:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return result


@router.get("/customers/{customer_id}/next-best-actions")
def list_actions(customer_id: str, status: str | None = None) -> list[dict[str, Any]]:
    from backend_v3.advisor.next_best_action import list_actions as _list

    try:
        return _list(customer_id, status=status)
    except Exception as exc:
        raise HTTPException(503, f"Could not list actions: {type(exc).__name__}: {exc}")


@router.post("/next-best-actions/{proposal_id}/decide")
def decide_action(proposal_id: str, body: DecideActionIn) -> dict[str, Any]:
    from backend_v3.advisor.next_best_action import decide_action as _decide

    try:
        return _decide(proposal_id, accept=body.accept, due_date=body.due_date)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(503, f"Could not record decision: {type(exc).__name__}: {exc}")


@router.get("/customers/{customer_id}/knowledge-coverage")
def knowledge_coverage(customer_id: str) -> dict[str, Any]:
    from backend_v3.advisor.knowledge_coverage import compute_coverage

    result = compute_coverage(customer_id)
    if result is None:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return result


@router.get("/customers/{customer_id}/memory-freshness")
def memory_freshness(customer_id: str) -> dict[str, Any]:
    from backend_v3.advisor.knowledge_coverage import compute_freshness

    result = compute_freshness(customer_id)
    if result is None:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return result


@router.get("/customers/{customer_id}/knowledge-graph")
def knowledge_graph(customer_id: str) -> dict[str, Any]:
    from backend_v3.advisor.customer_knowledge_graph import get_customer_knowledge_graph

    result = get_customer_knowledge_graph(customer_id)
    if result is None:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return result


@router.get("/insights")
def insights() -> dict[str, Any]:
    from backend_v3.advisor.insights_service import get_insights

    try:
        return get_insights()
    except Exception as exc:
        raise HTTPException(503, f"Could not build insights: {type(exc).__name__}: {exc}")


@router.get("/kpis")
def kpis() -> dict[str, Any]:
    from backend_v3.advisor.kpi_service import get_kpi_dashboard

    try:
        return get_kpi_dashboard()
    except Exception as exc:
        raise HTTPException(503, f"Could not compute KPIs: {type(exc).__name__}: {exc}")


@router.get("/ai-audit")
def ai_audit(customer_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    from backend_v3.advisor.ai_audit import list_ai_audit_trail

    try:
        return list_ai_audit_trail(customer_id=customer_id, limit=min(limit, 500))
    except Exception as exc:
        raise HTTPException(503, f"Could not read audit trail: {type(exc).__name__}: {exc}")

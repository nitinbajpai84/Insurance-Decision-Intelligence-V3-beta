"""
Advisor Customer Intelligence API — Milestone 1 (Know My Customer):
Agent Home, Customer List, Customer 360, Prepare for Meeting.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.get("/customers")
def list_customers():
    """Agent Home + Customer List: every customer with a computed priority
    signal (real, derived from life events/concerns/last-contact — not an
    AI guess) so the advisor can see who needs attention first."""
    from backend_v3.advisor.prioritization import compute_priority
    from backend_v3.advisor.retrieval import list_customers as _list

    try:
        rows = _list()
    except Exception as exc:
        raise HTTPException(503, f"Could not reach the customer graph: {type(exc).__name__}: {exc}")

    out = []
    for r in rows:
        life_events = [e for e in r["life_events"] if e.get("description")]
        concerns = [c for c in r["concerns"] if c.get("topic")]
        meetings = [m for m in r["meetings"] if m.get("date")]
        priority_info = compute_priority(life_events, concerns, meetings)
        out.append({
            "customer_id": r["customer_id"],
            "name": r["name"],
            "life_stage": r["life_stage"],
            **priority_info,
        })
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda c: priority_rank.get(c["priority"], 3))
    return out


@router.get("/customers/{customer_id}")
def get_customer_360(customer_id: str):
    """Customer 360: full grounded profile — no Gemini call, this is pure
    retrieval so it's instant and always available even if Gemini is down."""
    from backend_v3.advisor.prioritization import compute_priority
    from backend_v3.advisor.retrieval import assemble_customer_context

    try:
        ctx = assemble_customer_context(customer_id)
    except Exception as exc:
        raise HTTPException(503, f"Could not reach customer data: {type(exc).__name__}: {exc}")
    if ctx is None:
        raise HTTPException(404, f"Customer {customer_id} not found")

    priority_info = compute_priority(ctx["life_events"], ctx["concerns"], ctx["meetings"])
    return {**ctx, **priority_info}


@router.post("/customers/{customer_id}/briefing")
def prepare_meeting(customer_id: str):
    """The hero action: 'Prepare for Meeting'. Retrieves Neo4j + Qdrant +
    DuckDB context, then Gemini reasons over it into a structured brief."""
    from backend_v3.advisor.briefing_service import prepare_meeting_briefing

    try:
        briefing = prepare_meeting_briefing(customer_id)
    except Exception as exc:
        raise HTTPException(503, f"Meeting preparation failed: {type(exc).__name__}: {exc}")
    if briefing is None:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return briefing

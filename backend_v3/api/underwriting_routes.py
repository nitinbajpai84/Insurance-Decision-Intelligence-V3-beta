"""
Underwriting endpoints (U1).

The queue, one case with its recommendation and rule trace, the underwriter's
decision, and the versioned rule store behind all of it.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.risk import decision_log, underwriting_service as uw
from backend_v3.risk.rules_store import list_rules, rule_versions

router = APIRouter(tags=["underwriting"], prefix="/underwriting")


class DecisionRequest(BaseModel):
    decision: str = Field(..., description="One of approved_standard, approved_rated, approved_exclusion, postponed, declined")
    actor: str = Field("underwriter", description="Who is recording the decision")
    reason: str | None = Field(None, description="Required when contradicting the recommendation")


@router.get("/queue")
def get_queue(
    awaiting_only: bool = Query(True, description="Only cases still needing an underwriter"),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    return {
        "summary": uw.queue_summary(),
        "cases": uw.list_cases(status=status, awaiting_only=awaiting_only, limit=limit),
    }


@router.get("/cases/{application_id}")
def get_case(application_id: str):
    case = uw.get_case(application_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"No such application: {application_id}")
    return case


@router.post("/cases/{application_id}/decision")
def post_decision(application_id: str, body: DecisionRequest):
    try:
        return uw.record_decision(
            application_id, body.decision, actor=body.actor, reason=body.reason
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        # Covers both an unknown decision and an unexplained override -- both are
        # the caller sending something the domain refuses, not a server fault.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/rules")
def get_rules(active_only: bool = Query(False)):
    return {"rules": list_rules(active_only=active_only)}


@router.get("/rules/{rule_key}/versions")
def get_rule_versions(rule_key: str):
    versions = rule_versions(rule_key)
    if not versions:
        raise HTTPException(status_code=404, detail=f"No such rule key: {rule_key}")
    return {"rule_key": rule_key, "versions": versions}


@router.get("/governance")
def get_governance():
    """Straight-through and override rates -- the pair, never one alone."""
    return decision_log.override_stats()

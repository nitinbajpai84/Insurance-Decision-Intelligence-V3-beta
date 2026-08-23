"""
Claims-to-underwriting feedback loop endpoints (C3).

Every payload carries the method, because the measure here is exposure-matched
incidence and a reader who assumes it is a raw percentage will misread it.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Query

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.risk import feedback_loop as loop

router = APIRouter(tags=["feedback-loop"], prefix="/feedback-loop")


@router.get("/report")
def get_report():
    return loop.loop_report()


@router.get("/cases")
def get_cases(limit: int = Query(25, ge=1, le=200)):
    return {"method": loop.method(), "cases": loop.cases_behind_the_leak(limit=limit)}

"""
Advisor Customer Intelligence API.

Stage 1 keeps the original customer and briefing endpoints stable while adding
advisor SaaS surfaces for My Day, Tasks, Connections, and onboarding results.
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
    from backend_v3.advisor.customer_service import list_customer_summaries

    try:
        return list_customer_summaries()
    except Exception as exc:
        raise HTTPException(503, f"Could not reach the customer graph: {type(exc).__name__}: {exc}")


@router.get("/customers/{customer_id}")
def get_customer_360(customer_id: str):
    from backend_v3.advisor.customer_service import get_customer_360 as _get_customer_360

    try:
        ctx = _get_customer_360(customer_id)
    except Exception as exc:
        raise HTTPException(503, f"Could not reach customer data: {type(exc).__name__}: {exc}")
    if ctx is None:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return ctx


@router.post("/customers/{customer_id}/briefing")
def prepare_meeting(customer_id: str):
    from backend_v3.advisor.briefing_service import prepare_meeting_briefing

    try:
        briefing = prepare_meeting_briefing(customer_id)
    except Exception as exc:
        raise HTTPException(503, f"Meeting preparation failed: {type(exc).__name__}: {exc}")
    if briefing is None:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return briefing


@router.get("/my-day")
def my_day():
    from backend_v3.advisor.agent_service import get_my_day

    try:
        return get_my_day()
    except Exception as exc:
        raise HTTPException(503, f"Could not build My Day: {type(exc).__name__}: {exc}")


@router.get("/tasks")
def tasks():
    from backend_v3.advisor.agent_service import list_tasks

    try:
        return list_tasks()
    except Exception as exc:
        raise HTTPException(503, f"Could not build task list: {type(exc).__name__}: {exc}")


@router.get("/connections")
def connections():
    from backend_v3.advisor.integration_service import list_connections

    return list_connections()


@router.get("/meetings/today")
def meetings_today():
    """Today's calendar meetings plus the customer-meeting count line."""
    from backend_v3.advisor.meeting_service import today_summary

    try:
        return today_summary()
    except Exception as exc:
        raise HTTPException(503, f"Could not read today's meetings: {type(exc).__name__}: {exc}")


@router.get("/meetings/unmatched")
def meetings_unmatched():
    """Meetings whose attendees did not resolve to a customer."""
    from backend_v3.advisor.meeting_service import list_unmatched_meetings

    try:
        return list_unmatched_meetings()
    except Exception as exc:
        raise HTTPException(503, f"Could not read unmatched meetings: {type(exc).__name__}: {exc}")


@router.get("/onboarding/result")
def onboarding_result():
    from backend_v3.advisor.agent_service import get_onboarding_result

    try:
        return get_onboarding_result()
    except Exception as exc:
        raise HTTPException(503, f"Could not build onboarding result: {type(exc).__name__}: {exc}")

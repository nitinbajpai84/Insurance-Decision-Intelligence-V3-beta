"""
Follow-up lifecycle API — Stage 3.
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
router = APIRouter(prefix="/advisor", tags=["follow-ups"])


class FollowUpUpdate(BaseModel):
    title: str | None = None
    due_date: str | None = None
    assigned_to: str | None = None


@router.get("/follow-ups")
def list_followups(status: str | None = None, overdue: bool = False) -> list[dict[str, Any]]:
    from backend_v3.advisor.followups import list_followups as _list

    try:
        return _list(status=status, overdue_only=overdue)
    except Exception as exc:
        raise HTTPException(503, f"Could not reach follow-ups: {type(exc).__name__}: {exc}")


@router.get("/customers/{customer_id}/follow-ups")
def list_customer_followups(customer_id: str) -> list[dict[str, Any]]:
    from backend_v3.advisor.followups import list_followups as _list

    try:
        return _list(customer_id=customer_id)
    except Exception as exc:
        raise HTTPException(503, f"Could not reach follow-ups: {type(exc).__name__}: {exc}")


@router.patch("/follow-ups/{followup_id}")
def update_followup(followup_id: str, body: FollowUpUpdate) -> dict[str, Any]:
    from backend_v3.advisor.followups import update_followup as _update

    try:
        return _update(followup_id, title=body.title, due_date=body.due_date, assigned_to=body.assigned_to)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(503, f"Update failed: {type(exc).__name__}: {exc}")


@router.post("/follow-ups/{followup_id}/complete")
def complete_followup(followup_id: str) -> dict[str, Any]:
    from backend_v3.advisor.followups import complete_followup as _complete

    try:
        return _complete(followup_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(503, f"Completion failed: {type(exc).__name__}: {exc}")


@router.post("/follow-ups/{followup_id}/reopen")
def reopen_followup(followup_id: str) -> dict[str, Any]:
    from backend_v3.advisor.followups import reopen_followup as _reopen

    try:
        return _reopen(followup_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(503, f"Reopen failed: {type(exc).__name__}: {exc}")

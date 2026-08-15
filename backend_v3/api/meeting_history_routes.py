"""
Meeting History API — Stage 3.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# main.py mounts this under /api/v3.
router = APIRouter(prefix="/advisor", tags=["meeting-history"])


@router.get("/customers/{customer_id}/meeting-history")
def meeting_history(customer_id: str) -> list[dict[str, Any]]:
    from backend_v3.advisor.meeting_history import get_meeting_history

    try:
        return get_meeting_history(customer_id)
    except Exception as exc:
        raise HTTPException(503, f"Could not build meeting history: {type(exc).__name__}: {exc}")

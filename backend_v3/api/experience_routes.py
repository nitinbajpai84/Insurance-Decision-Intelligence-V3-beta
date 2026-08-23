"""
Experience monitoring endpoints (P1).

Every response carries the expected basis, because an A/E figure without its
denominator stated is not interpretable.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.risk import experience_service as exp

router = APIRouter(tags=["experience"], prefix="/experience")


@router.get("/basis")
def get_basis():
    """What "expected" means, and what it cannot tell you."""
    return exp.basis()


@router.get("/overview")
def get_overview():
    return exp.experience_overview()


@router.get("/by/{dimension}")
def get_by_dimension(dimension: str):
    try:
        return exp.experience_by(dimension)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

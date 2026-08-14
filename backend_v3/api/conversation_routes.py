"""
Conversation capture + memory approval endpoints — Milestone 2.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

router = APIRouter(prefix="/advisor", tags=["advisor-memory"])


class TranscriptIn(BaseModel):
    transcript: str


class ApproveIn(BaseModel):
    edited_value: str | None = None


@router.post("/customers/{customer_id}/conversations")
def upload_conversation(customer_id: str, body: TranscriptIn):
    from backend_v3.advisor.conversation_service import ingest_conversation

    if not body.transcript or not body.transcript.strip():
        raise HTTPException(400, "Transcript is empty")
    try:
        result = ingest_conversation(customer_id, body.transcript)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(503, f"Conversation processing failed: {type(exc).__name__}: {exc}")
    return result


@router.get("/customers/{customer_id}/conversations")
def list_conversations(customer_id: str):
    from backend_v3.advisor.conversation_service import get_conversation_history

    try:
        return get_conversation_history(customer_id)
    except Exception as exc:
        raise HTTPException(503, f"Could not reach conversation history: {type(exc).__name__}: {exc}")


@router.get("/customers/{customer_id}/pending-memories")
def list_pending_memories(customer_id: str, status: str = "pending"):
    from backend_v3.advisor.memory_model import get_pending_memories

    try:
        return get_pending_memories(customer_id, status=status)
    except Exception as exc:
        raise HTTPException(503, f"Could not reach memory store: {type(exc).__name__}: {exc}")


@router.get("/customers/{customer_id}/memory-timeline")
def memory_timeline(customer_id: str):
    from backend_v3.advisor.memory_model import get_memory_timeline

    try:
        return get_memory_timeline(customer_id)
    except Exception as exc:
        raise HTTPException(503, f"Could not reach memory store: {type(exc).__name__}: {exc}")


@router.post("/memories/{memory_id}/approve")
def approve_memory(memory_id: str, body: ApproveIn):
    from backend_v3.advisor.memory_model import approve_memory as _approve

    try:
        return _approve(memory_id, edited_value=body.edited_value)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(503, f"Approval failed: {type(exc).__name__}: {exc}")


@router.post("/memories/{memory_id}/reject")
def reject_memory(memory_id: str):
    from backend_v3.advisor.memory_model import reject_memory as _reject

    try:
        return _reject(memory_id)
    except Exception as exc:
        raise HTTPException(503, f"Rejection failed: {type(exc).__name__}: {exc}")

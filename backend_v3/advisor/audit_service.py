"""
Audit Service boundary.

Stage 1 keeps audit logging intentionally small and local to the graph where
practical. This gives future integration writes a single place to record who
approved, rejected, imported, or synced customer information.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def audit_event(event_type: str, actor: str, subject_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "actor": actor,
        "subject_id": subject_id,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

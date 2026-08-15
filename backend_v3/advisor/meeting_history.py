"""
Meeting History timeline — Stage 3.

Every Conversation record (a transcript upload, meeting notes, or a
future Teams/Zoom transcript) already has a source id everything else
derived from it points back to: PendingMemory.source and
FollowUp.source are both "conversation_<id>". This module joins that
back up into one timeline entry per meeting:

    Meeting -> Summary -> Insights -> Memory changes -> Follow-ups

"Insights" are the extraction's raw proposals; "memory changes" are what
became of them (accepted/edited/rejected), which can differ from the
original proposal once an advisor edits a value before approving it.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_meeting_history(customer_id: str) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    conversations = run_query(
        "MATCH (c:Customer {customer_id: $customer_id})-[:HAD_CONVERSATION]->(conv:Conversation) "
        "RETURN conv.conversation_id AS conversation_id, conv.date AS date, conv.summary AS summary, "
        "coalesce(conv.interaction_type, 'meeting') AS interaction_type, "
        "conv.source_system AS source_system "
        "ORDER BY conv.date DESC",
        {"customer_id": customer_id},
    )

    memories = run_query(
        "MATCH (c:Customer {customer_id: $customer_id})-[:HAS_PENDING_MEMORY]->(m:PendingMemory) "
        "RETURN m.source AS source, m.memory_id AS memory_id, m.memory_type AS memory_type, "
        "m.value AS value, m.evidence AS evidence, m.confidence AS confidence, m.status AS status",
        {"customer_id": customer_id},
    )
    memories_by_source: dict[str, list[dict[str, Any]]] = {}
    for memory in memories:
        memories_by_source.setdefault(memory["source"], []).append(memory)

    followups = run_query(
        "MATCH (c:Customer {customer_id: $customer_id})-[:HAS_FOLLOWUP]->(f:FollowUp) "
        "RETURN f.source AS source, f.followup_id AS followup_id, f.title AS title, "
        "f.due_date AS due_date, f.assigned_to AS assigned_to, f.status AS status",
        {"customer_id": customer_id},
    )
    followups_by_source: dict[str, list[dict[str, Any]]] = {}
    for followup in followups:
        followups_by_source.setdefault(followup["source"], []).append(followup)

    timeline = []
    for conversation in conversations:
        source_key = f"conversation_{conversation['conversation_id']}"
        related_memories = memories_by_source.get(source_key, [])
        timeline.append(
            {
                "conversation_id": conversation["conversation_id"],
                "date": conversation["date"],
                "summary": conversation["summary"],
                "interaction_type": conversation["interaction_type"],
                "source_system": conversation["source_system"],
                "insights": [
                    {
                        "memory_id": m["memory_id"],
                        "memory_type": m["memory_type"],
                        "value": m["value"],
                        "evidence": m["evidence"],
                        "confidence": m["confidence"],
                    }
                    for m in related_memories
                ],
                "memory_changes": [
                    {"memory_id": m["memory_id"], "memory_type": m["memory_type"], "value": m["value"], "status": m["status"]}
                    for m in related_memories
                    if m["status"] != "pending"
                ],
                "pending_review_count": sum(1 for m in related_memories if m["status"] == "pending"),
                "follow_ups": [
                    {
                        "followup_id": f["followup_id"],
                        "title": f["title"],
                        "due_date": f["due_date"],
                        "assigned_to": f["assigned_to"],
                        "status": f["status"],
                    }
                    for f in followups_by_source.get(source_key, [])
                ],
            }
        )
    return timeline

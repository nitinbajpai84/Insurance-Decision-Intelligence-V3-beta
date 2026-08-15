"""
BE-4 Semantic Memory Service (Qdrant side) + orchestration that ties
conversation upload together: transcript -> chunk -> embed -> Qdrant,
transcript -> Gemini extraction -> pending memories (memory_model.py).

Qdrant storage happens unconditionally (it's just semantic memory of what
was actually said — no approval needed to remember a transcript existed).
Neo4j facts only get written later, and only for items the advisor
approves — see memory_model.approve_memory.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def _save_conversation_record(customer_id: str, conversation_id: str, summary: str, transcript: str) -> None:
    from backend_v3.graph_store.neo4j_client import run_write

    today = datetime.now(timezone.utc).date().isoformat()
    excerpt = transcript[:500] + ("…" if len(transcript) > 500 else "")
    run_write(
        "MATCH (c:Customer {customer_id: $customer_id}) "
        "MERGE (conv:Conversation {conversation_id: $conversation_id}) "
        "SET conv.date = $today, conv.summary = $summary, conv.transcript_excerpt = $excerpt "
        "MERGE (c)-[:HAD_CONVERSATION]->(conv)",
        {"customer_id": customer_id, "conversation_id": conversation_id, "today": today, "summary": summary, "excerpt": excerpt},
    )


def ingest_conversation(customer_id: str, transcript: str) -> dict[str, Any]:
    """The Milestone 2 entry point: upload a transcript, get back a
    processing result with proposed memories awaiting advisor approval."""
    from backend_v3.advisor.conversation_intelligence import analyze_conversation
    from backend_v3.advisor.memory_model import create_pending_memory
    from backend_v3.advisor.retrieval import get_customer_graph
    from backend_v3.advisor.semantic_memory_service import store_transcript_chunks
    import uuid

    if get_customer_graph(customer_id) is None:
        raise ValueError(f"Customer {customer_id} not found")

    conversation_id = str(uuid.uuid4())
    chunks_stored = store_transcript_chunks(customer_id, conversation_id, transcript)
    analysis = analyze_conversation(transcript)
    _save_conversation_record(customer_id, conversation_id, analysis["summary"], transcript)

    proposed = []
    for item in analysis.get("extracted_items", []):
        mem = create_pending_memory(
            customer_id=customer_id,
            memory_type=item["memory_type"],
            value=item["value"],
            evidence=item["evidence"],
            confidence=item["confidence"],
            conversation_id=conversation_id,
            category=item.get("category"),
        )
        proposed.append(mem)

    return {
        "conversation_id": conversation_id,
        "customer_id": customer_id,
        "summary": analysis["summary"],
        "chunks_stored": chunks_stored,
        "proposed_memories": proposed,
    }


def get_conversation_history(customer_id: str) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    return run_query(
        "MATCH (c:Customer {customer_id: $customer_id})-[:HAD_CONVERSATION]->(conv:Conversation) "
        "RETURN conv.conversation_id AS conversation_id, conv.date AS date, "
        "conv.summary AS summary, conv.transcript_excerpt AS transcript_excerpt "
        "ORDER BY conv.date DESC",
        {"customer_id": customer_id},
    )

"""
Semantic Memory Service boundary.

Qdrant stores what was said in conversations and retrieves semantically
relevant snippets. It is memory/evidence, not customer truth; approved facts
are promoted separately through memory_model.py into Neo4j.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CONVERSATIONS_COLLECTION = "advisor_conversations"
CHUNK_SIZE_CHARS = 1200
CHUNK_OVERLAP_CHARS = 150


def chunk_text(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE_CHARS:
        return [text] if text.strip() else []
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_SIZE_CHARS
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP_CHARS
    return chunks


def store_transcript_chunks(customer_id: str, conversation_id: str, transcript: str) -> int:
    from backend_v3.ingestion.ocr import embed_text
    from backend_v3.vector_store.qdrant_client import ensure_collection, upsert_points

    ensure_collection(CONVERSATIONS_COLLECTION)
    chunks = chunk_text(transcript)
    points = []
    for i, chunk in enumerate(chunks):
        vector = embed_text(chunk)
        points.append({
            "id": str(uuid.uuid4()),
            "vector": vector,
            "payload": {
                "customer_id": customer_id,
                "conversation_id": conversation_id,
                "chunk_index": i,
                "text": chunk,
                "conversation_type": "uploaded_transcript",
            },
        })
    if points:
        upsert_points(CONVERSATIONS_COLLECTION, points)
    return len(points)


def get_relevant_conversation_memory(customer_id: str, query_text: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    from backend_v3.ingestion.ocr import embed_text
    from backend_v3.vector_store.qdrant_client import search
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    probe = query_text or "Meeting preparation context and history for this customer."
    vector = embed_text(probe)
    hits = search(
        CONVERSATIONS_COLLECTION,
        vector,
        limit=limit,
        query_filter=Filter(must=[FieldCondition(key="customer_id", match=MatchValue(value=customer_id))]),
    )
    return [
        {
            "text": h["payload"]["text"],
            "score": h["score"],
            "source": "conversation_notes",
            "confidence": round(min(1.0, h["score"]), 2),
        }
        for h in hits
    ]

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


def count_conversation_chunks_by_customer() -> dict[str, int]:
    """How many stored chunks each customer has, for callers (priority
    scoring's fleet-wide pass) that need presence/volume across every
    customer without N embedding calls and N semantic searches.

    One scroll through the collection's payloads — no vectors, no
    per-customer round trip, no embedding model call at all, since a
    plain count needs no query vector.
    """
    from backend_v3.vector_store.qdrant_client import get_client

    counts: dict[str, int] = {}
    try:
        client = get_client()
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=CONVERSATIONS_COLLECTION,
                limit=500,
                offset=offset,
                with_payload=["customer_id"],
                with_vectors=False,
            )
            for point in points:
                customer_id = (point.payload or {}).get("customer_id")
                if customer_id:
                    counts[customer_id] = counts.get(customer_id, 0) + 1
            if offset is None:
                break
    except Exception:
        # A collection that doesn't exist yet (fresh environment) or a
        # Qdrant outage must not break a fleet-wide priority pass —
        # every customer just falls back to a 0 count.
        return {}
    return counts


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

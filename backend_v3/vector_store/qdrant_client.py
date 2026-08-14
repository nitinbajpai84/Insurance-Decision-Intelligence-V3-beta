"""
Thin Qdrant client wrapper — the ONLY module that imports qdrant_client
directly (see docs/ARCHITECTURE.md's "client wrapper convention").
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.config import require_qdrant

VECTOR_SIZE = 3072  # matches Gemini's gemini-embedding-001, same as V2's LanceDB tables

_client = None


def get_client():
    global _client
    if _client is None:
        from qdrant_client import QdrantClient

        url, api_key = require_qdrant()
        _client = QdrantClient(url=url, api_key=api_key)
    return _client


def ensure_collection(name: str, vector_size: int = VECTOR_SIZE) -> None:
    from qdrant_client.models import Distance, VectorParams

    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def upsert_points(collection: str, points: list[dict[str, Any]]) -> None:
    """points: [{"id": ..., "vector": [...], "payload": {...}}, ...]"""
    from qdrant_client.models import PointStruct

    client = get_client()
    client.upsert(
        collection_name=collection,
        points=[PointStruct(id=p["id"], vector=p["vector"], payload=p.get("payload", {})) for p in points],
    )


def search(collection: str, query_vector: list[float], limit: int = 10, query_filter: dict | None = None) -> list[dict[str, Any]]:
    client = get_client()
    hits = client.query_points(
        collection_name=collection, query=query_vector, limit=limit, query_filter=query_filter
    ).points
    return [{"id": h.id, "score": h.score, "payload": h.payload} for h in hits]


def health_check() -> dict[str, Any]:
    try:
        client = get_client()
        collections = [c.name for c in client.get_collections().collections]
        return {"status": "ok", "collections": collections}
    except Exception as exc:
        return {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}

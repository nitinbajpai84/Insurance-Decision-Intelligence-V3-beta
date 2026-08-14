"""
Claims-document ingestion pipeline: OCR/extract -> chunk -> embed -> dual
write to Qdrant (chunks, for semantic search) and Neo4j (entities/relations,
for graph traversal). See docs/ARCHITECTURE.md for the overall shape.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.ingestion.ocr import embed_text, extract_claim_document
from backend_v3.vector_store.qdrant_client import ensure_collection, upsert_points

CLAIMS_COLLECTION = "claims_documents"
CHUNK_SIZE_CHARS = 1200
CHUNK_OVERLAP_CHARS = 150


def _chunk_text(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE_CHARS:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE_CHARS
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP_CHARS
    return chunks


def _write_graph(claim_id: str, doc_id: str, extraction: dict[str, Any]) -> None:
    from backend_v3.graph_store.neo4j_client import run_write

    fields = extraction.get("extracted_fields", {})
    run_write(
        """
        MERGE (c:Claim {claim_id: $claim_id})
        MERGE (d:Document {doc_id: $doc_id})
        SET d.doc_type = $doc_type, d.extraction_confidence = $confidence
        MERGE (d)-[:BELONGS_TO]->(c)
        """,
        {
            "claim_id": claim_id,
            "doc_id": doc_id,
            "doc_type": extraction.get("doc_type", "other"),
            "confidence": extraction.get("extraction_confidence", 0.0),
        },
    )
    for party in fields.get("parties", []) or []:
        if not party.get("name"):
            continue
        run_write(
            """
            MATCH (d:Document {doc_id: $doc_id})
            MERGE (p:Party {name: $name})
            SET p.role = $role
            MERGE (p)-[:MENTIONED_IN]->(d)
            """,
            {"doc_id": doc_id, "name": party["name"], "role": party.get("role", "other")},
        )
    for flag in fields.get("flags", []) or []:
        run_write(
            """
            MATCH (d:Document {doc_id: $doc_id})
            MERGE (f:Flag {description: $flag})
            MERGE (f)-[:RAISED_BY]->(d)
            """,
            {"doc_id": doc_id, "flag": flag},
        )


def ingest_claim_document(claim_id: str, file_bytes: bytes, filename: str, mime_type: str) -> dict[str, Any]:
    doc_id = str(uuid.uuid4())

    extraction = extract_claim_document(file_bytes, mime_type)

    ensure_collection(CLAIMS_COLLECTION)
    chunks = _chunk_text(extraction.get("full_text", ""))
    points = []
    for i, chunk in enumerate(chunks):
        vector = embed_text(chunk)
        points.append({
            "id": str(uuid.uuid4()),
            "vector": vector,
            "payload": {
                "claim_id": claim_id,
                "doc_id": doc_id,
                "filename": filename,
                "doc_type": extraction.get("doc_type", "other"),
                "chunk_index": i,
                "chunk_text": chunk,
            },
        })
    if points:
        upsert_points(CLAIMS_COLLECTION, points)

    _write_graph(claim_id, doc_id, extraction)

    return {
        "doc_id": doc_id,
        "claim_id": claim_id,
        "filename": filename,
        "doc_type": extraction.get("doc_type"),
        "extraction_confidence": extraction.get("extraction_confidence"),
        "chunks_embedded": len(points),
        "extracted_fields": extraction.get("extracted_fields", {}),
    }

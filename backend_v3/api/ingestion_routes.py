"""Claims-document ingestion endpoints."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.ingestion.pipeline import ingest_claim_document

router = APIRouter(tags=["ingestion"])


@router.post("/claims/{claim_id}/documents")
async def upload_claim_document(claim_id: str, file: UploadFile = File(...)):
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty file")
    try:
        result = ingest_claim_document(
            claim_id=claim_id,
            file_bytes=contents,
            filename=file.filename or "unknown",
            mime_type=file.content_type or "application/octet-stream",
        )
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    return result


@router.get("/claims/{claim_id}/documents")
def list_claim_documents(claim_id: str):
    from backend_v3.graph_store.neo4j_client import run_query

    docs = run_query(
        """
        MATCH (d:Document)-[:BELONGS_TO]->(c:Claim {claim_id: $claim_id})
        OPTIONAL MATCH (p:Party)-[:MENTIONED_IN]->(d)
        OPTIONAL MATCH (f:Flag)-[:RAISED_BY]->(d)
        RETURN d.doc_id AS doc_id, d.doc_type AS doc_type, d.extraction_confidence AS confidence,
               collect(DISTINCT p.name) AS parties, collect(DISTINCT f.description) AS flags
        """,
        {"claim_id": claim_id},
    )
    return {"claim_id": claim_id, "documents": docs}

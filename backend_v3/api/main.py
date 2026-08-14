"""
Meridian V3 (beta) — FastAPI entrypoint.

Mirrors backend_v2/api/main.py's shape (health check + CORS + router
registration) but reports Neo4j/Qdrant status alongside DuckDB/Gemini.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.config import CORS_ORIGINS, GEMINI_API_KEY

app = FastAPI(title="Meridian V3 beta — context-graph + unstructured ingestion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/v3/health")
def health():
    from backend_v3.graph_store.neo4j_client import health_check as neo4j_health
    from backend_v3.vector_store.qdrant_client import health_check as qdrant_health

    return {
        "service": "meridian-v3-beta",
        "neo4j": neo4j_health(),
        "qdrant": qdrant_health(),
        "gemini": {"api_key_present": bool(GEMINI_API_KEY)},
    }


try:
    from backend_v3.api.ingestion_routes import router as ingestion_router

    app.include_router(ingestion_router, prefix="/api/v3")
except Exception as exc:  # pragma: no cover — surfaced via /api/v3/health instead of a hard crash
    print(f"[main] ingestion_routes not loaded: {type(exc).__name__}: {exc}", file=sys.stderr)

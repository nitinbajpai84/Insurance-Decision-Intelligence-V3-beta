# Meridian V3 (beta)

Forked from `Insurance PoC - V2.0` — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for what's different and why. The live V2 "Meridian" site is untouched by
anything in this repo.

## Status

Scaffold stage. Structured business data (policies/customers/claims) still
needs to be carried over from V2's DuckDB; Neo4j AuraDB Free + Qdrant Cloud
Free need to be provisioned and their credentials dropped into `.env`
(copy `.env.example`); the claims-document ingestion pipeline
(`backend_v3/ingestion/`) is written but untested against live databases.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # then fill in GEMINI_API_KEY, NEO4J_*, QDRANT_*
uvicorn backend_v3.api.main:app --port 3011 --reload
```

`GET /api/v3/health` reports Neo4j/Qdrant/Gemini connectivity.

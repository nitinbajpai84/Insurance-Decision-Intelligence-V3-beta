# Meridian V3 (beta) — Architecture

Forked from `Insurance PoC - V2.0` on 2026-08-15. V2 (live as "Meridian" on
Vercel + Cloud Run) is untouched and keeps running independently. This is a
separate GitHub repo, separate Vercel project, separate Cloud Run service —
nothing here can break the V2 production site.

## What's changing vs. V2

| Layer | V2 | V3 beta |
|---|---|---|
| Structured business data (policies, customers, claims, campaigns) | DuckDB | **Unchanged** — still DuckDB, still the system of record for tabular facts |
| Context graph (concept_nodes, graph_edges, decision_rules) | DuckDB tables + DuckPGQ | **Neo4j AuraDB Free** — real Cypher, native multi-hop traversal |
| Semantic search (glossary/schema embeddings) | Embedded LanceDB files baked into the Docker image | **Qdrant Cloud Free** — hosted, metadata filtering, hybrid search |
| Unstructured documents | Not handled | **New**: OCR + extraction pipeline, chunked/embedded into Qdrant, entities/relationships into Neo4j |

DuckDB stays because it's genuinely good at what it's doing (fast analytical
SQL over the structured book of business) and nothing about that is broken.
Only the graph and vector layers — which is what an unstructured-document
pipeline actually stresses — move to dedicated services.

## Why Neo4j AuraDB Free + Qdrant Cloud Free

Both are real, managed, free-tier services — not self-hosted, so there's no
VM/Docker uptime to babysit (the failure mode that caused the Render OOM
saga earlier in this project). Neo4j is literally the reference graph
database the user asked to emulate; Qdrant is the closest open-source analog
to Pinecone's feature set (hybrid search, rich metadata filtering).

Trade-off, noted honestly: both are stateful managed services with their own
free-tier limits (node/edge counts, vector counts, cluster size) that we
haven't hit yet and should watch as ingestion volume grows. If a limit
becomes a real constraint, self-hosting on a persistent VM (e.g. Oracle
Always Free) is the fallback — same interfaces, different connection string,
no application code change needed if the client wrappers below are used
consistently.

## First unstructured use case: claims documents

Claim forms, medical reports, adjuster notes, damage photos. Chosen because
it directly feeds two things V2 already has UI for (fraud exposure, claims
processing) but currently only sees structured `claims` / `claim_fraud_indicators`
rows — no visibility into the actual documents behind a claim.

## Ingestion pipeline shape

```
upload (PDF/image) for claim_id
  -> OCR + structured extraction (Gemini multimodal — see ingestion/ocr.py)
  -> text chunking
  -> embed chunks -> upsert to Qdrant (payload: claim_id, doc_type, chunk_text, source_doc_id)
  -> extract entities/relationships (parties, dates, amounts, diagnoses, flags)
     -> upsert nodes/edges to Neo4j, linked to claim::<claim_id> node
  -> write a document_ingest_log row to DuckDB (audit trail: what was
     ingested, when, extraction confidence) so the structured layer knows
     an unstructured document exists for a claim, without duplicating its
     content there
```

Neo4j and Qdrant are queried live at answer-time by the SQL/graph agent,
the same way V2's `binding_resolver` currently queries DuckDB + LanceDB —
that resolver is the piece most directly being forked and rewired.

## Client wrapper convention

`backend_v3/graph_store/neo4j_client.py` and `backend_v3/vector_store/qdrant_client.py`
are the ONLY places that import the `neo4j` / `qdrant_client` SDKs directly.
Every other module goes through them. This is what makes "swap AuraDB Free
for a self-hosted Neo4j later" a config change, not a rewrite.

## Credentials

Never pasted into chat. Create the AuraDB Free instance and Qdrant Cloud
Free cluster yourself (both require their own account signup — outside what
an assistant can do on your behalf), download/copy the connection details,
and drop them into `backend_v3/.env` (gitignored) following `.env.example`.
Same pattern as `GEMINI_API_KEY` earlier in this project: read locally,
never echoed, promoted to a managed secret (GCP Secret Manager) at deploy
time.

## Status

Scaffold only as of 2026-08-15. Neo4j/Qdrant connectivity, the structured
business-data layer carried over from V2, and the actual ingestion endpoint
are next.

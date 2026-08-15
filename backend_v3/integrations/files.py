"""
Document indexing for file repositories (Drive, OneDrive, SharePoint).

The rule that governs this module: a file is a contextual source, never
customer truth.

Concretely, indexing a document does three things and deliberately not a
fourth:

  1. it resolves which customer the document is about, and skips it
     entirely if that cannot be established;
  2. it writes a Document node carrying full provenance and the source
     permission string, so a file the advisor loses access to can be
     excluded later;
  3. it embeds the text into Qdrant so retrieval can cite it.

It does not write goals, needs, life events, or any other fact. Anything
a document implies still has to travel the Stage 1 proposal-and-approval
path before it becomes customer truth.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _match_customer(title: str, text: str, source_system: str) -> tuple[str | None, str]:
    """Find the customer a document concerns.

    Email addresses in the content are checked first because they are
    deterministic. A customer name appearing in the title is treated as a
    weaker signal and still requires the name to resolve to exactly one
    customer.
    """
    from backend_v3.integrations.identity import resolve_identity

    for address in set(_EMAIL_RE.findall(text[:5000])):
        match = resolve_identity(email=address, source_system=source_system)
        if match.resolved:
            return match.customer_id, f"email:{address}"

    from backend_v3.graph_store.neo4j_client import run_query

    haystack = f"{title} {text[:2000]}".lower()
    rows = run_query("MATCH (c:Customer) RETURN c.customer_id AS customer_id, c.name AS name", {})
    hits = [r for r in rows if r["name"] and r["name"].lower() in haystack]
    if len(hits) == 1:
        return hits[0]["customer_id"], "name_in_document"
    return None, "unmatched"


def index_document(
    *,
    source_system: str,
    source_id: str,
    title: str,
    text: str,
    reference: str,
    modified_at: str | None = None,
    permissions: str = "inherits_source",
) -> dict[str, Any]:
    """Index one document as a contextual source."""
    from backend_v3.graph_store.neo4j_client import run_write

    customer_id, matched_on = _match_customer(title, text, source_system)
    if not customer_id:
        # A document we cannot attribute is not indexed. Embedding it
        # against no customer would make it unretrievable anyway, and
        # storing it would be collecting the advisor's files for nothing.
        return {"indexed": False, "reason": "no_customer_match", "title": title}

    document_id = f"{source_system}_{source_id}"
    run_write(
        "MATCH (c:Customer {customer_id: $customer_id}) "
        "MERGE (d:Document {document_id: $document_id}) "
        "SET d.title = $title, d.modified_at = $modified_at, d.permissions = $permissions, "
        "    d.customer_id = $customer_id, d.matched_on = $matched_on, "
        "    d.source_system = $source_system, d.source_id = $source_id, "
        "    d.original_reference = $original_reference, d.imported_at = $imported_at, "
        "    d.contextual_only = true "
        "MERGE (c)-[r:HAS_DOCUMENT]->(d) "
        "SET r.source = $source, r.confidence = 1.0, r.created_at = $now",
        {
            "customer_id": customer_id,
            "document_id": document_id,
            "title": title,
            "modified_at": modified_at,
            "permissions": permissions,
            "matched_on": matched_on,
            "source_system": source_system,
            "source_id": source_id,
            "original_reference": reference,
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "source": document_id,
            "now": datetime.now(timezone.utc).isoformat(),
        },
    )

    chunks = 0
    try:
        from backend_v3.advisor.semantic_memory_service import store_transcript_chunks

        chunks = store_transcript_chunks(customer_id, document_id, f"{title}\n\n{text}")
    except Exception:
        # Losing the embedding must not lose the graph record above.
        chunks = 0

    return {
        "indexed": True,
        "document_id": document_id,
        "customer_id": customer_id,
        "matched_on": matched_on,
        "chunks_stored": chunks,
    }


def list_documents(customer_id: str) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    return run_query(
        "MATCH (c:Customer {customer_id: $customer_id})-[:HAS_DOCUMENT]->(d:Document) "
        "RETURN d.document_id AS document_id, d.title AS title, d.source_system AS source_system, "
        "d.original_reference AS original_reference, d.modified_at AS modified_at, "
        "d.matched_on AS matched_on "
        "ORDER BY d.modified_at DESC",
        {"customer_id": customer_id},
    )

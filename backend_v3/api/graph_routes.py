"""Context graph endpoint — whole-graph snapshot shaped for react-force-graph."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

router = APIRouter(tags=["graph"])


@router.get("/graph")
def get_graph(limit: int = 300):
    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        """
        MATCH (a)-[r]->(b)
        RETURN
          elementId(a) AS src_id, labels(a)[0] AS src_type, coalesce(a.claim_id, a.doc_id, a.name, a.description) AS src_label,
          elementId(b) AS dst_id, labels(b)[0] AS dst_type, coalesce(b.claim_id, b.doc_id, b.name, b.description) AS dst_label,
          type(r) AS rel_type
        LIMIT $limit
        """,
        {"limit": limit},
    )

    nodes: dict[str, dict] = {}
    links = []
    for row in rows:
        nodes.setdefault(row["src_id"], {"id": row["src_id"], "type": row["src_type"], "label": row["src_label"]})
        nodes.setdefault(row["dst_id"], {"id": row["dst_id"], "type": row["dst_type"], "label": row["dst_label"]})
        links.append({"source": row["src_id"], "target": row["dst_id"], "type": row["rel_type"]})

    return {"nodes": list(nodes.values()), "links": links}

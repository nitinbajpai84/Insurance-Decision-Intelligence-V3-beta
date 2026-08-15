"""
Per-customer knowledge graph view — Stage 4.

The existing /graph endpoint (graph_routes.py) is a whole-database
snapshot built for the Claims context graph; it carries no relationship
provenance. This module is scoped to one customer and keeps the
source/confidence/created_at every edge already carries in Neo4j, so a
click on a node or edge in the UI can show "value, source, confidence,
last verified" exactly as the spec asks — the data was always there,
just not exposed in graph-shaped form before.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Customer -> Family, Life Events, Goals, Needs, Policies, Conversations —
# the exact traversal the spec lists, one relationship type per hop.
_EDGES = (
    ("HAS_FAMILY_MEMBER", "FamilyMember", "name"),
    ("EXPERIENCED", "LifeEvent", "description"),
    ("HAS_GOAL", "Goal", "description"),
    ("HAS_NEED", "Need", "description"),
    ("OWNS", "Policy", "product_name"),
    ("HAD_CONVERSATION", "Conversation", "summary"),
    ("CONCERNED_ABOUT", "Topic", "name"),
)


def get_customer_knowledge_graph(customer_id: str) -> dict[str, Any] | None:
    from backend_v3.graph_store.neo4j_client import run_query

    center = run_query(
        "MATCH (c:Customer {customer_id: $customer_id}) RETURN c.name AS name", {"customer_id": customer_id}
    )
    if not center or not center[0].get("name"):
        return None

    nodes: dict[str, dict[str, Any]] = {
        f"customer:{customer_id}": {
            "id": f"customer:{customer_id}",
            "type": "Customer",
            "label": center[0]["name"],
            "value": center[0]["name"],
            "source": None,
            "confidence": None,
            "last_verified_at": None,
        }
    }
    links: list[dict[str, Any]] = []

    for rel_type, label, value_field in _EDGES:
        # Conversation volume can run high (a real book of repeated
        # captures); cap it so the force layout stays legible — the most
        # recent ones are the most relevant to show anyway.
        limit_clause = "ORDER BY r.created_at DESC LIMIT 15 " if rel_type == "HAD_CONVERSATION" else ""
        rows = run_query(
            f"MATCH (c:Customer {{customer_id: $customer_id}})-[r:{rel_type}]->(n) "
            f"RETURN elementId(n) AS node_id, labels(n)[0] AS node_type, "
            f"n.{value_field} AS value, r.source AS source, r.confidence AS confidence, "
            f"r.created_at AS created_at "
            f"{limit_clause}",
            {"customer_id": customer_id},
        )
        for row in rows:
            if not row.get("value"):
                continue
            node_id = f"{label}:{row['node_id']}"
            # Conversation summaries run to full sentences; a short label
            # keeps the force layout legible, the full text is still in
            # `value` for the click-to-inspect panel.
            raw_value = str(row["value"])
            short_label = raw_value[:24] + "…" if len(raw_value) > 24 else raw_value
            nodes[node_id] = {
                "id": node_id,
                "type": row["node_type"] or label,
                "label": short_label,
                "value": row["value"],
                "source": row.get("source"),
                "confidence": row.get("confidence"),
                "last_verified_at": row.get("created_at"),
            }
            links.append(
                {
                    "source": f"customer:{customer_id}",
                    "target": node_id,
                    "type": rel_type,
                }
            )

    return {"customer_id": customer_id, "nodes": list(nodes.values()), "links": links}

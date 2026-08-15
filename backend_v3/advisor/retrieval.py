"""
Retrieval layer for the advisor product — assembles a customer's full
context from all three stores before Gemini ever sees anything:

  Neo4j    -> relationships: family, life stage, goals, needs, life events,
              meetings, concerns, discussed topics, owned-policy links
  DuckDB   -> authoritative portfolio figures (premium, status) for those
              owned policies — Neo4j only holds the relationship
  Qdrant   -> semantically relevant past conversation notes

Every function here returns plain dicts with a `source` and `confidence`
per fact, taken straight from the relationship provenance written in
synthetic_data.py (or, later, by the Milestone 2 memory-approval flow) —
this is what lets the briefing service cite evidence instead of asserting
facts with no traceable origin.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def list_customers() -> list[dict[str, Any]]:
    """Every Customer node Neo4j knows about — used for Agent Home / Customer
    List. Not the full assemble_customer_context (no portfolio/Qdrant call)
    since this runs for every customer on one page load."""
    from backend_v3.graph_store.neo4j_client import run_query

    return run_query(
        "MATCH (c:Customer) "
        "OPTIONAL MATCH (c)-[:EXPERIENCED]->(e:LifeEvent) "
        "OPTIONAL MATCH (c)-[:CONCERNED_ABOUT]->(t:Topic) "
        "OPTIONAL MATCH (c)-[:HAD_MEETING]->(m:Meeting) "
        "RETURN c.customer_id AS customer_id, c.name AS name, c.life_stage AS life_stage, "
        "collect(DISTINCT {description: e.description, date: e.date}) AS life_events, "
        "collect(DISTINCT {topic: t.name}) AS concerns, "
        "collect(DISTINCT {date: m.date}) AS meetings"
    )


def get_customer_graph(customer_id: str) -> dict[str, Any] | None:
    """Everything Neo4j knows about this customer, each fact carrying its
    relationship provenance (source/confidence/created_at)."""
    from backend_v3.graph_store.neo4j_client import run_query

    core = run_query(
        "MATCH (c:Customer {customer_id: $customer_id}) "
        "OPTIONAL MATCH (a:Advisor)-[:ADVISES]->(c) "
        "RETURN c.name AS name, c.life_stage AS life_stage, a.name AS advisor_name",
        {"customer_id": customer_id},
    )
    if not core or not core[0].get("name"):
        return None
    profile = core[0]

    def _rel(cypher: str) -> list[dict]:
        return run_query(cypher, {"customer_id": customer_id})

    family = _rel(
        "MATCH (c:Customer {customer_id: $customer_id})-[r:HAS_FAMILY_MEMBER]->(f:FamilyMember) "
        "RETURN f.name AS name, f.relationship AS relationship, r.source AS source, r.confidence AS confidence"
    )
    goals = _rel(
        "MATCH (c:Customer {customer_id: $customer_id})-[r:HAS_GOAL]->(g:Goal) "
        "RETURN g.description AS description, g.category AS category, r.source AS source, r.confidence AS confidence"
    )
    needs = _rel(
        "MATCH (c:Customer {customer_id: $customer_id})-[r:HAS_NEED]->(n:Need) "
        "RETURN n.description AS description, n.category AS category, r.source AS source, r.confidence AS confidence"
    )
    life_events = _rel(
        "MATCH (c:Customer {customer_id: $customer_id})-[r:EXPERIENCED]->(e:LifeEvent) "
        "RETURN e.description AS description, e.date AS date, e.category AS category, "
        "r.source AS source, r.confidence AS confidence ORDER BY e.date DESC"
    )
    meetings = _rel(
        "MATCH (c:Customer {customer_id: $customer_id})-[r:HAD_MEETING]->(m:Meeting) "
        "RETURN m.date AS date, m.summary AS summary, r.source AS source, r.confidence AS confidence ORDER BY m.date DESC"
    )
    concerns = _rel(
        "MATCH (c:Customer {customer_id: $customer_id})-[r:CONCERNED_ABOUT]->(t:Topic) "
        "RETURN t.name AS topic, r.source AS source, r.confidence AS confidence"
    )
    discussed = _rel(
        "MATCH (c:Customer {customer_id: $customer_id})-[r:DISCUSSED]->(t:Topic) "
        "RETURN t.name AS topic, r.source AS source, r.confidence AS confidence"
    )
    owned_policy_ids = _rel(
        "MATCH (c:Customer {customer_id: $customer_id})-[:OWNS]->(p:Policy) RETURN p.policy_id AS policy_id"
    )

    return {
        "customer_id": customer_id,
        "name": profile["name"],
        "life_stage": profile["life_stage"],
        "advisor_name": profile.get("advisor_name"),
        "family": family,
        "goals": goals,
        "needs": needs,
        "life_events": life_events,
        "meetings": meetings,
        "concerns": concerns,
        "discussed_topics": discussed,
        "owned_policy_ids": [r["policy_id"] for r in owned_policy_ids],
    }


def get_portfolio(customer_id: str, policy_ids: list[str]) -> list[dict[str, Any]]:
    """Authoritative policy figures from DuckDB for the policies Neo4j says
    this customer owns — premium/status are facts DuckDB owns, not Neo4j."""
    if not policy_ids:
        return []
    from backend_v3.structured_store.duckdb_client import get_connection

    con = get_connection()
    try:
        ph = ",".join("?" for _ in policy_ids)
        rows = con.execute(
            f"select pol.policy_id, prod.product_name, prod.line_of_business, "
            f"pol.annual_premium, pol.policy_status "
            f"from policies pol join products prod on prod.product_id = pol.product_id "
            f"where pol.policy_id in ({ph})",
            policy_ids,
        ).fetchall()
        return [
            {
                "policy_id": r[0], "product_name": r[1], "line_of_business": r[2],
                "annual_premium": r[3], "policy_status": r[4],
                "source": "policy_system", "confidence": 1.0,
            }
            for r in rows
        ]
    finally:
        con.close()


def get_claims_for_customer(customer_id: str) -> list[dict[str, Any]]:
    """Stitches the Claims module into the advisor view — a customer's
    claims history, straight from DuckDB (same table the standalone Claims
    pages read), so an advisor sees the full relationship in one place
    instead of two disconnected modules."""
    from backend_v3.structured_store.duckdb_client import get_connection

    con = get_connection()
    try:
        rows = con.execute(
            "select claim_id, claim_number, claim_status, loss_date, report_date, "
            "loss_cause, paid_amount, reserve_amount "
            "from claims where customer_id = ? order by report_date desc",
            [customer_id],
        ).fetchall()
        cols = ["claim_id", "claim_number", "claim_status", "loss_date", "report_date",
                "loss_cause", "paid_amount", "reserve_amount"]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        con.close()


def get_relevant_conversations(customer_id: str, query_text: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    """Semantically relevant past conversation notes from Qdrant.

    Without a specific query_text, embeds a generic "meeting preparation"
    probe so the most broadly-relevant notes for this customer surface —
    Qdrant is filtered to this customer_id either way, so this is really
    semantic *ranking* within one customer's notes, not cross-customer search.
    """
    from backend_v3.advisor.semantic_memory_service import get_relevant_conversation_memory

    return get_relevant_conversation_memory(customer_id, query_text=query_text, limit=limit)


def assemble_customer_context(customer_id: str) -> dict[str, Any] | None:
    """The single entry point the briefing service (and Customer 360 API)
    calls — everything needed to prepare for a meeting, fully retrieved
    before any Gemini call happens."""
    graph = get_customer_graph(customer_id)
    if graph is None:
        return None
    portfolio = get_portfolio(customer_id, graph["owned_policy_ids"])
    conversations = get_relevant_conversations(customer_id)
    claims = get_claims_for_customer(customer_id)
    return {**graph, "portfolio": portfolio, "relevant_conversations": conversations, "claims": claims}

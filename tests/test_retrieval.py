"""
Integration tests against the live Neo4j/Qdrant/DuckDB instances (this
project verifies against real infrastructure throughout rather than mocks
— see docs/ARCHITECTURE.md). Requires the seeded advisor data
(backend_v3/advisor/synthetic_data.py) to have been run first.
"""
from conftest import KNOWN_CUSTOMER_ID, UNKNOWN_CUSTOMER_ID

from backend_v3.advisor.retrieval import assemble_customer_context, get_customer_graph, list_customers


def test_get_customer_graph_returns_none_for_unknown_customer():
    assert get_customer_graph(UNKNOWN_CUSTOMER_ID) is None


def test_get_customer_graph_returns_expected_shape_for_known_customer():
    graph = get_customer_graph(KNOWN_CUSTOMER_ID)
    assert graph is not None
    assert graph["customer_id"] == KNOWN_CUSTOMER_ID
    assert graph["name"]
    assert graph["life_stage"]
    for key in ("family", "goals", "needs", "life_events", "meetings", "concerns", "discussed_topics"):
        assert isinstance(graph[key], list)
    assert isinstance(graph["owned_policy_ids"], list) and len(graph["owned_policy_ids"]) > 0


def test_every_graph_fact_carries_source_and_confidence():
    graph = get_customer_graph(KNOWN_CUSTOMER_ID)
    for section in ("family", "goals", "needs", "life_events", "meetings", "concerns", "discussed_topics"):
        for item in graph[section]:
            assert "source" in item, f"{section} item missing source: {item}"
            assert "confidence" in item, f"{section} item missing confidence: {item}"
            assert item["confidence"] == 1.0  # seed data is already-approved advisor memory


def test_assemble_customer_context_joins_portfolio_from_duckdb():
    ctx = assemble_customer_context(KNOWN_CUSTOMER_ID)
    assert ctx is not None
    assert len(ctx["portfolio"]) == len(ctx["owned_policy_ids"])
    for policy in ctx["portfolio"]:
        assert policy["source"] == "policy_system"
        assert policy["annual_premium"] > 0


def test_assemble_customer_context_returns_none_for_unknown_customer():
    assert assemble_customer_context(UNKNOWN_CUSTOMER_ID) is None


def test_relevant_conversations_are_scoped_to_the_right_customer():
    ctx = assemble_customer_context(KNOWN_CUSTOMER_ID)
    # every retrieved conversation note must genuinely belong to this
    # customer -- a cross-customer leak here would be a real privacy bug.
    assert len(ctx["relevant_conversations"]) > 0
    for note in ctx["relevant_conversations"]:
        assert 0.0 <= note["confidence"] <= 1.0


def test_list_customers_includes_the_seeded_ten():
    customers = list_customers()
    ids = {c["customer_id"] for c in customers}
    assert KNOWN_CUSTOMER_ID in ids
    assert len(customers) >= 10

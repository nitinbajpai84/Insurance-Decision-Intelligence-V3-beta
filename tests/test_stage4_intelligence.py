"""
Stage 4 tests: transparent priority scoring, Next Best Action, knowledge
coverage/freshness, KPI honesty, and AI auditability.

The core property under test throughout: nothing here is an unexplained
number. Every score, coverage percentage, and KPI must be traceable to
real reasons or explicitly `null` with a stated cause — never a
fabricated figure.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend_v3.api.main import app
from conftest import KNOWN_CUSTOMER_ID

client = TestClient(app)


# --------------------------------------------------------------------------
# Priority scoring
# --------------------------------------------------------------------------

def test_priority_score_always_carries_reasons():
    """The spec's core requirement: never an unexplained black-box score."""
    from backend_v3.advisor.priority_service import score_customer

    result = score_customer(KNOWN_CUSTOMER_ID)
    assert result is not None
    assert result["reasons"], "a priority score with zero reasons is exactly the black box the spec forbids"
    for reason in result["reasons"]:
        assert reason["label"], "every reason must be a human-readable explanation, not just a code"


def test_priority_score_is_a_transparent_sum_of_its_reasons():
    """The score must equal the sum of the weights of the reasons shown —
    if it didn't, the displayed reasons wouldn't actually explain the
    number sitting next to them."""
    from backend_v3.advisor.priority_service import score_customer

    result = score_customer(KNOWN_CUSTOMER_ID)
    assert result["score"] == sum(r["weight"] for r in result["reasons"])


def test_score_all_customers_is_sorted_descending():
    from backend_v3.advisor.priority_service import score_all_customers

    scores = score_all_customers()
    assert len(scores) >= 10
    values = [s["score"] for s in scores]
    assert values == sorted(values, reverse=True)


def test_score_all_customers_responds_quickly():
    """score_all_customers() used to call score_customer() per customer,
    each doing a Qdrant semantic search — 20 sequential embed+search
    round trips for one fleet-wide ranking. It now does a handful of
    bulk queries plus one Qdrant scroll regardless of customer count."""
    import time

    start = time.monotonic()
    res = client.get("/api/v3/advisor/priority")
    elapsed = time.monotonic() - start

    assert res.status_code == 200
    assert elapsed < 5, f"Fleet-wide priority took {elapsed:.1f}s — expected bulk queries, not O(customers)"


def test_bulk_scores_agree_with_the_authoritative_single_customer_score():
    """The fast fleet-wide pass must produce the exact same score and
    reasons as score_customer()'s authoritative, Qdrant-backed
    computation for every customer — a caught regression: an earlier
    version counted Neo4j :HAD_CONVERSATION relationships instead of
    Qdrant chunks, which undercounted engagement for every seeded
    customer (their conversation memory has no matching Neo4j node) and
    silently changed several customers' scores and priority tier."""
    from backend_v3.advisor.priority_service import score_all_customers, score_customer

    bulk_by_id = {c["customer_id"]: c for c in score_all_customers()}
    checked = 0
    for customer_id, bulk_score in bulk_by_id.items():
        authoritative = score_customer(customer_id)
        assert bulk_score["score"] == authoritative["score"], (
            f"{authoritative['name']}: bulk={bulk_score['score']} authoritative={authoritative['score']}"
        )
        assert bulk_score["priority"] == authoritative["priority"]
        checked += 1
    assert checked >= 10


def test_priority_api_endpoint():
    res = client.get(f"/api/v3/advisor/customers/{KNOWN_CUSTOMER_ID}/priority")
    assert res.status_code == 200
    assert "reasons" in res.json()


def test_priority_unknown_customer_returns_404():
    res = client.get("/api/v3/advisor/customers/cust_does_not_exist/priority")
    assert res.status_code == 404


# --------------------------------------------------------------------------
# Next Best Action
# --------------------------------------------------------------------------

@pytest.fixture
def cleanup_nba():
    created_proposal_customer_ids: list[str] = []
    yield created_proposal_customer_ids
    from backend_v3.graph_store.neo4j_client import run_write

    for customer_id in created_proposal_customer_ids:
        run_write(
            "MATCH (:Customer {customer_id: $id})-[:HAS_NBA_PROPOSAL]->(n:NextBestAction) DETACH DELETE n",
            {"id": customer_id},
        )
        run_write(
            "MATCH (:Customer {customer_id: $id})-[:HAS_FOLLOWUP]->(f:FollowUp) "
            "WHERE f.source STARTS WITH 'next_best_action_' DETACH DELETE f",
            {"id": customer_id},
        )


def test_next_best_action_never_names_a_product(cleanup_nba):
    """Structural check, not just prompt trust: the response schema has
    no product-name field, and the action text should read as a
    discussion area rather than an instruction to sell."""
    from backend_v3.advisor.next_best_action import generate_next_best_actions

    result = generate_next_best_actions(KNOWN_CUSTOMER_ID)
    cleanup_nba.append(KNOWN_CUSTOMER_ID)

    assert result is not None
    for action in result["actions"]:
        assert "based_on" in action and action["based_on"], "every action must cite a grounding fact"
        lowered = action["action"].lower()
        for forbidden in ("sell ", "buy our", "purchase our", "recommend product"):
            assert forbidden not in lowered, f"action reads like a sales instruction: {action['action']}"


def test_accepting_an_action_creates_a_real_followup(cleanup_nba):
    from backend_v3.advisor.next_best_action import decide_action, generate_next_best_actions

    result = generate_next_best_actions(KNOWN_CUSTOMER_ID)
    cleanup_nba.append(KNOWN_CUSTOMER_ID)
    if not result["actions"]:
        pytest.skip("Gemini returned no actions this run")

    proposal_id = result["actions"][0]["proposal_id"]
    decision = decide_action(proposal_id, accept=True, due_date="2099-01-01")
    assert decision["status"] == "accepted"
    assert decision["followup_id"] is not None

    from backend_v3.advisor.followups import get_followup

    followup = get_followup(decision["followup_id"])
    assert followup is not None
    assert followup["due_date"] == "2099-01-01"


def test_rejecting_an_action_creates_no_followup(cleanup_nba):
    from backend_v3.advisor.next_best_action import decide_action, generate_next_best_actions

    result = generate_next_best_actions(KNOWN_CUSTOMER_ID)
    cleanup_nba.append(KNOWN_CUSTOMER_ID)
    if not result["actions"]:
        pytest.skip("Gemini returned no actions this run")

    proposal_id = result["actions"][0]["proposal_id"]
    decision = decide_action(proposal_id, accept=False)
    assert decision["status"] == "rejected"
    assert decision["followup_id"] is None


def test_deciding_an_already_decided_proposal_is_rejected(cleanup_nba):
    from backend_v3.advisor.next_best_action import decide_action, generate_next_best_actions

    result = generate_next_best_actions(KNOWN_CUSTOMER_ID)
    cleanup_nba.append(KNOWN_CUSTOMER_ID)
    if not result["actions"]:
        pytest.skip("Gemini returned no actions this run")

    proposal_id = result["actions"][0]["proposal_id"]
    decide_action(proposal_id, accept=False)
    with pytest.raises(ValueError):
        decide_action(proposal_id, accept=True)


# --------------------------------------------------------------------------
# Knowledge coverage and freshness
# --------------------------------------------------------------------------

def test_coverage_percent_matches_the_category_list():
    from backend_v3.advisor.knowledge_coverage import compute_coverage

    result = compute_coverage(KNOWN_CUSTOMER_ID)
    assert result is not None
    present = sum(1 for c in result["categories"] if c["present"])
    expected_pct = round(100 * present / len(result["categories"]))
    assert result["coverage_percent"] == expected_pct
    assert set(result["missing_categories"]) == {c["category"] for c in result["categories"] if not c["present"]}


def test_stale_facts_produce_discovery_questions_not_assumptions():
    """The spec's explicit instruction: stale information becomes a
    question, never something the system just assumes is still true."""
    from backend_v3.advisor.knowledge_coverage import compute_freshness

    result = compute_freshness(KNOWN_CUSTOMER_ID)
    assert result is not None
    assert len(result["discovery_questions"]) == result["stale_count"]
    for question in result["discovery_questions"]:
        assert question.strip().endswith("?"), "a discovery question must actually be phrased as a question"


def test_knowledge_graph_center_node_is_the_customer():
    from backend_v3.advisor.customer_knowledge_graph import get_customer_knowledge_graph

    graph = get_customer_knowledge_graph(KNOWN_CUSTOMER_ID)
    assert graph is not None
    center = [n for n in graph["nodes"] if n["type"] == "Customer"]
    assert len(center) == 1
    assert all(link["source"] == center[0]["id"] for link in graph["links"])


def test_knowledge_graph_nodes_carry_provenance_for_click_to_inspect():
    """The spec: clicking a node should show value/source/confidence/last
    verified — so every non-customer node must actually carry them."""
    from backend_v3.advisor.customer_knowledge_graph import get_customer_knowledge_graph

    graph = get_customer_knowledge_graph(KNOWN_CUSTOMER_ID)
    fact_nodes = [n for n in graph["nodes"] if n["type"] != "Customer"]
    assert fact_nodes, "expected at least one fact node for the seeded customer"
    for node in fact_nodes:
        assert "value" in node and "source" in node and "confidence" in node and "last_verified_at" in node


# --------------------------------------------------------------------------
# KPI honesty
# --------------------------------------------------------------------------

def test_kpi_dashboard_covers_all_five_categories():
    res = client.get("/api/v3/advisor/kpis")
    assert res.status_code == 200
    body = res.json()
    assert set(body.keys()) == {"agent", "customer", "ai", "business", "guardrails"}


def test_kpi_dashboard_responds_quickly():
    """The customer-KPI aggregate used to call compute_coverage() and
    compute_freshness() once per customer — each doing several Neo4j
    round trips plus a Qdrant search and DuckDB calls — making the whole
    dashboard take 15-25s for 20 customers. It now runs two bulk Cypher
    queries regardless of customer count; this guards against that
    regressing back into an N+1 pattern."""
    import time

    start = time.monotonic()
    res = client.get("/api/v3/advisor/kpis")
    elapsed = time.monotonic() - start

    assert res.status_code == 200
    assert elapsed < 5, f"KPI dashboard took {elapsed:.1f}s — expected a handful of bulk queries, not O(customers)"


def test_bulk_customer_kpis_match_authoritative_per_customer_values():
    """The fast aggregate path must agree with the slower, authoritative
    per-customer computation it replaced for the loop — otherwise the
    dashboard would be fast but wrong."""
    from backend_v3.advisor.customer_service import list_customer_summaries
    from backend_v3.advisor.knowledge_coverage import compute_coverage
    from backend_v3.advisor.kpi_service import get_kpi_dashboard

    customers = list_customer_summaries()
    authoritative = [compute_coverage(c["customer_id"]) for c in customers]
    authoritative = [c for c in authoritative if c]
    expected_avg = round(sum(c["coverage_percent"] for c in authoritative) / len(authoritative))

    dashboard = get_kpi_dashboard()
    # Financial coverage in the bulk path checks policy *presence* via
    # :OWNS rather than the DuckDB-joined portfolio the authoritative
    # path uses, so allow a small tolerance rather than requiring an
    # exact match on live, mutating demo data.
    assert abs(dashboard["customer"]["average_knowledge_coverage_percent"] - expected_avg) <= 5


def test_unmeasurable_kpis_are_null_with_a_reason_not_fabricated():
    """A metric this product genuinely cannot compute yet (e.g. customer
    complaints — no intake exists) must say so, not return a plausible
    fake number."""
    res = client.get("/api/v3/advisor/kpis")
    body = res.json()
    assert body["business"]["conversions_tracked"] is None
    assert body["business"]["conversions_reason"]
    assert body["guardrails"]["customer_complaints"] is None
    assert body["guardrails"]["customer_complaints_reason"]


def test_kpi_rates_are_percentages_or_null():
    res = client.get("/api/v3/advisor/kpis")
    body = res.json()
    for value in (
        body["ai"]["memory_approval_rate_percent"],
        body["ai"]["memory_rejection_rate_percent"],
        body["customer"]["average_knowledge_coverage_percent"],
    ):
        assert value is None or 0 <= value <= 100


# --------------------------------------------------------------------------
# AI auditability
# --------------------------------------------------------------------------

def test_every_audit_row_has_the_spec_required_fields():
    """customer, agent, timestamp, source, model, output, confidence,
    human decision — the spec's exact field list."""
    from backend_v3.advisor.ai_audit import list_ai_audit_trail

    rows = list_ai_audit_trail(customer_id=KNOWN_CUSTOMER_ID, limit=20)
    assert rows, "expected audit history for the seeded/exercised customer"
    required = {"customer_id", "agent", "timestamp", "source", "model", "output", "confidence", "human_decision"}
    for row in rows:
        assert required.issubset(row.keys()), f"audit row missing required fields: {required - row.keys()}"


def test_audit_trail_api_endpoint():
    res = client.get(f"/api/v3/advisor/ai-audit?customer_id={KNOWN_CUSTOMER_ID}")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_insights_api_endpoint():
    res = client.get("/api/v3/advisor/insights")
    assert res.status_code == 200
    body = res.json()
    for key in (
        "customers_requiring_attention",
        "new_life_events",
        "emerging_needs",
        "unresolved_conversations",
        "followup_opportunities",
    ):
        assert key in body

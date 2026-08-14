"""HTTP-layer tests: status codes and error handling for the advisor API."""
from conftest import KNOWN_CUSTOMER_ID, UNKNOWN_CUSTOMER_ID
from fastapi.testclient import TestClient

from backend_v3.api.main import app

client = TestClient(app)


def test_list_customers_returns_200_and_sorted_priority():
    res = client.get("/api/v3/advisor/customers")
    assert res.status_code == 200
    body = res.json()
    assert len(body) >= 10
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    ranks = [priority_rank[c["priority"]] for c in body]
    assert ranks == sorted(ranks), "customers must be sorted highest-priority first"


def test_get_customer_360_returns_200_for_known_customer():
    res = client.get(f"/api/v3/advisor/customers/{KNOWN_CUSTOMER_ID}")
    assert res.status_code == 200
    body = res.json()
    assert body["customer_id"] == KNOWN_CUSTOMER_ID
    assert "portfolio" in body and "family" in body


def test_get_customer_360_returns_404_for_unknown_customer():
    res = client.get(f"/api/v3/advisor/customers/{UNKNOWN_CUSTOMER_ID}")
    assert res.status_code == 404


def test_briefing_returns_404_for_unknown_customer():
    res = client.post(f"/api/v3/advisor/customers/{UNKNOWN_CUSTOMER_ID}/briefing")
    assert res.status_code == 404


def test_briefing_returns_200_and_structured_json_for_known_customer():
    res = client.post(f"/api/v3/advisor/customers/{KNOWN_CUSTOMER_ID}/briefing")
    assert res.status_code == 200
    body = res.json()
    for key in ("who_is_customer", "what_changed", "what_matters", "what_they_said",
                "what_to_remember", "suggested_questions", "potential_discussion_areas"):
        assert key in body


def test_upload_conversation_returns_400_for_empty_transcript():
    res = client.post(f"/api/v3/advisor/customers/{KNOWN_CUSTOMER_ID}/conversations", json={"transcript": "   "})
    assert res.status_code == 400


def test_upload_conversation_returns_404_for_unknown_customer():
    res = client.post(f"/api/v3/advisor/customers/{UNKNOWN_CUSTOMER_ID}/conversations", json={"transcript": "Hello, this is a test."})
    assert res.status_code == 404


def test_upload_conversation_returns_200_with_proposed_memories():
    res = client.post(
        f"/api/v3/advisor/customers/{KNOWN_CUSTOMER_ID}/conversations",
        json={"transcript": "Customer mentioned they are considering buying a second property next year."},
    )
    assert res.status_code == 200
    body = res.json()
    assert "conversation_id" in body
    assert "proposed_memories" in body


def test_approve_unknown_memory_returns_404():
    res = client.post("/api/v3/advisor/memories/does-not-exist/approve", json={})
    assert res.status_code == 404


def test_memory_timeline_and_conversation_history_return_200():
    assert client.get(f"/api/v3/advisor/customers/{KNOWN_CUSTOMER_ID}/memory-timeline").status_code == 200
    assert client.get(f"/api/v3/advisor/customers/{KNOWN_CUSTOMER_ID}/conversations").status_code == 200
    assert client.get(f"/api/v3/advisor/customers/{KNOWN_CUSTOMER_ID}/pending-memories").status_code == 200

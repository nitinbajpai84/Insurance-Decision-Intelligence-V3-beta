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

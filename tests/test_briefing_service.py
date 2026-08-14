"""
These two tests make a real Gemini call (no mocking framework is set up in
this project — see test_retrieval.py's docstring) so keep the count low;
prioritization/retrieval logic is covered by the faster tests elsewhere.
"""
from conftest import KNOWN_CUSTOMER_ID, UNKNOWN_CUSTOMER_ID

from backend_v3.advisor.briefing_service import prepare_meeting_briefing


def test_briefing_returns_none_for_unknown_customer():
    assert prepare_meeting_briefing(UNKNOWN_CUSTOMER_ID) is None


def test_briefing_has_the_required_grounded_and_generated_sections():
    briefing = prepare_meeting_briefing(KNOWN_CUSTOMER_ID)
    assert briefing is not None

    # Deterministic sections must be present and grounded regardless of
    # whether Gemini succeeded.
    for key in ("what_matters", "what_they_said", "what_to_remember", "portfolio", "family"):
        assert key in briefing

    if briefing["gemini_error"] is None:
        # Gemini succeeded -- verify the governance rules actually held.
        assert briefing["who_is_customer"]["value"]
        assert 0 <= len(briefing["suggested_questions"]) <= 5

        for item in briefing["what_changed"]:
            assert item["based_on"], "what_changed item has no evidence citation"
            assert item["priority"] in ("high", "medium", "low")

        for q in briefing["suggested_questions"]:
            assert q["based_on"], "suggested question has no evidence citation"

        for area in briefing["potential_discussion_areas"]:
            assert area["based_on"], "discussion area has no evidence citation"
            # Never a product-recommendation framing -- see the system
            # instruction in briefing_service.py rule #1.
            lowered = area["area"].lower()
            assert "sell" not in lowered and "recommend" not in lowered

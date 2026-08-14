"""
End-to-end Milestone 2 test: the exact business success test from the spec
-- upload a transcript mentioning a new education-related fact and a cost
increase, approve the extraction, and confirm the next Prepare for Meeting
briefing reflects it. Uses John Kemp (whose real daughter Ella is a
toddler, so the scenario is adapted to be age-coherent -- preschool costs
increasing rather than "university" -- while testing the identical
mechanics: extract -> approve -> Neo4j update -> briefing reflects it.
"""
from conftest import KNOWN_CUSTOMER_ID, UNKNOWN_CUSTOMER_ID

from backend_v3.advisor.briefing_service import prepare_meeting_briefing
from backend_v3.advisor.conversation_service import get_conversation_history, ingest_conversation
from backend_v3.advisor.memory_model import approve_memory

TEST_TRANSCRIPT = """
Advisor: How's everything with the family?

Customer: We've decided on a bilingual preschool program for our daughter starting next year.
The fees turned out to be about SGD 12,000 higher per year than we'd budgeted, so we need to
revisit our education savings plan for her.
"""


def test_ingest_conversation_raises_for_unknown_customer():
    try:
        ingest_conversation(UNKNOWN_CUSTOMER_ID, TEST_TRANSCRIPT)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_ingest_conversation_stores_transcript_and_extracts_items():
    result = ingest_conversation(KNOWN_CUSTOMER_ID, TEST_TRANSCRIPT)
    assert result["customer_id"] == KNOWN_CUSTOMER_ID
    assert result["chunks_stored"] >= 1
    assert result["summary"]
    assert len(result["proposed_memories"]) >= 1
    for mem in result["proposed_memories"]:
        assert mem["status"] == "pending"
        assert mem["evidence"]
        assert 0.0 <= mem["confidence"] <= 1.0

    history = get_conversation_history(KNOWN_CUSTOMER_ID)
    assert any(h["conversation_id"] == result["conversation_id"] for h in history)


# goal/need/concern pass through retrieval.py -> briefing_service.py
# verbatim (no Gemini paraphrasing), so an exact-match assertion is
# reliable. life_event instead gets summarized into what_changed by
# Gemini, so it's excluded here -- that path is covered qualitatively by
# test_memory_model.py's promotion test instead.
VERBATIM_TYPES = {"goal": "goals", "need": "needs", "concern": "concerns"}


def _descriptions_in_briefing(briefing, memory_type: str) -> set[str]:
    section = VERBATIM_TYPES[memory_type]
    if section == "concerns":
        return {c["topic"] for c in briefing["what_to_remember"]["concerns"]}
    return {n["description"] for n in briefing["what_matters"][section]}


def test_success_scenario_approved_memory_appears_in_next_briefing():
    """The literal business success test: extract -> approve -> briefing
    reflects it, without any changes to Milestone 1's briefing_service.py
    or retrieval.py -- proving the shared-node-shape design worked.

    Gemini's classification of "we need to revisit our education savings
    plan" as need vs. goal vs. concern isn't perfectly deterministic across
    calls, so this accepts any of the three rather than requiring exactly
    "need" -- what matters for the business test is that SOMETHING got
    extracted, approved, and reflected in the next briefing."""
    result = ingest_conversation(KNOWN_CUSTOMER_ID, TEST_TRANSCRIPT)
    candidates = [m for m in result["proposed_memories"] if m["memory_type"] in VERBATIM_TYPES]
    assert len(candidates) >= 1, f"expected at least one goal/need/concern, got: {result['proposed_memories']}"

    target = candidates[0]
    approved = approve_memory(target["memory_id"])
    assert approved["promoted"] is True

    after = prepare_meeting_briefing(KNOWN_CUSTOMER_ID)
    after_values = _descriptions_in_briefing(after, target["memory_type"])
    assert approved["value"] in after_values

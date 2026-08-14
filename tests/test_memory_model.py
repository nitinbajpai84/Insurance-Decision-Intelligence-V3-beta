"""
Tests for the Milestone 2 Customer Memory model: create/approve/reject/edit,
conflict detection, and that promotion writes provenance consistent with
what retrieval.py expects (this is the exact bug class found during manual
browser testing -- a native Neo4j Date type slipping into a property that
every other write path stores as a plain string).
"""
import uuid

from conftest import KNOWN_CUSTOMER_ID

from backend_v3.advisor.memory_model import (
    approve_memory,
    check_conflict,
    create_pending_memory,
    get_memory_timeline,
    get_pending_memories,
    reject_memory,
)
from backend_v3.advisor.retrieval import get_customer_graph


def _fresh_memory(memory_type="concern", value=None, category=None):
    value = value or f"test memory {uuid.uuid4()}"
    return create_pending_memory(
        customer_id=KNOWN_CUSTOMER_ID,
        memory_type=memory_type,
        value=value,
        evidence="test evidence quote",
        confidence=0.85,
        conversation_id=str(uuid.uuid4()),
        category=category,
    ), value


def test_create_pending_memory_appears_in_pending_list():
    mem, value = _fresh_memory()
    pending = get_pending_memories(KNOWN_CUSTOMER_ID, status="pending")
    assert any(p["memory_id"] == mem["memory_id"] and p["value"] == value for p in pending)


def test_check_conflict_detects_same_category_need():
    # John Kemp's seed data has a Need with category "Protection".
    conflict = check_conflict(KNOWN_CUSTOMER_ID, "need", "Protection")
    assert conflict is not None
    assert "protection" in conflict["category"].lower()


def test_check_conflict_none_for_unrelated_category():
    conflict = check_conflict(KNOWN_CUSTOMER_ID, "need", "TotallyUnrelatedCategoryXYZ")
    assert conflict is None


def test_check_conflict_only_applies_to_goal_and_need():
    # life_event/concern don't have a "category conflict" concept in this
    # model -- events accumulate, they don't overwrite each other.
    assert check_conflict(KNOWN_CUSTOMER_ID, "life_event", "career") is None
    assert check_conflict(KNOWN_CUSTOMER_ID, "concern", "Protection") is None


def test_reject_marks_status_and_writes_no_graph_fact():
    mem, value = _fresh_memory(memory_type="need", value=f"rejected need {uuid.uuid4()}", category="test_category_reject")
    reject_memory(mem["memory_id"])

    timeline = get_memory_timeline(KNOWN_CUSTOMER_ID)
    entry = next(t for t in timeline if t["memory_id"] == mem["memory_id"])
    assert entry["status"] == "rejected"

    graph = get_customer_graph(KNOWN_CUSTOMER_ID)
    assert not any(n["description"] == value for n in graph["needs"])


def test_approve_promotes_need_into_real_graph_fact_with_provenance():
    mem, value = _fresh_memory(memory_type="need", value=f"approved need {uuid.uuid4()}", category="test_category_approve")
    result = approve_memory(mem["memory_id"])
    assert result["status"] == "accepted"
    assert result["promoted"] is True

    graph = get_customer_graph(KNOWN_CUSTOMER_ID)
    matching = [n for n in graph["needs"] if n["description"] == value]
    assert len(matching) == 1
    assert matching[0]["source"].startswith("conversation_")
    assert matching[0]["confidence"] == 0.85


def test_approve_with_edited_value_uses_the_edit_not_the_original():
    mem, original_value = _fresh_memory(memory_type="concern", value=f"original {uuid.uuid4()}")
    edited_value = f"edited {uuid.uuid4()}"
    result = approve_memory(mem["memory_id"], edited_value=edited_value)
    assert result["status"] == "edited"
    assert result["value"] == edited_value

    graph = get_customer_graph(KNOWN_CUSTOMER_ID)
    topics = {t["topic"] for t in graph["concerns"]}
    assert edited_value in topics
    assert original_value not in topics


def test_promoted_life_event_date_is_a_plain_string_not_a_neo4j_native_type():
    """Regression test for the bug found during manual testing: a native
    Neo4j Date type in LifeEvent.date crashed prioritization.py's date
    parsing (and, separately, broke JSON serialization for Conversation.date
    in conversation_service.py) because every other write path in this
    codebase stores dates as plain strings."""
    mem, value = _fresh_memory(memory_type="life_event", value=f"life event {uuid.uuid4()}")
    approve_memory(mem["memory_id"])

    graph = get_customer_graph(KNOWN_CUSTOMER_ID)
    matching = [e for e in graph["life_events"] if e["description"] == value]
    assert len(matching) == 1
    assert isinstance(matching[0]["date"], str)


def test_preference_and_commitment_types_are_not_promoted_to_graph_nodes():
    # per memory_model.py's _PROMOTABLE set -- these stay PendingMemory-only.
    mem, value = _fresh_memory(memory_type="preference", value=f"preference {uuid.uuid4()}")
    result = approve_memory(mem["memory_id"])
    assert result["promoted"] is False

"""
Stage 3 tests: follow-up lifecycle, meeting history, and the My Day
before/during/after panels.

These run against live Neo4j (this project's established convention —
see conftest.py's cleanup fixture), using a customer already seeded by
synthetic_data.py so briefing/retrieval code paths are exercised for
real.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend_v3.api.main import app
from conftest import KNOWN_CUSTOMER_ID

client = TestClient(app)


@pytest.fixture
def cleanup_followup():
    created_ids: list[str] = []
    yield created_ids
    from backend_v3.graph_store.neo4j_client import run_write

    for followup_id in created_ids:
        run_write("MATCH (f:FollowUp {followup_id: $id}) DETACH DELETE f", {"id": followup_id})


# --------------------------------------------------------------------------
# Follow-up lifecycle
# --------------------------------------------------------------------------

def test_followup_create_edit_complete_reopen_cycle(cleanup_followup):
    from backend_v3.advisor.followups import complete_followup, create_followup, reopen_followup, update_followup

    followup = create_followup(
        customer_id=KNOWN_CUSTOMER_ID,
        title=f"test followup {uuid.uuid4()}",
        source="conversation_test",
        due_date="2026-08-20",
    )
    cleanup_followup.append(followup["followup_id"])
    assert followup["status"] == "open"
    assert followup["due_date"] == "2026-08-20"

    updated = update_followup(followup["followup_id"], due_date="2026-09-01", assigned_to="senior_advisor")
    assert updated["due_date"] == "2026-09-01"
    assert updated["assigned_to"] == "senior_advisor"

    completed = complete_followup(followup["followup_id"])
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None

    reopened = reopen_followup(followup["followup_id"])
    assert reopened["status"] == "open"
    assert reopened["completed_at"] is None


def test_overdue_followup_detection(cleanup_followup):
    from backend_v3.advisor.followups import create_followup, list_followups

    overdue = create_followup(
        customer_id=KNOWN_CUSTOMER_ID,
        title=f"test overdue {uuid.uuid4()}",
        source="conversation_test",
        due_date="2020-01-01",
    )
    future = create_followup(
        customer_id=KNOWN_CUSTOMER_ID,
        title=f"test future {uuid.uuid4()}",
        source="conversation_test",
        due_date="2099-01-01",
    )
    cleanup_followup.extend([overdue["followup_id"], future["followup_id"]])

    overdue_ids = {f["followup_id"] for f in list_followups(overdue_only=True)}
    assert overdue["followup_id"] in overdue_ids
    assert future["followup_id"] not in overdue_ids


def test_follow_up_memory_type_promotes_to_a_real_followup_not_a_generic_fact(cleanup_followup):
    """The spec's "assign / due date / complete" only makes sense on a
    dedicated entity — confirm approval actually creates one rather than
    silently discarding a follow_up proposal like the pre-Stage-3 code did."""
    from backend_v3.advisor.memory_model import approve_memory, create_pending_memory

    memory = create_pending_memory(
        customer_id=KNOWN_CUSTOMER_ID,
        memory_type="follow_up",
        value=f"test follow-up promotion {uuid.uuid4()}",
        evidence="advisor and customer agreed to follow up",
        confidence=0.9,
        conversation_id="test",
    )
    result = approve_memory(memory["memory_id"])
    assert result["promoted"] is True
    assert result["followup_id"] is not None
    cleanup_followup.append(result["followup_id"])

    from backend_v3.advisor.followups import get_followup

    followup = get_followup(result["followup_id"])
    assert followup is not None
    assert followup["due_date"]  # a default was applied, not left blank


def test_followup_api_endpoints(cleanup_followup):
    res = client.get(f"/api/v3/advisor/customers/{KNOWN_CUSTOMER_ID}/follow-ups")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.get("/api/v3/advisor/follow-ups?overdue=true")
    assert res.status_code == 200


def test_completing_unknown_followup_returns_404():
    res = client.post("/api/v3/advisor/follow-ups/does-not-exist/complete")
    assert res.status_code == 404


# --------------------------------------------------------------------------
# Meeting History
# --------------------------------------------------------------------------

def test_meeting_history_joins_conversation_to_insights_and_changes():
    from backend_v3.advisor.meeting_history import get_meeting_history

    timeline = get_meeting_history(KNOWN_CUSTOMER_ID)
    assert isinstance(timeline, list)
    # Every entry must expose the four things the spec asks for.
    for entry in timeline[:3]:
        assert "summary" in entry
        assert "insights" in entry
        assert "memory_changes" in entry
        assert "follow_ups" in entry


def test_meeting_history_api_endpoint():
    res = client.get(f"/api/v3/advisor/customers/{KNOWN_CUSTOMER_ID}/meeting-history")
    assert res.status_code == 200


# --------------------------------------------------------------------------
# My Day meeting lifecycle
# --------------------------------------------------------------------------

def test_my_day_exposes_all_four_lifecycle_panels():
    res = client.get("/api/v3/advisor/my-day")
    assert res.status_code == 200
    body = res.json()

    for key in (
        "meetings_requiring_preparation",
        "meetings_awaiting_processing",
        "memory_updates_awaiting_approval",
        "overdue_followups",
    ):
        assert key in body, f"My Day is missing the '{key}' panel"
        assert key in body["summary"], f"My Day summary is missing the '{key}' count"
        # Panels cap at 8 items (the pattern every other My Day panel
        # uses); the summary count is the uncapped total, so it may be
        # larger but never smaller than what's shown.
        assert body["summary"][key] >= len(body[key])
        assert len(body[key]) <= 8


def test_preparing_a_meeting_removes_customer_from_requiring_preparation():
    """The whole point of tracking last_prepared_date: generating a
    briefing should make 'requiring preparation' shrink, not stay static."""
    from backend_v3.advisor.agent_service import get_my_day
    from backend_v3.advisor.briefing_service import prepare_meeting_briefing

    prepare_meeting_briefing(KNOWN_CUSTOMER_ID)
    day = get_my_day()
    still_pending = {m["customer_id"] for m in day["meetings_requiring_preparation"]}
    assert KNOWN_CUSTOMER_ID not in still_pending


# --------------------------------------------------------------------------
# Conversation source type (transcript vs notes)
# --------------------------------------------------------------------------

def test_meeting_notes_are_a_distinct_interaction_type_from_transcript():
    from backend_v3.advisor.conversation_service import ingest_conversation

    result = ingest_conversation(
        KNOWN_CUSTOMER_ID,
        "Quick note: customer mentioned interest in reviewing beneficiaries next quarter.",
        interaction_type="notes",
    )

    from backend_v3.graph_store.neo4j_client import run_query, run_write

    try:
        rows = run_query(
            "MATCH (conv:Conversation {conversation_id: $id}) RETURN conv.interaction_type AS t",
            {"id": result["conversation_id"]},
        )
        assert rows[0]["t"] == "notes"
    finally:
        run_write(
            "MATCH (c:Customer)-[:HAS_PENDING_MEMORY]->(m:PendingMemory) "
            "WHERE m.source = $source DETACH DELETE m",
            {"source": f"conversation_{result['conversation_id']}"},
        )
        run_write(
            "MATCH (conv:Conversation {conversation_id: $id}) DETACH DELETE conv",
            {"id": result["conversation_id"]},
        )


def test_invalid_interaction_type_is_rejected():
    from backend_v3.advisor.conversation_service import ingest_conversation

    with pytest.raises(ValueError):
        ingest_conversation(KNOWN_CUSTOMER_ID, "some text", interaction_type="video")

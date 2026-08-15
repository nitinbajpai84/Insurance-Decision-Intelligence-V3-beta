"""
Stage 2 tests: identity resolution, CSV validation, calendar parsing, and
the honesty guarantees of the Connection Center.

Like the rest of this suite these run against the live Neo4j/Qdrant
instance rather than mocks, so anything written here uses an obviously
disposable namespace and is cleaned up in a fixture.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend_v3.api.main import app

client = TestClient(app)

TEST_PREFIX = "stage2test"


@pytest.fixture(scope="module", autouse=True)
def cleanup_stage2_artifacts():
    """Remove anything this module wrote, so a test run never leaves data
    visible in the demo (a real risk with live-infrastructure testing)."""
    yield
    from backend_v3.graph_store.neo4j_client import run_write

    run_write(
        "MATCH (n) WHERE n.source_system = $source OR n.customer_id STARTS WITH $prefix "
        "DETACH DELETE n",
        {"source": TEST_PREFIX, "prefix": f"{TEST_PREFIX}_"},
    )
    run_write(
        "MATCH (i:CustomerIdentity) WHERE i.customer_id STARTS WITH $prefix DETACH DELETE i",
        {"prefix": f"{TEST_PREFIX}_"},
    )
    # register_identity() merges a CustomerIdentity onto the REAL seeded
    # customer under test (e.g. John Kemp), not a stage2test_-prefixed
    # one — the two matches above miss it entirely, since neither its
    # properties nor its customer_id carry the test prefix. Only the
    # HAS_IDENTITY relationship's `source` does.
    run_write(
        "MATCH (:Customer)-[r:HAS_IDENTITY {source: $source}]->(i:CustomerIdentity) DETACH DELETE i",
        {"source": TEST_PREFIX},
    )
    run_write(
        "MATCH (i:CustomerIdentity) WHERE i.value_raw STARTS WITH $prefix "
        "   OR i.value_normalized STARTS WITH $prefix "
        "DETACH DELETE i",
        {"prefix": TEST_PREFIX},
    )
    run_write("MATCH (c:Connection {provider: $p}) DETACH DELETE c", {"p": TEST_PREFIX})
    # Family members merge onto the real seeded customer (like the
    # CustomerIdentity case above), so only their own name carries the
    # test prefix.
    run_write(
        "MATCH (f:FamilyMember) WHERE f.name STARTS WITH $prefix DETACH DELETE f",
        {"prefix": TEST_PREFIX},
    )


# --------------------------------------------------------------------------
# Identity resolution
# --------------------------------------------------------------------------

def test_email_and_phone_normalization_converges_on_one_value():
    from backend_v3.integrations.identity import normalize_email, normalize_phone

    assert normalize_email("  John.Kemp@Example.COM ") == "john.kemp@example.com"
    # The same Singapore number written three ways must collapse to one key.
    assert normalize_phone("+65 9123 4567") == normalize_phone("6591234567") == "6591234567"


def test_unmatched_identity_is_never_silently_resolved():
    """The core safety property: no deterministic key means no auto-match."""
    from backend_v3.integrations.identity import resolve_identity

    result = resolve_identity(email=f"nobody-{uuid.uuid4()}@example.com", source_system=TEST_PREFIX)
    assert result.resolved is False
    assert result.customer_id is None
    assert "match required" in result.reason.lower()


def test_registered_identity_then_resolves_deterministically():
    from backend_v3.advisor.customer_service import list_customer_summaries
    from backend_v3.integrations.identity import register_identity, resolve_identity

    customer_id = list_customer_summaries()[0]["customer_id"]
    address = f"{TEST_PREFIX}-{uuid.uuid4()}@example.com"

    assert resolve_identity(email=address, source_system=TEST_PREFIX).resolved is False
    register_identity(customer_id, "email", address, TEST_PREFIX)

    after = resolve_identity(email=address, source_system=TEST_PREFIX)
    assert after.resolved is True
    assert after.customer_id == customer_id
    assert after.confidence == 1.0


def test_name_only_match_proposes_but_does_not_resolve():
    """A shared name is not evidence of identity."""
    from backend_v3.advisor.customer_service import list_customer_summaries
    from backend_v3.integrations.identity import resolve_identity

    name = list_customer_summaries()[0]["name"]
    result = resolve_identity(name=name, source_system=TEST_PREFIX)

    assert result.resolved is False, "a name alone must never auto-bind a customer"
    assert result.candidates, "the matching customer should still be offered as a candidate"
    assert result.candidates[0].confidence < 1.0


# --------------------------------------------------------------------------
# CSV import
# --------------------------------------------------------------------------

CSV_HEADER = b"external_id,full_name,email\n"


def test_preview_reports_errors_and_duplicates_without_writing():
    from backend_v3.graph_store.neo4j_client import run_query
    from backend_v3.integrations.csv_import import preview

    content = CSV_HEADER + (
        b"S2-1,Valid Person,valid@example.com\n"
        b"S2-1,Duplicate Row,dupe@example.com\n"
        b",Missing Id,noid@example.com\n"
        b"S2-3,Bad Email,not-an-email\n"
    )
    result = preview(content, "t.csv", "customers")

    assert result["valid_count"] == 1
    assert result["duplicate_count"] == 1
    assert result["error_count"] == 2  # missing id + malformed email
    assert result["committed"] is False

    written = run_query(
        "MATCH (c:Customer) WHERE c.name = 'Valid Person' RETURN count(c) AS c", {}
    )[0]["c"]
    assert written == 0, "preview must not write anything to the graph"


def test_missing_required_column_is_rejected_with_a_useful_message():
    from backend_v3.integrations.csv_import import ImportError_, preview

    with pytest.raises(ImportError_) as exc:
        preview(b"name,email\nJane,j@example.com\n", "t.csv", "customers")
    assert "external_id" in str(exc.value)


def test_header_aliases_are_accepted():
    """Real advisor exports do not agree on column names."""
    from backend_v3.integrations.csv_import import preview

    result = preview(
        b"Customer ID,Customer Name,E-Mail\nS2-9,Alias Person,alias@example.com\n",
        "t.csv",
        "customers",
    )
    assert result["valid_count"] == 1


# --------------------------------------------------------------------------
# Calendar parsing
# --------------------------------------------------------------------------

ICS = b"""BEGIN:VCALENDAR
BEGIN:VEVENT
UID:stage2-evt-1
SUMMARY:Review with Someone
DTSTART:20260815T020000Z
DTEND:20260815T030000Z
ORGANIZER:mailto:advisor@example.com
ATTENDEE;CN=Someone:mailto:someone@example.com
DESCRIPTION:Join https://zoom.us/j/123456
END:VEVENT
END:VCALENDAR
"""


def test_ics_parsing_extracts_the_fields_my_day_needs():
    from backend_v3.integrations.calendar_sources import parse_ics

    meetings = parse_ics(ICS, "t.ics")
    assert len(meetings) == 1
    meeting = meetings[0]
    assert meeting.external_id == "stage2-evt-1"
    assert meeting.title == "Review with Someone"
    # Stage 3: the CN display name is preserved as "Name <email>" so a
    # customer with no email on file can still produce a name candidate
    # for "Customer match required." — see calendar_sources._CN_PATTERN.
    assert meeting.attendees == ["Someone <someone@example.com>"]
    assert meeting.organizer == "advisor@example.com"
    assert meeting.meeting_link and "zoom.us" in meeting.meeting_link
    assert meeting.provenance and meeting.provenance.source_system == "ics"


def test_meeting_time_renders_in_the_advisor_timezone_not_utc():
    """A 02:00 UTC start is a 10:00 Singapore meeting; showing 2:00 AM
    would make My Day wrong for every advisor in the target market."""
    from backend_v3.integrations.timeutil import local_date, local_time_label

    assert local_time_label("2026-08-15T02:00:00+00:00") == "10:00 AM"
    # 23:00 UTC is already the next day locally.
    assert local_date("2026-08-14T23:00:00+00:00") == "2026-08-15"


# --------------------------------------------------------------------------
# Connection Center honesty
# --------------------------------------------------------------------------

def test_no_provider_claims_connected_without_a_real_connection_record():
    from backend_v3.advisor.integration_service import connection_center
    from backend_v3.integrations.connection_store import list_connections as stored

    real = {key for key, row in stored().items() if row.get("status") == "connected"}
    for group in connection_center():
        for provider in group["providers"]:
            if provider["connected"]:
                assert provider["provider"] in real, (
                    f"{provider['name']} reports connected with no connection record"
                )


def test_architecture_only_providers_cannot_be_connected_or_synced():
    from backend_v3.advisor.integration_service import connection_center

    for group in connection_center():
        for provider in group["providers"]:
            if provider["implementation"] == "architecture":
                assert provider["actions"]["connect"] is False
                assert provider["actions"]["sync_now"] is False
                assert provider["blocked_reason"]


def test_connecting_an_architecture_only_provider_is_refused():
    res = client.post("/api/v3/integrations/zoom/connect")
    assert res.status_code == 409
    assert "ingestion implementation" in res.json()["detail"]


def test_connection_center_exposes_every_stage2_category():
    res = client.get("/api/v3/integrations")
    assert res.status_code == 200
    categories = {group["category"] for group in res.json()}
    assert categories == {"Customer Data", "Calendar", "Meetings", "Communication", "Files"}


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------

def test_imported_family_member_appears_in_customer_graph():
    """upsert_contact's write shape must match synthetic_data.py's seed
    pattern exactly (:FamilyMember / :HAS_FAMILY_MEMBER) — a mismatch
    would make an imported family member disappear from Customer 360
    despite the import itself reporting success."""
    from backend_v3.advisor.customer_service import list_customer_summaries
    from backend_v3.advisor.retrieval import get_customer_graph
    from backend_v3.integrations.identity import register_identity
    from backend_v3.integrations.models import NormalizedContact, Provenance
    from backend_v3.integrations.pipeline import upsert_contact

    customer_id = list_customer_summaries()[0]["customer_id"]
    name = f"{TEST_PREFIX} spouse {uuid.uuid4()}"

    # upsert_contact resolves customer_external_id through identity
    # matching, same as any other source — give it a deterministic key
    # rather than relying on the mangled-ID fallback.
    register_identity(customer_id, "external_id", customer_id, TEST_PREFIX)

    result = upsert_contact(
        NormalizedContact(
            customer_external_id=customer_id,
            full_name=name,
            relationship="spouse",
            provenance=Provenance(TEST_PREFIX, name, "test"),
        )
    )
    assert result["written"] is True

    graph = get_customer_graph(customer_id)
    assert any(f["name"] == name and f["relationship"] == "spouse" for f in graph["family"])


def test_imported_policy_appears_in_customer_portfolio():
    """Same class of bug as the family-member case above: upsert_policy
    must write :OWNS (not a different relationship type) for
    retrieval.get_portfolio() to ever discover the policy_id at all —
    and even once discovered, a policy with no DuckDB row (every CSV
    import) needs the Neo4j-node fallback or its premium/status would
    still be silently blank."""
    from backend_v3.advisor.retrieval import assemble_customer_context
    from backend_v3.advisor.customer_service import list_customer_summaries
    from backend_v3.integrations.identity import register_identity
    from backend_v3.integrations.models import NormalizedPolicy, Provenance
    from backend_v3.integrations.pipeline import upsert_policy

    customer_id = list_customer_summaries()[0]["customer_id"]
    policy_id = f"{TEST_PREFIX}-POL-{uuid.uuid4()}"
    register_identity(customer_id, "external_id", customer_id, TEST_PREFIX)

    result = upsert_policy(
        NormalizedPolicy(
            customer_external_id=customer_id,
            policy_id=policy_id,
            product_name="Test Policy",
            line_of_business="Test LOB",
            annual_premium=1234.0,
            policy_status="active",
            provenance=Provenance(TEST_PREFIX, policy_id, "test"),
        )
    )
    assert result["written"] is True

    ctx = assemble_customer_context(customer_id)
    match = next((p for p in ctx["portfolio"] if p["policy_id"] == policy_id), None)
    assert match is not None, "imported policy did not surface in the portfolio"
    assert match["annual_premium"] == 1234.0
    assert match["policy_status"] == "active"

    from backend_v3.graph_store.neo4j_client import run_write

    run_write("MATCH (:Customer)-[r:OWNS]->(p:Policy {policy_id: $id}) DELETE r, p", {"id": policy_id})


def test_every_imported_record_carries_full_provenance():
    from backend_v3.integrations.models import Provenance

    provenance = Provenance(
        source_system="csv", source_id="ADV-1", original_reference="file.csv:row2"
    )
    props = provenance.as_properties()
    for required in ("source_system", "source_id", "original_reference", "imported_at"):
        assert props[required], f"{required} must be populated on every imported item"


def test_my_day_reports_customer_meeting_count_and_flags_unmatched():
    res = client.get("/api/v3/advisor/my-day")
    assert res.status_code == 200
    body = res.json()

    assert "meetings_message" in body
    assert body["meetings_message"].startswith("You have ")
    assert body["meetings_message"].endswith("customer meetings today.")

    # Every meeting is either matched to a customer or explicitly flagged.
    for meeting in body["calendar_meetings_today"]:
        if meeting["match_status"] == "matched":
            assert meeting["customer_id"]
            assert meeting["match_label"].startswith("Customer match:")
        else:
            assert meeting["customer_id"] is None
            assert meeting["match_label"] == "Customer match required."

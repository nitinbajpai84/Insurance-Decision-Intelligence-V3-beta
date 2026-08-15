"""
Account-provider tests: unified consent, least privilege, credential
handling, and the CRM connector tier split.

The security properties here are the ones worth guarding — a regression
that leaks a client secret or silently widens OAuth scope would not be
obvious from the UI.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend_v3.api.main import app

client = TestClient(app)

TEST_ACCOUNT = "google"


@pytest.fixture(autouse=True)
def clear_test_credentials():
    """Never leave test credentials behind — they would make the
    Connection Center claim Google is configured."""
    yield
    try:
        from backend_v3.integrations.credentials import delete_credentials

        delete_credentials(TEST_ACCOUNT)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Account model
# --------------------------------------------------------------------------

def test_each_capability_belongs_to_exactly_one_account():
    """A capability owned by two accounts would mean two credentials
    fighting over the same connection."""
    from backend_v3.integrations.accounts import ACCOUNT_PROVIDERS

    seen: dict[str, str] = {}
    for account in ACCOUNT_PROVIDERS:
        for capability in account.capabilities:
            assert capability not in seen, (
                f"{capability} is claimed by both {seen.get(capability)} and {account.key}"
            )
            seen[capability] = account.key


def test_account_capabilities_all_exist_in_the_registry():
    from backend_v3.integrations.accounts import ACCOUNT_PROVIDERS
    from backend_v3.integrations.registry import get_provider

    for account in ACCOUNT_PROVIDERS:
        for capability in account.capabilities:
            get_provider(capability)  # raises KeyError if the wiring drifts


def test_the_seven_requested_systems_are_all_reachable_through_an_account():
    from backend_v3.integrations.accounts import account_for_capability

    expected = {
        "google_calendar": "google",
        "gmail": "google",
        "google_drive": "google",
        "m365_email": "microsoft",
        "onedrive": "microsoft",
        "sharepoint": "microsoft",
        "whatsapp_business": "meta",
    }
    for capability, account_key in expected.items():
        account = account_for_capability(capability)
        assert account is not None, f"{capability} has no owning account"
        assert account.key == account_key


def test_requested_scopes_are_read_only():
    """A write scope slipping in would let the product modify an
    advisor's mailbox or calendar."""
    from backend_v3.integrations.registry import PROVIDERS

    forbidden = ("readwrite", ".send", "compose", ".modify", "full_control", "write")
    for provider in PROVIDERS:
        for scope in provider.scopes:
            lowered = scope.lower()
            assert not any(bad in lowered for bad in forbidden), (
                f"{provider.name} requests a non-read-only scope: {scope}"
            )


# --------------------------------------------------------------------------
# Least privilege
# --------------------------------------------------------------------------

def test_scopes_cover_only_the_enabled_capabilities():
    from backend_v3.integrations.accounts import GOOGLE, scopes_for

    calendar_only = scopes_for(GOOGLE, ["google_calendar"])
    assert calendar_only == ["https://www.googleapis.com/auth/calendar.events.readonly"]
    assert not any("gmail" in s for s in calendar_only), "mailbox access must not be requested for calendar sync"

    with_mail = scopes_for(GOOGLE, ["google_calendar", "gmail"])
    assert any("gmail" in s for s in with_mail)


def test_microsoft_requests_offline_access_for_refresh():
    from backend_v3.integrations.accounts import MICROSOFT, scopes_for

    assert "offline_access" in scopes_for(MICROSOFT, ["outlook_calendar"])


def test_unknown_capability_cannot_smuggle_in_scopes():
    from backend_v3.integrations.accounts import GOOGLE, scopes_for

    assert scopes_for(GOOGLE, ["sharepoint"]) == [], "a capability from another account must contribute nothing"


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------

def test_saved_secret_is_never_returned_only_masked():
    from backend_v3.integrations.credentials import credential_status, save_credentials
    from backend_v3.integrations.token_store import encryption_available

    if not encryption_available():
        pytest.skip("INTEGRATION_ENCRYPTION_KEY not configured in this environment")

    secret = "GOCSPX-supersecretvalue123"
    save_credentials(TEST_ACCOUNT, {"client_id": "abc.apps.googleusercontent.com", "client_secret": secret})

    status = credential_status(TEST_ACCOUNT)
    assert status["configured"] is True
    assert secret not in str(status), "the raw secret must never appear in an API-facing payload"
    assert status["hints"]["client_secret"] != secret
    assert "•" in status["hints"]["client_secret"]


def test_incomplete_credentials_are_rejected():
    from backend_v3.integrations.credentials import save_credentials
    from backend_v3.integrations.token_store import encryption_available

    if not encryption_available():
        pytest.skip("INTEGRATION_ENCRYPTION_KEY not configured in this environment")

    with pytest.raises(ValueError) as exc:
        save_credentials(TEST_ACCOUNT, {"client_id": "only-the-id"})
    assert "Client secret" in str(exc.value)


def test_account_api_never_exposes_a_secret_field():
    res = client.get("/api/v3/integrations/accounts")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 3
    for account in body:
        # The field *specification* is present; a stored value is not.
        assert "credential_fields" in account
        assert "client_secret" not in {k for k in account.keys()}


def test_connecting_without_credentials_is_refused_not_faked():
    res = client.post("/api/v3/integrations/accounts/google/connect", json={"capabilities": None})
    assert res.status_code == 409
    assert "credentials" in res.json()["detail"].lower()


# --------------------------------------------------------------------------
# CRM
# --------------------------------------------------------------------------

def test_all_seven_requested_crms_are_registered():
    res = client.get("/api/v3/integrations/crm")
    assert res.status_code == 200
    names = {row["name"] for row in res.json()}
    assert names == {
        "AgencyZoom",
        "Applied Epic",
        "EZLynx",
        "Salesforce",
        "HawkSoft",
        "InsuredMine",
        "HubSpot",
    }


def test_crm_tiers_are_labelled_honestly():
    """Partner-gated vendors must not be presented as self-serve, and each
    must offer the CSV path that genuinely works today."""
    res = client.get("/api/v3/integrations/crm")
    rows = {row["name"]: row for row in res.json()}

    assert rows["Salesforce"]["access"] == "self_serve_oauth"
    assert rows["HubSpot"]["access"] == "self_serve_oauth"
    for name in ("AgencyZoom", "Applied Epic", "EZLynx", "HawkSoft", "InsuredMine"):
        assert rows[name]["access"] == "partner_gated"
        assert rows[name]["csv_export_hint"], f"{name} should tell the advisor how to export CSV"


def test_partner_gated_crm_without_credentials_explains_the_csv_path():
    res = client.post("/api/v3/integrations/crm/hawksoft/connect")
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert "CSV" in detail


def test_no_crm_reports_connected_before_setup():
    res = client.get("/api/v3/integrations/crm")
    for row in res.json():
        if not row["credentials_configured"]:
            assert row["connected"] is False

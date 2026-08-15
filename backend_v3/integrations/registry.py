"""
Provider registry — the single source of truth for what this product can
actually do with each external system.

`implementation` is deliberately blunt, because the alternative is a demo
that lies:

  "live"          real ingestion exists and runs today with no third-party
                  credential (file-based sources).
  "credentialed"  real ingestion code exists and runs as soon as OAuth
                  credentials are configured. Until then the provider
                  reports not_connected and `missing_config` explains why.
  "architecture"  connector interface, scopes, and data contract are
                  defined, but no ingestion runs yet.

Nothing in the API may report a provider as connected unless a real
connection record exists for it. See connection_store.py.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

LIVE = "live"
CREDENTIALED = "credentialed"
ARCHITECTURE = "architecture"


@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    category: str
    implementation: str
    auth: str
    # Environment variables that must be set before a credentialed
    # provider can connect. Presence is checked, values are never read
    # into API responses.
    required_env: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    notes: str = ""

    def missing_config(self) -> list[str]:
        """What still has to be supplied before this provider can connect.

        Credentials may arrive two ways: environment variables (operator
        managed) or the in-app setup screen. Providers that belong to an
        account provider defer to it, since the whole group shares one
        credential and one consent.
        """
        from backend_v3.integrations.accounts import account_for_capability

        account = account_for_capability(self.key)
        if account is not None:
            from backend_v3.integrations.credentials import credential_status

            try:
                status = credential_status(account.key)
            except Exception:
                return [f"{account.name} credentials"]
            return [] if status["configured"] else [f"{account.name} credentials"]

        if self.key.startswith("crm_"):
            from backend_v3.integrations.credentials import credential_status

            try:
                status = credential_status(self.key)
            except Exception:
                return [f"{self.name} credentials"]
            return [] if status["configured"] else [f"{self.name} credentials"]

        return [name for name in self.required_env if not os.environ.get(name, "").strip()]

    def is_configurable(self) -> bool:
        """True when this provider could be connected right now."""
        if self.implementation == LIVE:
            return True
        if self.implementation == CREDENTIALED:
            return not self.missing_config()
        return False


PROVIDERS: tuple[Provider, ...] = (
    # --- 1. Customer data ---------------------------------------------------
    Provider(
        key="csv",
        name="CSV/Excel",
        category="Customer Data",
        implementation=LIVE,
        auth="file_upload",
        produces=("Customer", "Contact", "Policy", "Interaction"),
        notes="Advisor uploads a file; validation and duplicate detection run before anything is written.",
    ),
    Provider(
        key="crm_salesforce",
        name="Salesforce",
        category="Customer Data",
        implementation=CREDENTIALED,
        auth="oauth2",
        required_env=(),
        scopes=("api", "refresh_token"),
        produces=("Customer", "Contact", "Interaction"),
        notes="Connected App OAuth. Reads Account, Contact, and Task via SOQL.",
    ),
    Provider(
        key="crm_hubspot",
        name="HubSpot",
        category="Customer Data",
        implementation=CREDENTIALED,
        auth="api_token",
        scopes=("crm.objects.contacts.read", "crm.objects.companies.read"),
        produces=("Customer", "Contact"),
        notes="Private app token is the quickest path — no OAuth round trip needed.",
    ),
    Provider(
        key="crm_agencyzoom",
        name="AgencyZoom",
        category="Customer Data",
        implementation=CREDENTIALED,
        auth="api_token",
        produces=("Customer", "Contact"),
        notes="API access is issued per agency. CSV export works today via the importer.",
    ),
    Provider(
        key="crm_applied_epic",
        name="Applied Epic",
        category="Customer Data",
        implementation=CREDENTIALED,
        auth="oauth2",
        produces=("Customer", "Contact", "Policy"),
        notes="Requires Applied Developer Program enrolment. CSV export works today via the importer.",
    ),
    Provider(
        key="crm_ezlynx",
        name="EZLynx",
        category="Customer Data",
        implementation=CREDENTIALED,
        auth="api_token",
        produces=("Customer", "Contact", "Policy"),
        notes="API access is arranged through an EZLynx partner agreement. CSV export works today.",
    ),
    Provider(
        key="crm_hawksoft",
        name="HawkSoft",
        category="Customer Data",
        implementation=CREDENTIALED,
        auth="api_token",
        produces=("Customer", "Contact", "Policy"),
        notes="API access is granted through the HawkSoft Partner Program. CSV export works today.",
    ),
    Provider(
        key="crm_insuredmine",
        name="InsuredMine",
        category="Customer Data",
        implementation=CREDENTIALED,
        auth="api_token",
        produces=("Customer", "Contact"),
        notes="API keys are issued from your InsuredMine account. CSV export works today.",
    ),
    # --- 2/3. Calendar ------------------------------------------------------
    Provider(
        key="ics",
        name="Calendar file (.ics)",
        category="Calendar",
        implementation=LIVE,
        auth="file_upload",
        produces=("Meeting",),
        notes="Standard iCalendar export from any calendar product. Real parsing, no provider credential needed.",
    ),
    Provider(
        key="google_calendar",
        name="Google Calendar",
        category="Calendar",
        implementation=CREDENTIALED,
        auth="oauth2",
        required_env=("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"),
        scopes=("https://www.googleapis.com/auth/calendar.events.readonly",),
        produces=("Meeting",),
        notes="Read-only events scope. Ingestion implemented against the Google Calendar REST API.",
    ),
    Provider(
        key="outlook_calendar",
        name="Microsoft Outlook",
        category="Calendar",
        implementation=CREDENTIALED,
        auth="oauth2",
        required_env=("MS_OAUTH_CLIENT_ID", "MS_OAUTH_CLIENT_SECRET"),
        scopes=("Calendars.Read",),
        produces=("Meeting",),
        notes="Read-only calendar scope. Ingestion implemented against Microsoft Graph.",
    ),
    # --- 5. Meetings --------------------------------------------------------
    Provider(
        key="teams",
        name="Microsoft Teams",
        category="Meetings",
        implementation=CREDENTIALED,
        auth="oauth2",
        scopes=("OnlineMeetings.Read", "OnlineMeetingTranscript.Read.All"),
        produces=("Interaction",),
        notes="Transcripts are fetched only for meetings the advisor owns and only where the tenant has granted transcript access.",
    ),
    Provider(
        key="zoom",
        name="Zoom",
        category="Meetings",
        implementation=ARCHITECTURE,
        auth="oauth2",
        scopes=("meeting:read", "recording:read"),
        produces=("Interaction",),
        notes="Cloud recording transcripts via the Zoom API, only after the account owner authorizes the app.",
    ),
    Provider(
        key="google_meet",
        name="Google Meet",
        category="Meetings",
        implementation=ARCHITECTURE,
        auth="oauth2",
        scopes=("https://www.googleapis.com/auth/drive.readonly",),
        produces=("Interaction",),
        notes="Meet artifacts land in Drive; ingestion reads them through the Drive connector contract.",
    ),
    # --- 6. Email -----------------------------------------------------------
    Provider(
        key="m365_email",
        name="Microsoft 365/Outlook",
        category="Communication",
        implementation=CREDENTIALED,
        auth="oauth2",
        scopes=("Mail.Read",),
        produces=("Interaction",),
        notes="Requires explicit per-mailbox consent and a retention window; message bodies are never stored beyond it.",
    ),
    Provider(
        key="gmail",
        name="Gmail",
        category="Communication",
        implementation=CREDENTIALED,
        auth="oauth2",
        scopes=("https://www.googleapis.com/auth/gmail.readonly",),
        produces=("Interaction",),
        notes="Requires explicit consent and a retention window; only threads with matched customers are retained.",
    ),
    # --- 7. WhatsApp --------------------------------------------------------
    Provider(
        key="whatsapp_business",
        name="WhatsApp Business",
        category="Communication",
        implementation=CREDENTIALED,
        auth="oauth2",
        scopes=("whatsapp_business_messaging", "whatsapp_business_management"),
        produces=("Interaction",),
        notes="Official WhatsApp Business Platform API with webhook delivery. Personal WhatsApp accounts are never scraped.",
    ),
    # --- 8. Files -----------------------------------------------------------
    Provider(
        key="onedrive",
        name="OneDrive",
        category="Files",
        implementation=CREDENTIALED,
        auth="oauth2",
        scopes=("Files.Read",),
        produces=("Interaction",),
        notes="Files become contextual sources for retrieval, never customer truth on their own.",
    ),
    Provider(
        key="sharepoint",
        name="SharePoint",
        category="Files",
        implementation=CREDENTIALED,
        auth="oauth2",
        scopes=("Sites.Read.All",),
        produces=("Interaction",),
        notes="Site-scoped read access; document permissions are carried through to retrieval.",
    ),
    Provider(
        key="google_drive",
        name="Google Drive",
        category="Files",
        implementation=CREDENTIALED,
        auth="oauth2",
        scopes=("https://www.googleapis.com/auth/drive.readonly",),
        produces=("Interaction",),
        notes="Read-only Drive access; files are indexed as context with their source permissions retained.",
    ),
)

_BY_KEY = {p.key: p for p in PROVIDERS}

# Display order for the Connection Center, following the Stage 2 priority list.
CATEGORY_ORDER = ("Customer Data", "Calendar", "Meetings", "Communication", "Files")


def get_provider(key: str) -> Provider:
    if key not in _BY_KEY:
        raise KeyError(f"Unknown provider '{key}'")
    return _BY_KEY[key]


def list_providers() -> list[Provider]:
    return list(PROVIDERS)


def describe(provider: Provider) -> dict[str, Any]:
    """Registry-side facts only — no connection state. connection_store
    supplies status/account/last_sync so that the two can never drift."""
    return {
        "provider": provider.key,
        "name": provider.name,
        "category": provider.category,
        "implementation": provider.implementation,
        "auth": provider.auth,
        "scopes": list(provider.scopes),
        "produces": list(provider.produces),
        "notes": provider.notes,
        "missing_config": provider.missing_config(),
        "can_connect": provider.is_configurable(),
    }

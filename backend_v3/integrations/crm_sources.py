"""
CRM connectors for agency management systems and sales CRMs.

Two tiers, because these vendors genuinely differ in how reachable they
are, and pretending otherwise would produce connectors that fail on first
contact:

  Self-serve OAuth — Salesforce and HubSpot publish open OAuth apps and
  stable REST APIs. Their connectors below are concrete: an advisor
  registers an app, pastes two values, and syncs.

  Partner-gated — AgencyZoom, Applied Epic, EZLynx, HawkSoft, and
  InsuredMine gate API access behind a vendor agreement, and their
  endpoint contracts are issued with those credentials rather than
  published openly. Inventing paths for them would produce code that
  looks finished and 404s in production. Instead they use
  RestCrmConnector, which is driven by an endpoint + field mapping the
  advisor supplies from their vendor's own documentation.

Every CRM here maps onto the same normalized objects, so the core product
never learns a vendor's field names.

Worth saying plainly: all seven of these export CSV, and the Stage 2 CSV
importer already ingests that today with validation and duplicate
detection. Live API sync is the upgrade, not the only path.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.integrations.models import (
    NormalizedContact,
    NormalizedCustomer,
    NormalizedInteraction,
    NormalizedPolicy,
    Provenance,
)

SELF_SERVE = "self_serve_oauth"
PARTNER_GATED = "partner_gated"


@dataclass(frozen=True)
class CrmVendor:
    key: str
    name: str
    access: str
    auth_kind: str
    docs_url: str
    notes: str
    # Fields the advisor pastes during setup.
    credential_fields: tuple[tuple[str, str, bool], ...] = ()  # (key, label, is_secret)
    csv_export_hint: str = ""


CRM_VENDORS: tuple[CrmVendor, ...] = (
    CrmVendor(
        key="salesforce",
        name="Salesforce",
        access=SELF_SERVE,
        auth_kind="oauth2",
        docs_url="https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/",
        notes="Connected App with the api and refresh_token scopes. Reads Account, Contact, and Task via SOQL.",
        credential_fields=(
            ("client_id", "Consumer Key", False),
            ("client_secret", "Consumer Secret", True),
            ("login_url", "Login URL (use test.salesforce.com for a sandbox)", False),
        ),
        csv_export_hint="Reports → export as CSV.",
    ),
    CrmVendor(
        key="hubspot",
        name="HubSpot",
        access=SELF_SERVE,
        auth_kind="oauth2_or_token",
        docs_url="https://developers.hubspot.com/docs/api/crm/contacts",
        notes="Private app token is the quickest path: create one with crm.objects.contacts.read and companies.read.",
        credential_fields=(("access_token", "Private app access token", True),),
        csv_export_hint="Contacts → Actions → Export.",
    ),
    CrmVendor(
        key="agencyzoom",
        name="AgencyZoom",
        access=PARTNER_GATED,
        auth_kind="api_token",
        docs_url="https://www.agencyzoom.com/",
        notes="API access is issued per agency. Ask AgencyZoom support for API documentation and a key.",
        credential_fields=(
            ("base_url", "API base URL", False),
            ("api_token", "API token", True),
        ),
        csv_export_hint="Leads/Customers → Export.",
    ),
    CrmVendor(
        key="applied_epic",
        name="Applied Epic",
        access=PARTNER_GATED,
        auth_kind="oauth2",
        docs_url="https://developer.appliedsystems.com/",
        notes="Requires enrolment in the Applied Developer Program; endpoints are issued with your credentials.",
        credential_fields=(
            ("base_url", "API base URL", False),
            ("client_id", "Client ID", False),
            ("client_secret", "Client secret", True),
        ),
        csv_export_hint="Reporting → export to CSV/Excel.",
    ),
    CrmVendor(
        key="ezlynx",
        name="EZLynx",
        access=PARTNER_GATED,
        auth_kind="api_token",
        docs_url="https://www.ezlynx.com/",
        notes="API access is arranged through an EZLynx partner agreement.",
        credential_fields=(
            ("base_url", "API base URL", False),
            ("api_token", "API token", True),
        ),
        csv_export_hint="Applicants → Export.",
    ),
    CrmVendor(
        key="hawksoft",
        name="HawkSoft",
        access=PARTNER_GATED,
        auth_kind="api_token",
        docs_url="https://www.hawksoft.com/partners",
        notes="API access is granted through the HawkSoft Partner Program.",
        credential_fields=(
            ("base_url", "API base URL", False),
            ("api_token", "API token", True),
        ),
        csv_export_hint="Reports → export client list.",
    ),
    CrmVendor(
        key="insuredmine",
        name="InsuredMine",
        access=PARTNER_GATED,
        auth_kind="api_token",
        docs_url="https://www.insuredmine.com/",
        notes="API keys are issued from your InsuredMine account; confirm the base URL in their docs.",
        credential_fields=(
            ("base_url", "API base URL", False),
            ("api_token", "API key", True),
        ),
        csv_export_hint="Contacts → Export.",
    ),
)

_BY_KEY = {v.key: v for v in CRM_VENDORS}


def get_vendor(key: str) -> CrmVendor:
    if key not in _BY_KEY:
        raise KeyError(f"Unknown CRM '{key}'")
    return _BY_KEY[key]


def list_vendors() -> list[CrmVendor]:
    return list(CRM_VENDORS)


def describe_vendor(vendor: CrmVendor) -> dict[str, Any]:
    from backend_v3.integrations.connection_store import get_connection
    from backend_v3.integrations.credentials import credential_status

    provider_key = f"crm_{vendor.key}"
    record = get_connection(provider_key) or {}
    try:
        status = credential_status(provider_key)
    except Exception:
        status = {"configured": False, "source": "none", "missing": [], "hints": {}}

    return {
        "provider": provider_key,
        "vendor": vendor.key,
        "name": vendor.name,
        "access": vendor.access,
        "auth_kind": vendor.auth_kind,
        "docs_url": vendor.docs_url,
        "notes": vendor.notes,
        "csv_export_hint": vendor.csv_export_hint,
        "credential_fields": [
            {"key": key, "label": label, "secret": secret} for key, label, secret in vendor.credential_fields
        ],
        "credentials_configured": status.get("configured", False),
        "hints": status.get("hints", {}),
        "status": record.get("status") or "not_connected",
        "account": record.get("account"),
        "last_sync": record.get("last_sync"),
        "data_synchronized": record.get("data_synchronized") or {},
        "connected": (record.get("status") or "not_connected") == "connected",
    }


# --------------------------------------------------------------------------
# Salesforce
# --------------------------------------------------------------------------

SALESFORCE_API_VERSION = "v59.0"


def _salesforce_creds() -> dict[str, str]:
    from backend_v3.integrations.credentials import get_credentials

    return get_credentials("crm_salesforce")


def salesforce_authorization_url() -> dict[str, Any]:
    from urllib.parse import urlencode

    from backend_v3.config import OAUTH_REDIRECT_BASE

    creds = _salesforce_creds()
    if not creds.get("client_id"):
        raise RuntimeError("Salesforce needs its Consumer Key and Secret first.")

    login = (creds.get("login_url") or "login.salesforce.com").replace("https://", "").strip("/")
    redirect_uri = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/api/v3/integrations/crm/salesforce/callback"
    params = {
        "client_id": creds["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "api refresh_token",
    }
    return {
        "authorization_url": f"https://{login}/services/oauth2/authorize?{urlencode(params)}",
        "redirect_uri": redirect_uri,
    }


def salesforce_exchange_code(code: str) -> dict[str, Any]:
    import httpx

    from backend_v3.config import OAUTH_REDIRECT_BASE
    from backend_v3.integrations.connection_store import mark_connected
    from backend_v3.integrations.token_store import save_token

    creds = _salesforce_creds()
    login = (creds.get("login_url") or "login.salesforce.com").replace("https://", "").strip("/")
    response = httpx.post(
        f"https://{login}/services/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "redirect_uri": f"{OAUTH_REDIRECT_BASE.rstrip('/')}/api/v3/integrations/crm/salesforce/callback",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    save_token("crm_salesforce", payload.get("id", ""), payload)
    mark_connected("crm_salesforce", account=payload.get("instance_url", "Salesforce"))
    return {"instance_url": payload.get("instance_url")}


def _salesforce_query(soql: str) -> list[dict[str, Any]]:
    import httpx

    from backend_v3.integrations.calendar_sources import NotConnected
    from backend_v3.integrations.token_store import load_token

    token = load_token("crm_salesforce")
    if not token or not token.get("access_token"):
        raise NotConnected("Salesforce is not connected.")

    response = httpx.get(
        f"{token['instance_url']}/services/data/{SALESFORCE_API_VERSION}/query",
        params={"q": soql},
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=45.0,
    )
    response.raise_for_status()
    return response.json().get("records", [])


def sync_salesforce(limit: int = 200) -> dict[str, Any]:
    from backend_v3.integrations.pipeline import ingest

    customers: list[NormalizedCustomer] = []
    # Email lives on Contact rather than Account unless the org has Person
    # Accounts enabled, so it is picked up in the Contact pass below.
    for record in _salesforce_query(f"SELECT Id, Name, Phone FROM Account LIMIT {limit}"):
        customers.append(
            NormalizedCustomer(
                external_id=record["Id"],
                full_name=record.get("Name") or "Unnamed account",
                phone=record.get("Phone"),
                provenance=Provenance("crm_salesforce", record["Id"], f"Account/{record['Id']}"),
            )
        )

    contacts: list[NormalizedContact] = []
    for record in _salesforce_query(
        f"SELECT Id, Name, Email, Phone, AccountId, Title FROM Contact LIMIT {limit}"
    ):
        if not record.get("AccountId"):
            continue
        contacts.append(
            NormalizedContact(
                customer_external_id=record["AccountId"],
                full_name=record.get("Name") or "Unnamed contact",
                relationship=record.get("Title") or "contact",
                email=record.get("Email"),
                phone=record.get("Phone"),
                provenance=Provenance("crm_salesforce", record["Id"], f"Contact/{record['Id']}"),
            )
        )

    interactions: list[NormalizedInteraction] = []
    for record in _salesforce_query(
        f"SELECT Id, Subject, Description, ActivityDate, AccountId FROM Task "
        f"WHERE AccountId != null LIMIT {limit}"
    ):
        interactions.append(
            NormalizedInteraction(
                customer_external_id=record["AccountId"],
                interaction_type="crm_activity",
                occurred_at=record.get("ActivityDate") or "",
                summary=record.get("Subject") or "Activity",
                body=record.get("Description"),
                provenance=Provenance("crm_salesforce", record["Id"], f"Task/{record['Id']}"),
            )
        )

    return ingest(
        source_system="crm_salesforce",
        customers=customers,
        contacts=contacts,
        interactions=interactions,
    )


# --------------------------------------------------------------------------
# HubSpot
# --------------------------------------------------------------------------

HUBSPOT_API = "https://api.hubapi.com"


def _hubspot_headers() -> dict[str, str]:
    from backend_v3.integrations.calendar_sources import NotConnected
    from backend_v3.integrations.credentials import get_credentials

    token = get_credentials("crm_hubspot").get("access_token")
    if not token:
        raise NotConnected("HubSpot is not connected.")
    return {"Authorization": f"Bearer {token}"}


def hubspot_verify() -> dict[str, Any]:
    """Confirm the token works before reporting connected."""
    import httpx

    response = httpx.get(
        f"{HUBSPOT_API}/crm/v3/objects/contacts",
        params={"limit": 1},
        headers=_hubspot_headers(),
        timeout=30.0,
    )
    if response.status_code >= 400:
        detail = ""
        try:
            detail = response.json().get("message", "")
        except Exception:
            detail = response.text[:200]
        raise RuntimeError(f"HubSpot rejected this token: {detail or response.status_code}")
    return {"ok": True}


def sync_hubspot(limit: int = 100) -> dict[str, Any]:
    import httpx

    from backend_v3.integrations.pipeline import ingest

    headers = _hubspot_headers()
    response = httpx.get(
        f"{HUBSPOT_API}/crm/v3/objects/contacts",
        params={"limit": min(limit, 100), "properties": "firstname,lastname,email,phone,lifecyclestage"},
        headers=headers,
        timeout=45.0,
    )
    response.raise_for_status()

    customers: list[NormalizedCustomer] = []
    for record in response.json().get("results", []):
        props = record.get("properties") or {}
        name = " ".join(p for p in (props.get("firstname"), props.get("lastname")) if p).strip()
        customers.append(
            NormalizedCustomer(
                external_id=record["id"],
                full_name=name or props.get("email") or "Unnamed contact",
                email=props.get("email"),
                phone=props.get("phone"),
                life_stage=props.get("lifecyclestage"),
                provenance=Provenance(
                    "crm_hubspot", record["id"], f"{HUBSPOT_API}/contacts/{record['id']}"
                ),
            )
        )

    return ingest(source_system="crm_hubspot", customers=customers)


# --------------------------------------------------------------------------
# Partner-gated vendors: configurable REST connector
# --------------------------------------------------------------------------

@dataclass
class RestCrmMapping:
    """Where to fetch records and which fields map to the normalized model.

    This exists because the partner-gated vendors issue their endpoint
    contracts alongside credentials. Rather than guessing paths, the
    advisor supplies them once from their vendor's documentation and the
    connector handles the rest.
    """

    customers_path: str = ""
    records_key: str = "data"
    external_id_field: str = "id"
    name_field: str = "name"
    email_field: str = "email"
    phone_field: str = "phone"
    extra_headers: dict[str, str] = field(default_factory=dict)


def sync_rest_crm(vendor_key: str, mapping: RestCrmMapping | None = None) -> dict[str, Any]:
    """Sync a partner-gated CRM using its configured endpoint and mapping."""
    import httpx

    from backend_v3.integrations.credentials import get_credentials
    from backend_v3.integrations.pipeline import ingest

    vendor = get_vendor(vendor_key)
    provider_key = f"crm_{vendor.key}"
    creds = get_credentials(provider_key)

    base_url = (creds.get("base_url") or "").rstrip("/")
    token = creds.get("api_token")
    if not base_url or not token:
        raise RuntimeError(
            f"{vendor.name} needs its API base URL and token. Both are issued by {vendor.name} "
            "with your API agreement."
        )

    mapping = mapping or RestCrmMapping(customers_path=creds.get("customers_path", ""))
    if not mapping.customers_path:
        raise RuntimeError(
            f"{vendor.name} needs the customer-list endpoint path from its API documentation "
            "before it can sync. Until then, the CSV importer handles "
            f"{vendor.name} exports ({vendor.csv_export_hint})."
        )

    response = httpx.get(
        f"{base_url}/{mapping.customers_path.lstrip('/')}",
        headers={"Authorization": f"Bearer {token}", **mapping.extra_headers},
        timeout=45.0,
    )
    response.raise_for_status()
    payload = response.json()
    records = payload.get(mapping.records_key, payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise RuntimeError(
            f"Expected a list of records under '{mapping.records_key}' but {vendor.name} returned "
            f"{type(records).__name__}. Adjust the records key in the connector settings."
        )

    customers = [
        NormalizedCustomer(
            external_id=str(record.get(mapping.external_id_field, "")),
            full_name=str(record.get(mapping.name_field) or "Unnamed customer"),
            email=record.get(mapping.email_field),
            phone=record.get(mapping.phone_field),
            provenance=Provenance(
                provider_key,
                str(record.get(mapping.external_id_field, "")),
                f"{base_url}/{mapping.customers_path}",
            ),
        )
        for record in records
        if record.get(mapping.external_id_field)
    ]

    return ingest(source_system=provider_key, customers=customers)


SYNC_FUNCTIONS = {
    "crm_salesforce": sync_salesforce,
    "crm_hubspot": sync_hubspot,
}


def sync_crm(provider_key: str) -> dict[str, Any]:
    if provider_key in SYNC_FUNCTIONS:
        return SYNC_FUNCTIONS[provider_key]()
    vendor_key = provider_key.replace("crm_", "", 1)
    return sync_rest_crm(vendor_key)

"""
Account providers — the identity behind a group of capabilities.

An advisor does not think "I need to connect Gmail, then Drive, then
Calendar." They think "connect my Google account." Google, Microsoft, and
Meta each issue one credential and one consent that unlocks several of
this product's capabilities, so that is the unit the product exposes.

    Google     -> Calendar, Gmail, Drive, Meet
    Microsoft  -> Outlook Calendar, M365 Mail, OneDrive, SharePoint, Teams
    Meta       -> WhatsApp Business

Practical consequences:

  - one OAuth client registration per account, not per capability;
  - one consent screen listing the scopes for every capability the
    advisor enabled;
  - one access token, refreshed once, reused by every connector in the
    group;
  - disconnecting an account revokes every capability under it, because
    they share the credential.

Meta is modelled here for symmetry in the UI, but it is not an OAuth
authorization-code provider: the WhatsApp Business Platform issues a
long-lived system-user token instead. `auth_kind` records that difference
so the UI can present the right setup path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OAUTH_CODE = "oauth2_authorization_code"
API_TOKEN = "api_token"


@dataclass(frozen=True)
class CredentialField:
    """One value the advisor pastes during setup."""

    key: str
    label: str
    help_text: str
    secret: bool = False
    optional: bool = False
    default: str = ""


@dataclass(frozen=True)
class AccountProvider:
    key: str
    name: str
    auth_kind: str
    # Provider keys from registry.py that this account unlocks.
    capabilities: tuple[str, ...]
    credential_fields: tuple[CredentialField, ...]
    console_url: str
    console_name: str
    setup_steps: tuple[str, ...] = ()
    docs_url: str = ""
    notes: str = ""

    def redirect_uri(self) -> str:
        from backend_v3.config import OAUTH_REDIRECT_BASE

        return f"{OAUTH_REDIRECT_BASE.rstrip('/')}/api/v3/integrations/accounts/{self.key}/callback"


GOOGLE = AccountProvider(
    key="google",
    name="Google",
    auth_kind=OAUTH_CODE,
    capabilities=("google_calendar", "gmail", "google_drive", "google_meet"),
    credential_fields=(
        CredentialField("client_id", "Client ID", "Ends in .apps.googleusercontent.com"),
        CredentialField("client_secret", "Client secret", "Shown once when you create the OAuth client", secret=True),
    ),
    console_url="https://console.cloud.google.com/apis/credentials",
    console_name="Google Cloud Console",
    docs_url="https://developers.google.com/identity/protocols/oauth2/web-server",
    setup_steps=(
        "Create (or pick) a project in Google Cloud Console.",
        "Enable the APIs you want: Google Calendar API, Gmail API, Google Drive API.",
        "Configure the OAuth consent screen. While it is in Testing, add your own Google address under Test users.",
        "Go to Credentials → Create credentials → OAuth client ID → Web application.",
        "Paste the redirect URI shown below into Authorised redirect URIs.",
        "Copy the Client ID and Client secret into the fields below.",
    ),
    notes="One Google consent covers Calendar, Gmail, and Drive. All scopes requested are read-only.",
)

MICROSOFT = AccountProvider(
    key="microsoft",
    name="Microsoft 365",
    auth_kind=OAUTH_CODE,
    capabilities=("outlook_calendar", "m365_email", "onedrive", "sharepoint", "teams"),
    credential_fields=(
        CredentialField("client_id", "Application (client) ID", "The GUID on your app registration overview"),
        CredentialField("client_secret", "Client secret value", "Copy the Value, not the Secret ID — it is shown only once", secret=True),
        CredentialField(
            "tenant",
            "Directory (tenant) ID",
            "Your tenant GUID, or 'common' for any work or personal account",
            optional=True,
            default="common",
        ),
    ),
    console_url="https://entra.microsoft.com",
    console_name="Microsoft Entra admin center",
    docs_url="https://learn.microsoft.com/entra/identity-platform/quickstart-register-app",
    setup_steps=(
        "In the Microsoft Entra admin center, go to Applications → App registrations → New registration.",
        "Under Redirect URI choose Web and paste the redirect URI shown below.",
        "Open Certificates & secrets → New client secret, then copy the Value immediately.",
        "Open API permissions → Add a permission → Microsoft Graph → Delegated permissions.",
        "Add Calendars.Read, Mail.Read, Files.Read, Sites.Read.All, OnlineMeetings.Read, offline_access.",
        "Copy the Application (client) ID and the secret Value into the fields below.",
    ),
    notes="One Microsoft consent covers Outlook Calendar, mail, OneDrive, SharePoint, and Teams. All delegated scopes are read-only.",
)

META = AccountProvider(
    key="meta",
    name="WhatsApp Business",
    auth_kind=API_TOKEN,
    capabilities=("whatsapp_business",),
    credential_fields=(
        CredentialField("access_token", "System user access token", "A permanent token from Business Settings → System users", secret=True),
        CredentialField("phone_number_id", "Phone number ID", "From WhatsApp → API Setup — this is not the phone number itself"),
        CredentialField("business_account_id", "WhatsApp Business Account ID", "From WhatsApp → API Setup", optional=True),
        CredentialField("webhook_verify_token", "Webhook verify token", "Any string you choose; you enter the same value in Meta", secret=True),
    ),
    console_url="https://developers.facebook.com/apps",
    console_name="Meta for Developers",
    docs_url="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started",
    setup_steps=(
        "Create a Meta app of type Business and add the WhatsApp product.",
        "Connect a WhatsApp Business Account and a business phone number.",
        "In Business Settings → System users, create a system user and generate a permanent token with whatsapp_business_messaging and whatsapp_business_management.",
        "Copy the Phone number ID from WhatsApp → API Setup.",
        "Choose any webhook verify token, then paste the callback URL and that same token into WhatsApp → Configuration → Webhooks.",
        "Subscribe the webhook to the 'messages' field.",
    ),
    notes=(
        "Uses the official WhatsApp Business Platform. Messages arrive by webhook to a business number your "
        "organization owns — personal WhatsApp accounts are never accessed."
    ),
)

ACCOUNT_PROVIDERS: tuple[AccountProvider, ...] = (GOOGLE, MICROSOFT, META)
_BY_KEY = {a.key: a for a in ACCOUNT_PROVIDERS}

# Reverse index: capability provider key -> owning account provider.
_ACCOUNT_FOR_CAPABILITY: dict[str, AccountProvider] = {
    capability: account for account in ACCOUNT_PROVIDERS for capability in account.capabilities
}


def get_account(key: str) -> AccountProvider:
    if key not in _BY_KEY:
        raise KeyError(f"Unknown account provider '{key}'")
    return _BY_KEY[key]


def account_for_capability(provider_key: str) -> AccountProvider | None:
    return _ACCOUNT_FOR_CAPABILITY.get(provider_key)


def list_accounts() -> list[AccountProvider]:
    return list(ACCOUNT_PROVIDERS)


def describe_account(account: AccountProvider) -> dict[str, Any]:
    """Setup-facing description. Never includes stored credential values."""
    from backend_v3.integrations.credentials import credential_status
    from backend_v3.integrations.registry import get_provider

    status = credential_status(account.key)
    capabilities = []
    for key in account.capabilities:
        try:
            provider = get_provider(key)
        except KeyError:
            continue
        capabilities.append(
            {
                "provider": provider.key,
                "name": provider.name,
                "category": provider.category,
                "implementation": provider.implementation,
                "scopes": list(provider.scopes),
            }
        )

    return {
        "account": account.key,
        "name": account.name,
        "auth_kind": account.auth_kind,
        "console_url": account.console_url,
        "console_name": account.console_name,
        "docs_url": account.docs_url,
        "setup_steps": list(account.setup_steps),
        "notes": account.notes,
        "redirect_uri": account.redirect_uri(),
        "capabilities": capabilities,
        "credential_fields": [
            {
                "key": f.key,
                "label": f.label,
                "help_text": f.help_text,
                "secret": f.secret,
                "optional": f.optional,
                "default": f.default,
            }
            for f in account.credential_fields
        ],
        "credentials_configured": status["configured"],
        "credentials_source": status["source"],
        "missing_credentials": status["missing"],
    }


def scopes_for(account: AccountProvider, capability_keys: list[str] | None = None) -> list[str]:
    """Union of scopes for the requested capabilities.

    Requesting only what the advisor enabled is the least-privilege part:
    someone who wants calendar sync alone is never asked for mailbox
    access. `offline_access` is added for Microsoft because Graph will not
    issue a refresh token without it.
    """
    from backend_v3.integrations.registry import get_provider

    selected = capability_keys or list(account.capabilities)
    scopes: list[str] = []
    for key in selected:
        if key not in account.capabilities:
            continue
        try:
            provider = get_provider(key)
        except KeyError:
            continue
        for scope in provider.scopes:
            if scope not in scopes:
                scopes.append(scope)

    if account.key == "microsoft":
        for scope in ("offline_access",):
            if scope not in scopes:
                scopes.append(scope)
    return scopes

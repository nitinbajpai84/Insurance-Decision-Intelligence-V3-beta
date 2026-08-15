"""
OAuth client credentials entered by the advisor.

Stage 2 read client IDs and secrets from environment variables, which
means connecting a provider required editing .env and restarting the
backend. That is fine for an operator and hostile to an advisor, so
credentials can now be saved from the setup screen instead.

Rules this module enforces:

  - secrets are Fernet-encrypted before storage, using the same key as
    token_store. With no key configured, saving is refused rather than
    written in plaintext;
  - `get_credentials` is server-side only. Every API-facing function
    returns presence and masked hints, never a secret value;
  - environment variables still win when present, so an operator-managed
    deployment keeps working and cannot be silently overridden from the UI.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Environment variables that pre-supply an account's credentials.
ENV_MAP: dict[str, dict[str, str]] = {
    "google": {
        "client_id": "GOOGLE_OAUTH_CLIENT_ID",
        "client_secret": "GOOGLE_OAUTH_CLIENT_SECRET",
    },
    "microsoft": {
        "client_id": "MS_OAUTH_CLIENT_ID",
        "client_secret": "MS_OAUTH_CLIENT_SECRET",
        "tenant": "MS_OAUTH_TENANT",
    },
    "meta": {
        "access_token": "WHATSAPP_ACCESS_TOKEN",
        "phone_number_id": "WHATSAPP_PHONE_NUMBER_ID",
        "business_account_id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "webhook_verify_token": "WHATSAPP_WEBHOOK_VERIFY_TOKEN",
    },
}


def _env_credentials(account_key: str) -> dict[str, str]:
    import os

    return {
        field: os.environ.get(env_name, "").strip()
        for field, env_name in ENV_MAP.get(account_key, {}).items()
        if os.environ.get(env_name, "").strip()
    }


def _stored_credentials(account_key: str) -> dict[str, str]:
    from backend_v3.graph_store.neo4j_client import run_query
    from backend_v3.integrations.token_store import _fernet

    rows = run_query(
        "MATCH (c:IntegrationCredential {account: $account}) RETURN c.ciphertext AS ciphertext",
        {"account": account_key},
    )
    if not rows or not rows[0].get("ciphertext"):
        return {}
    return json.loads(_fernet().decrypt(rows[0]["ciphertext"].encode()).decode())


def get_credentials(account_key: str) -> dict[str, str]:
    """Full credentials for server-side use. Never expose the result."""
    try:
        stored = _stored_credentials(account_key)
    except Exception:
        stored = {}
    # Environment wins, so an operator-configured deployment is authoritative.
    return {**stored, **_env_credentials(account_key)}


def _field_specs(account_key: str) -> list[tuple[str, str, bool, bool]]:
    """(key, label, is_secret, is_optional) for either an account provider
    or a CRM vendor — both store credentials through this module."""
    if account_key.startswith("crm_"):
        from backend_v3.integrations.crm_sources import get_vendor

        vendor = get_vendor(account_key.replace("crm_", "", 1))
        # A CRM's login_url/base_url style fields are optional only when a
        # sensible default exists; the vendor spec marks secrets explicitly.
        return [(key, label, secret, False) for key, label, secret in vendor.credential_fields]

    from backend_v3.integrations.accounts import get_account

    return [
        (f.key, f.label, f.secret, f.optional) for f in get_account(account_key).credential_fields
    ]


def _required_fields(account_key: str) -> list[str]:
    return [key for key, _, _, optional in _field_specs(account_key) if not optional]


def save_credentials(account_key: str, values: dict[str, str]) -> dict[str, Any]:
    """Encrypt and store credentials the advisor pasted in the setup screen."""
    from backend_v3.graph_store.neo4j_client import run_write
    from backend_v3.integrations.accounts import get_account
    from backend_v3.integrations.audit import audit
    from backend_v3.integrations.token_store import _fernet

    allowed = {key for key, _, _, _ in _field_specs(account_key)}
    cleaned = {
        key: str(value).strip()
        for key, value in values.items()
        if key in allowed and str(value).strip()
    }

    missing = [field for field in _required_fields(account_key) if field not in cleaned]
    if missing:
        labels = {key: label for key, label, _, _ in _field_specs(account_key)}
        raise ValueError(f"Missing required value(s): {', '.join(labels.get(m, m) for m in missing)}")

    # Raises EncryptionUnavailable if no key is configured — refusing is
    # the correct outcome, because the alternative is a plaintext secret.
    blob = _fernet().encrypt(json.dumps(cleaned).encode()).decode()
    run_write(
        "MERGE (c:IntegrationCredential {account: $account}) "
        "SET c.ciphertext = $blob, c.updated_at = $now, c.field_names = $fields",
        {
            "account": account_key,
            "blob": blob,
            "now": datetime.now(timezone.utc).isoformat(),
            "fields": sorted(cleaned.keys()),
        },
    )
    # Field names only — values must never reach the audit log.
    audit("integration.credentials_saved", subject_id=account_key, metadata={"fields": sorted(cleaned.keys())})
    return credential_status(account_key)


def delete_credentials(account_key: str) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_write
    from backend_v3.integrations.audit import audit

    run_write("MATCH (c:IntegrationCredential {account: $account}) DETACH DELETE c", {"account": account_key})
    audit("integration.credentials_deleted", subject_id=account_key)
    return credential_status(account_key)


def _mask(value: str) -> str:
    """Enough to recognise a value, never enough to use it."""
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}{'•' * 6}{value[-4:]}"


def credential_status(account_key: str) -> dict[str, Any]:
    """Presence and masked hints only — safe to return over the API."""
    env = _env_credentials(account_key)
    try:
        stored = _stored_credentials(account_key)
    except Exception:
        stored = {}

    combined = {**stored, **env}
    required = _required_fields(account_key)
    missing = [field for field in required if not combined.get(field)]

    if env and not missing:
        source = "environment"
    elif stored and not missing:
        source = "saved_in_app"
    elif combined:
        source = "incomplete"
    else:
        source = "none"

    hints = {}
    for key, _label, secret, _optional in _field_specs(account_key):
        value = combined.get(key, "")
        if not value:
            continue
        hints[key] = _mask(value) if secret else value

    return {
        "account": account_key,
        "configured": not missing,
        "source": source,
        "missing": missing,
        "present_fields": sorted(k for k, v in combined.items() if v),
        # Non-secret values are shown in full so the advisor can confirm
        # what is stored; secrets are masked.
        "hints": hints,
    }

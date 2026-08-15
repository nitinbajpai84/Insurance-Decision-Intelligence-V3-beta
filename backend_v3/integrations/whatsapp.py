"""
WhatsApp Business Platform (Meta Cloud API).

This is the only supported WhatsApp path, and it differs from Google and
Microsoft in two ways that matter:

  - it is not an OAuth sign-in. Meta issues a long-lived system-user
    token against a business phone number the organization owns, so
    "connecting" means saving that token rather than redirecting the
    advisor to a consent screen;
  - messages arrive by webhook rather than polling. Meta calls the
    callback URL when a customer replies.

Personal WhatsApp accounts are not accessible through this API and are
never scraped. If a message arrives from a number that does not resolve
to a customer, it is counted and discarded rather than stored.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.integrations.models import NormalizedInteraction, Provenance

GRAPH_VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"


def webhook_url() -> str:
    from backend_v3.config import OAUTH_REDIRECT_BASE

    return f"{OAUTH_REDIRECT_BASE.rstrip('/')}/api/v3/integrations/whatsapp/webhook"


def verify_credentials() -> dict[str, Any]:
    """Confirm the saved token can actually read the business number.

    Connecting only after a successful call is what stops a typo'd token
    from showing as connected and silently failing later.
    """
    import httpx

    from backend_v3.integrations.credentials import get_credentials

    creds = get_credentials("meta")
    token = creds.get("access_token")
    phone_number_id = creds.get("phone_number_id")
    if not token or not phone_number_id:
        raise RuntimeError("WhatsApp needs an access token and a phone number ID before it can connect.")

    response = httpx.get(
        f"{GRAPH}/{phone_number_id}",
        params={"fields": "display_phone_number,verified_name,quality_rating"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    if response.status_code >= 400:
        detail = ""
        try:
            detail = response.json().get("error", {}).get("message", "")
        except Exception:
            detail = response.text[:200]
        raise RuntimeError(f"Meta rejected these credentials: {detail or response.status_code}")

    data = response.json()
    return {
        "display_phone_number": data.get("display_phone_number", ""),
        "verified_name": data.get("verified_name", ""),
        "quality_rating": data.get("quality_rating", ""),
    }


def connect() -> dict[str, Any]:
    """Validate credentials against Meta, then record the connection."""
    from backend_v3.integrations.connection_store import mark_connected

    details = verify_credentials()
    label = details.get("verified_name") or details.get("display_phone_number") or "WhatsApp Business"
    mark_connected("whatsapp_business", account=label)
    return {
        "provider": "whatsapp_business",
        "account": label,
        "webhook_url": webhook_url(),
        **details,
    }


def verify_webhook(mode: str, token: str, challenge: str) -> str | None:
    """Meta's subscription handshake: echo the challenge iff the verify
    token matches the one the advisor configured."""
    from backend_v3.integrations.credentials import get_credentials

    expected = get_credentials("meta").get("webhook_verify_token")
    if mode == "subscribe" and expected and token == expected:
        return challenge
    return None


def parse_webhook_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten Meta's nested webhook body into simple message dicts."""
    messages: list[dict[str, Any]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            # Contact names arrive alongside, keyed by wa_id.
            profiles = {
                contact.get("wa_id"): (contact.get("profile") or {}).get("name", "")
                for contact in value.get("contacts", [])
            }
            for message in value.get("messages", []):
                if message.get("type") != "text":
                    # Media messages carry no text to embed; only their
                    # presence would be recorded, which is not useful yet.
                    continue
                sender = message.get("from", "")
                try:
                    when = datetime.fromtimestamp(int(message.get("timestamp", 0)), tz=timezone.utc)
                except (TypeError, ValueError):
                    when = datetime.now(timezone.utc)
                messages.append(
                    {
                        "message_id": message.get("id", ""),
                        "from_phone": sender,
                        "profile_name": profiles.get(sender, ""),
                        "text": (message.get("text") or {}).get("body", ""),
                        "timestamp": when.isoformat(),
                    }
                )
    return messages


def handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Ingest inbound customer messages, matched by phone number."""
    from backend_v3.integrations.identity import resolve_identity
    from backend_v3.integrations.pipeline import ingest

    interactions: list[NormalizedInteraction] = []
    unmatched = 0

    for message in parse_webhook_payload(payload):
        if not message["text"].strip():
            continue
        match = resolve_identity(whatsapp=message["from_phone"], source_system="whatsapp_business")
        if not match.resolved:
            # An unknown number is not stored. Matching it would require
            # guessing, and keeping it would collect a stranger's message.
            unmatched += 1
            continue

        interactions.append(
            NormalizedInteraction(
                customer_external_id=match.customer_id or "",
                interaction_type="whatsapp",
                occurred_at=message["timestamp"],
                summary=message["text"][:200],
                body=message["text"],
                provenance=Provenance(
                    source_system="whatsapp_business",
                    source_id=message["message_id"],
                    original_reference=f"whatsapp:{message['from_phone']}",
                    customer_id=match.customer_id,
                ),
            )
        )

    result = ingest(source_system="whatsapp_business", interactions=interactions)
    result["unmatched_messages"] = unmatched
    return result

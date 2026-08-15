"""
Connector contracts for the systems Stage 2 defines but does not yet
ingest from: CRM, meeting platforms, email, WhatsApp, and file stores.

These are interfaces plus the policy that governs each source — the part
that has to be decided before any credential exists, because it dictates
what a connector is allowed to do once it does. A concrete connector
subclasses one of these and implements `fetch`; nothing else in the
product changes, since everything downstream consumes models.py.

No class here fabricates data. `fetch` raises NotImplementedError until a
real implementation exists, which is what keeps the Connection Center
honest.
"""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.integrations.models import (
    NormalizedActivity,
    NormalizedContact,
    NormalizedCustomer,
    NormalizedInteraction,
    NormalizedPolicy,
)


@dataclass
class SourcePermission:
    """What the advisor authorized, carried alongside ingested data.

    `retention_days` is enforced by the ingestion side rather than trusted
    to the source: content older than the window is dropped even if the
    provider still serves it.
    """

    granted_by: str
    scopes: tuple[str, ...]
    granted_at: str
    retention_days: int | None = None
    inherits_source_acl: bool = False


class BaseConnector(ABC):
    provider_key: str = ""
    produces: tuple[str, ...] = ()

    def __init__(self, permission: SourcePermission | None = None) -> None:
        self.permission = permission

    @abstractmethod
    def fetch(self, **kwargs: Any) -> dict[str, list[Any]]:
        """Return normalized objects keyed by pipeline argument name
        ('customers', 'contacts', 'policies', 'interactions', 'meetings')."""

    def sync(self, **kwargs: Any) -> dict[str, Any]:
        """Fetch and run the standard pipeline. Connectors get this free."""
        from backend_v3.integrations.pipeline import ingest

        return ingest(source_system=self.provider_key, **self.fetch(**kwargs))


# --------------------------------------------------------------------------
# 4. CRM
# --------------------------------------------------------------------------

class CRMConnector(BaseConnector):
    """Vendor-neutral CRM contract.

    A CRM connector's entire job is mapping its vendor's objects onto the
    five normalized ones. The core product never learns the vendor's
    field names, which is what makes swapping CRMs a connector change
    rather than a migration.
    """

    produces = ("Customer", "Contact", "Policy", "Interaction", "Activity")

    @abstractmethod
    def fetch_customers(self) -> list[NormalizedCustomer]: ...

    @abstractmethod
    def fetch_contacts(self) -> list[NormalizedContact]: ...

    @abstractmethod
    def fetch_policies(self) -> list[NormalizedPolicy]: ...

    @abstractmethod
    def fetch_interactions(self) -> list[NormalizedInteraction]: ...

    def fetch_activities(self) -> list[NormalizedActivity]:
        return []

    def fetch(self, **kwargs: Any) -> dict[str, list[Any]]:
        return {
            "customers": self.fetch_customers(),
            "contacts": self.fetch_contacts(),
            "policies": self.fetch_policies(),
            "interactions": self.fetch_interactions(),
        }


# --------------------------------------------------------------------------
# 5. Meeting platforms
# --------------------------------------------------------------------------

class MeetingPlatformConnector(BaseConnector):
    """Teams / Zoom / Meet.

    Transcripts are the sensitive part, so two conditions gate them:
    the advisor must own or host the meeting, and the workspace must have
    granted transcript access. `fetch_transcript` returns None when either
    is false — a missing transcript is a normal outcome, never a reason to
    synthesize one.
    """

    produces = ("Interaction",)

    @abstractmethod
    def list_meetings(self, since: str, until: str) -> list[dict[str, Any]]:
        """Meeting metadata only: id, subject, start, end, participants."""

    @abstractmethod
    def fetch_transcript(self, meeting_id: str) -> str | None:
        """Approved transcript text, or None when not available."""

    def fetch(self, since: str = "", until: str = "", **kwargs: Any) -> dict[str, list[Any]]:
        interactions: list[NormalizedInteraction] = []
        for meeting in self.list_meetings(since, until):
            transcript = self.fetch_transcript(meeting["id"])
            if transcript is None:
                continue
            interactions.append(
                NormalizedInteraction(
                    customer_external_id=meeting.get("customer_external_id", ""),
                    interaction_type="meeting",
                    occurred_at=meeting["start"],
                    summary=meeting.get("subject", "Meeting"),
                    body=transcript,
                )
            )
        return {"interactions": interactions}


# --------------------------------------------------------------------------
# 6. Email
# --------------------------------------------------------------------------

class EmailConnector(BaseConnector):
    """Microsoft 365 / Gmail.

    Email is the broadest source here, so it is the most constrained:

    - consent is per mailbox and explicit; `require_consent` refuses to
      run without it;
    - only threads that resolve to a known customer are retained, so the
      advisor's unrelated mail never enters the graph;
    - bodies past the retention window are dropped at ingestion time,
      leaving the derived summary rather than the original message.
    """

    produces = ("Interaction",)

    def require_consent(self) -> SourcePermission:
        if self.permission is None:
            raise PermissionError(
                "Email ingestion requires explicit mailbox consent recorded as a SourcePermission."
            )
        return self.permission

    @abstractmethod
    def list_threads(self, since: str) -> list[dict[str, Any]]:
        """Thread metadata: id, participants, subject, last_message_at."""

    @abstractmethod
    def fetch_thread_body(self, thread_id: str) -> str:
        """Full thread text for a thread already matched to a customer."""

    def within_retention(self, occurred_at: str) -> bool:
        from datetime import datetime, timedelta, timezone

        permission = self.require_consent()
        if not permission.retention_days:
            return True
        try:
            when = datetime.fromisoformat(str(occurred_at).replace("Z", "+00:00"))
        except ValueError:
            return False
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return when >= datetime.now(timezone.utc) - timedelta(days=permission.retention_days)

    def fetch(self, since: str = "", **kwargs: Any) -> dict[str, list[Any]]:
        from backend_v3.integrations.identity import resolve_identity

        self.require_consent()
        interactions: list[NormalizedInteraction] = []

        for thread in self.list_threads(since):
            matched: str | None = None
            for participant in thread.get("participants", []):
                match = resolve_identity(email=participant, source_system=self.provider_key)
                if match.resolved:
                    matched = match.customer_id
                    break
            if not matched:
                continue  # not a customer thread — never ingested
            occurred_at = thread.get("last_message_at", "")
            interactions.append(
                NormalizedInteraction(
                    customer_external_id=matched,
                    interaction_type="email",
                    occurred_at=occurred_at,
                    summary=thread.get("subject", "Email thread"),
                    body=self.fetch_thread_body(thread["id"]) if self.within_retention(occurred_at) else None,
                )
            )
        return {"interactions": interactions}


# --------------------------------------------------------------------------
# 7. WhatsApp
# --------------------------------------------------------------------------

class WhatsAppBusinessConnector(BaseConnector):
    """WhatsApp Business Platform API only.

    Messages arrive by webhook from a business phone number the advisor's
    organization owns; there is no polling of a personal account and no
    scraping path anywhere in this design. Customer matching is by phone
    number, which is WhatsApp's own identifier.
    """

    produces = ("Interaction",)
    provider_key = "whatsapp_business"

    @abstractmethod
    def verify_webhook(self, token: str, challenge: str) -> str | None:
        """Meta's webhook verification handshake."""

    @abstractmethod
    def parse_webhook_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize a webhook body into {from_phone, text, timestamp}."""

    def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        from backend_v3.integrations.identity import resolve_identity
        from backend_v3.integrations.pipeline import ingest

        interactions: list[NormalizedInteraction] = []
        unmatched = 0
        for message in self.parse_webhook_payload(payload):
            match = resolve_identity(whatsapp=message["from_phone"], source_system=self.provider_key)
            if not match.resolved:
                unmatched += 1
                continue
            interactions.append(
                NormalizedInteraction(
                    customer_external_id=match.customer_id or "",
                    interaction_type="whatsapp",
                    occurred_at=message["timestamp"],
                    summary=message["text"][:200],
                    body=message["text"],
                )
            )
        result = ingest(source_system=self.provider_key, interactions=interactions)
        result["unmatched_messages"] = unmatched
        return result

    def fetch(self, **kwargs: Any) -> dict[str, list[Any]]:
        raise NotImplementedError("WhatsApp is webhook-driven; use handle_webhook().")


# --------------------------------------------------------------------------
# 8. File repositories
# --------------------------------------------------------------------------

class FileRepositoryConnector(BaseConnector):
    """OneDrive / SharePoint / Google Drive.

    Files are contextual sources, never customer truth. A document is
    embedded into Qdrant so it can be *cited* during retrieval, and any
    fact drawn from one still has to travel the Stage 1 proposal path and
    be approved before it becomes truth.

    Source ACLs are carried onto the indexed chunk so a document the
    advisor loses access to stops being retrievable.
    """

    produces = ("Interaction",)
    contextual_only = True

    @abstractmethod
    def list_files(self, folder: str | None = None) -> list[dict[str, Any]]:
        """File metadata: id, name, modified_at, web_url, permissions."""

    @abstractmethod
    def fetch_text(self, file_id: str) -> str:
        """Extracted text content of one file."""

    def fetch(self, **kwargs: Any) -> dict[str, list[Any]]:
        raise NotImplementedError(
            "File connectors index into semantic memory rather than writing customer facts; "
            "call index_files() once a concrete connector exists."
        )

"""
Normalized objects every connector must produce.

The core product depends on these shapes, never on a provider's own
payload — that is what keeps a CRM swap from rippling through the
application. A connector's only job is to turn its source format into
these dataclasses.

Provenance is mandatory on every imported record, not decorative: it is
what lets the advisor see where a fact came from, and what makes an
import reversible per source.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Provenance:
    """Where an imported item came from.

    source_system      provider key, e.g. "csv", "google_calendar"
    source_id          the record's ID *in that system*
    imported_at        ISO-8601 UTC
    customer_id        resolved customer, None until identity matching runs
    original_reference human-traceable pointer back to the source (file
                       name + row, calendar event URL, CRM record URL)
    """

    source_system: str
    source_id: str
    original_reference: str
    customer_id: str | None = None
    imported_at: str = field(default_factory=_now)

    def as_properties(self, prefix: str = "") -> dict[str, Any]:
        """Flatten for a Neo4j SET clause."""
        return {
            f"{prefix}source_system": self.source_system,
            f"{prefix}source_id": self.source_id,
            f"{prefix}original_reference": self.original_reference,
            f"{prefix}imported_at": self.imported_at,
            f"{prefix}source": f"{self.source_system}_{self.source_id}",
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedCustomer:
    external_id: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    life_stage: str | None = None
    advisor_name: str | None = None
    provenance: Provenance | None = None


@dataclass
class NormalizedContact:
    """A person related to a customer — family member or other contact."""

    customer_external_id: str
    full_name: str
    relationship: str
    email: str | None = None
    phone: str | None = None
    provenance: Provenance | None = None


@dataclass
class NormalizedPolicy:
    customer_external_id: str
    policy_id: str
    product_name: str
    line_of_business: str | None = None
    annual_premium: float | None = None
    policy_status: str | None = None
    provenance: Provenance | None = None


@dataclass
class NormalizedInteraction:
    """A past touchpoint: meeting, call, note, email thread."""

    customer_external_id: str
    interaction_type: str
    occurred_at: str
    summary: str
    body: str | None = None
    provenance: Provenance | None = None


@dataclass
class NormalizedActivity:
    """A task/activity owned by the advisor about a customer."""

    customer_external_id: str
    title: str
    due_date: str | None = None
    status: str = "open"
    provenance: Provenance | None = None


@dataclass
class NormalizedMeeting:
    """A calendar event. `attendees` are raw addresses as the calendar
    reports them; identity matching maps them to customers afterwards."""

    external_id: str
    title: str
    starts_at: str
    ends_at: str | None = None
    attendees: list[str] = field(default_factory=list)
    organizer: str | None = None
    meeting_link: str | None = None
    location: str | None = None
    status: str = "confirmed"
    provenance: Provenance | None = None


NORMALIZED_OBJECTS = (
    "Customer",
    "Contact",
    "Policy",
    "Interaction",
    "Activity",
    "Meeting",
)

# Stage 2 — Connections and Customer Ingestion

The advisor should not have to populate this application by hand. Stage 2
builds the path from the systems they already use into a unified customer
context, and the governance that keeps that path trustworthy.

## The pipeline

Every source flows through one path:

```
SOURCE → INGESTION → NORMALIZATION → CUSTOMER IDENTITY MATCHING
       → CUSTOMER MODEL → NEO4J → QDRANT
```

Connectors own the first three steps and return the dataclasses in
`integrations/models.py`. `integrations/pipeline.py` owns everything after,
so identity matching and provenance apply identically regardless of source.

Imported customers reuse the node shapes `synthetic_data.py` already seeds,
which is why they appear in Customer 360, My Day, and briefings without any
change to Stage 1 retrieval code.

## Implementation status

The registry (`integrations/registry.py`) is the single source of truth, and
the Connection Center renders it verbatim. Three honest states:

| State | Meaning | Providers |
|---|---|---|
| **Available now** | Ingests today, no third-party credential needed | CSV/Excel, Calendar file (.ics) |
| **Needs credentials** | Real ingestion code; activates when OAuth credentials are set | Google Calendar, Microsoft Outlook |
| **Architecture only** | Connector contract and permission model defined; no ingestion yet | CRM, Teams, Zoom, Meet, M365, Gmail, WhatsApp, OneDrive, SharePoint, Drive |

A provider reports `connected` only when `connection_store` holds a real
record for it. Architecture-only providers cannot be connected or synced —
the API returns 409 rather than pretending.

## Customer identity resolution

The critical piece. The same person arrives as a CRM ID, an email address, a
phone number, a calendar attendee, or a WhatsApp contact.

1. **Deterministic first.** An exact match on a normalized identifier
   (`crm_id`, `external_id`, `email`, `calendar_attendee`, `whatsapp`,
   `phone`) is the only thing that auto-resolves, because it is the only
   thing that is actually certain. Emails lowercase; phone numbers reduce to
   digits so `+65 9123 4567` and `6591234567` converge.
2. **Names propose, they never decide.** A name-only hit returns as a
   candidate with confidence 0.6 and `resolved=False`, surfaced as
   *"Customer match required."*
3. **Gemini assists only on the ambiguous middle.** It ranks an existing
   closed list of candidates. It cannot invent a `customer_id`, its score is
   capped below the name-match threshold, and it never sets `resolved=True`.

Confirmed matches are written back as `(:CustomerIdentity)` nodes, so an
advisor resolving a meeting once makes every future meeting with that
attendee resolve automatically.

## Provenance

Every imported item carries `source_system`, `source_id`, `imported_at`,
`customer_id`, and `original_reference` (a traceable pointer such as
`customers_import.csv:row4` or a calendar event URL). Relationships carry
their own `source`/`confidence`/`created_at`, matching the Stage 1 pattern.

## Security

- **OAuth** — authorization-code flow with single-use, expiring state
  parameters. Scopes come from the provider's registry declaration and are
  read-only; nothing can request more.
- **Encrypted credentials** — tokens are Fernet-encrypted before storage. If
  `INTEGRATION_ENCRYPTION_KEY` is absent, connecting an OAuth provider is
  refused rather than storing plaintext.
- **Disconnect/revoke** — revokes upstream where supported, then destroys the
  local credential regardless, so a failed remote call never leaves a usable
  token behind.
- **Audit logging** — connect, disconnect, sync, import, and match events
  persist as `(:AuditEvent)` nodes. Audit failures never break the operation
  they describe.
- **Retention** — `COMMUNICATION_RETENTION_DAYS` bounds how long raw email or
  chat bodies may be kept; enforcement lives on the ingestion side rather
  than trusting the source.

## Source-specific policy

- **Email** — consent is per mailbox and explicit; only threads resolving to
  a known customer are retained, so unrelated advisor mail never enters the
  graph.
- **Meeting platforms** — transcripts require both advisor ownership and
  workspace grant. A missing transcript is a normal outcome, never a reason
  to synthesize one.
- **WhatsApp** — official Business Platform API with webhook delivery only.
  Personal accounts are never scraped; there is no scraping path in the design.
- **Files** — contextual sources, never customer truth. A document is
  embedded so it can be *cited*; any fact drawn from one still travels the
  Stage 1 proposal-and-approval path. Source ACLs follow the indexed chunk.

## Timezone handling

Calendars deliver instants; advisors read a local clock. `integrations/timeutil.py`
converts using `DISPLAY_TIMEZONE` (default `Asia/Singapore`) for both the
displayed time and the stored `meeting_date`, so an 07:00 local meeting —
23:00 UTC the previous day — is not filed under yesterday. The `tzdata`
package is a dependency because Windows ships no IANA database and slim
Linux images often drop theirs.

## Success test

```bash
# 10 customers
curl -F "file=@sample_data/customers_import.csv" -F "dataset=customers" \
  http://127.0.0.1:3011/api/v3/import/csv/commit

# calendar with meetings
curl -F "file=@sample_data/calendar_today.ics" \
  http://127.0.0.1:3011/api/v3/import/calendar/ics

curl http://127.0.0.1:3011/api/v3/advisor/meetings/today
```

Verified result: **"You have 5 customer meetings today."** Each of the five
resolves to the correct customer by attendee email. The sample file
deliberately includes a sixth event with a non-customer attendee, which is
flagged *"Customer match required."* rather than guessed — resolving it from
`/advisor/meetings/match` teaches the identity for next time.

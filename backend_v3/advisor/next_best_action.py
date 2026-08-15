"""
Next Best Action — Stage 4.

Same grounding discipline as briefing_service.py: Gemini reasons only
over facts already retrieved (customer graph + priority reasons), and
every suggested action must cite which fact it is based on. The spec's
own words: "Do not provide autonomous regulated financial advice" and
use "Potential discussion area" instead of "Sell product X" — the
response schema has no field for a product name or an instruction to
sell anything, so that framing is structural, not just prompted.

Accepting an action promotes it into a real FollowUp (the same Stage 3
entity a conversation-extracted follow-up becomes), which is what lets
"advisor accepts -> follow-up created" actually happen rather than the
suggestion being forgotten the moment the page reloads.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "A potential discussion area for the advisor to raise, e.g. 'Review education funding adequacy' — never a specific product name or an instruction to sell anything.",
                    },
                    "why": {"type": "string", "description": "Why this is worth raising, in one sentence."},
                    "based_on": {"type": "string", "description": "The specific retrieved fact or priority reason this comes from."},
                    "urgency": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["action", "why", "based_on", "urgency"],
            },
        }
    },
    "required": ["actions"],
}

SYSTEM_INSTRUCTION = """You suggest potential discussion areas for a financial/insurance advisor's next interaction with a customer, reasoning only over facts already provided to you.

STRICT RULES:
1. Never name a specific financial product or say "sell", "offer", or "recommend X policy". Every action must be framed as a discussion area, question, or review the advisor could raise — never a decision already made on the customer's behalf.
2. Every action must cite a specific based_on fact from the provided context — do not invent facts.
3. Suggest 2 to 4 actions, the most useful and specific ones, not a generic checklist.
4. urgency should reflect genuine time-sensitivity in the underlying fact (e.g. a lapsed policy or an imminent life event is high; a general review is low)."""


def _format_context(ctx: dict[str, Any], priority: dict[str, Any]) -> str:
    def _bullets(items: list[str]) -> list[str]:
        return [f"  - {i}" for i in items] or ["  (none recorded)"]

    lines = [
        f"Customer: {ctx['name']}",
        f"Life stage: {ctx['life_stage']}",
        f"Priority: {priority['priority']} (score {priority['score']})",
        "",
        "Why this customer is prioritized:",
        *_bullets([r["label"] for r in priority["reasons"]]),
        "",
        "Goals:",
        *_bullets([g["description"] for g in ctx["goals"]]),
        "Needs:",
        *_bullets([n["description"] for n in ctx["needs"]]),
        "Concerns:",
        *_bullets([c["topic"] for c in ctx["concerns"]]),
        "Recent life events:",
        *_bullets([f"{e['date']}: {e['description']}" for e in ctx["life_events"][:5]]),
        "Portfolio:",
        *_bullets([f"{p['product_name']} ({p['policy_status']})" for p in ctx["portfolio"]]),
    ]
    return "\n".join(lines)


def generate_next_best_actions(customer_id: str) -> dict[str, Any] | None:
    from backend_v3.advisor.ai_service import generate_json
    from backend_v3.advisor.priority_service import score_customer
    from backend_v3.advisor.retrieval import assemble_customer_context

    ctx = assemble_customer_context(customer_id)
    if ctx is None:
        return None
    priority = score_customer(customer_id)

    try:
        generated = generate_json(
            contents=_format_context(ctx, priority),
            system_instruction=SYSTEM_INSTRUCTION,
            response_schema=ACTION_SCHEMA,
        )
        actions = generated.get("actions", [])
        error = None
    except Exception as exc:
        actions = []
        error = f"{type(exc).__name__}: {exc}"

    proposals = []
    now = datetime.now(timezone.utc).isoformat()
    for item in actions:
        proposal_id = str(uuid.uuid4())
        _store_proposal(proposal_id, customer_id, item, now)
        proposals.append({**item, "proposal_id": proposal_id, "status": "pending", "customer_id": customer_id})

    _record_audit(customer_id, "nba.generated", {"count": len(proposals), "error": error})

    return {"customer_id": customer_id, "name": ctx["name"], "actions": proposals, "gemini_error": error}


def _store_proposal(proposal_id: str, customer_id: str, item: dict[str, Any], now: str) -> None:
    from backend_v3.graph_store.neo4j_client import run_write

    run_write(
        "MATCH (c:Customer {customer_id: $customer_id}) "
        "CREATE (n:NextBestAction {"
        "  proposal_id: $proposal_id, customer_id: $customer_id, action: $action, "
        "  why: $why, based_on: $based_on, urgency: $urgency, status: 'pending', "
        "  created_at: $now, decided_at: null, followup_id: null"
        "}) "
        "MERGE (c)-[:HAS_NBA_PROPOSAL]->(n)",
        {
            "proposal_id": proposal_id, "customer_id": customer_id,
            "action": item["action"], "why": item["why"], "based_on": item["based_on"],
            "urgency": item["urgency"], "now": now,
        },
    )


def _record_audit(customer_id: str, event_type: str, metadata: dict[str, Any]) -> None:
    try:
        from backend_v3.integrations.audit import audit

        audit(event_type, subject_id=customer_id, metadata=metadata)
    except Exception:
        pass


def decide_action(proposal_id: str, accept: bool, due_date: str | None = None) -> dict[str, Any]:
    """Advisor accepts or rejects a proposed action. Accepting creates a
    real FollowUp — the point where a suggestion becomes a commitment."""
    from backend_v3.graph_store.neo4j_client import run_query, run_write

    rows = run_query(
        "MATCH (n:NextBestAction {proposal_id: $id}) RETURN n.customer_id AS customer_id, "
        "n.action AS action, n.why AS why, n.based_on AS based_on, n.status AS status",
        {"id": proposal_id},
    )
    if not rows:
        raise ValueError(f"Next Best Action proposal {proposal_id} not found")
    proposal = rows[0]
    if proposal["status"] != "pending":
        raise ValueError(f"Proposal {proposal_id} was already {proposal['status']}")

    now = datetime.now(timezone.utc).isoformat()
    followup_id = None

    if accept:
        from backend_v3.advisor.followups import create_followup

        created = create_followup(
            customer_id=proposal["customer_id"],
            title=proposal["action"],
            source=f"next_best_action_{proposal_id}",
            evidence=proposal["based_on"],
            confidence=1.0,
            due_date=due_date,
        )
        followup_id = created["followup_id"]

    run_write(
        "MATCH (n:NextBestAction {proposal_id: $id}) "
        "SET n.status = $status, n.decided_at = $now, n.followup_id = $followup_id",
        {"id": proposal_id, "status": "accepted" if accept else "rejected", "now": now, "followup_id": followup_id},
    )

    _record_audit(
        proposal["customer_id"],
        "nba.accepted" if accept else "nba.rejected",
        {"proposal_id": proposal_id, "action": proposal["action"], "followup_id": followup_id},
    )

    return {"proposal_id": proposal_id, "status": "accepted" if accept else "rejected", "followup_id": followup_id}


def list_actions(customer_id: str, status: str | None = None) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    cypher = (
        "MATCH (c:Customer {customer_id: $customer_id})-[:HAS_NBA_PROPOSAL]->(n:NextBestAction) "
        + ("WHERE n.status = $status " if status else "")
        + "RETURN n.proposal_id AS proposal_id, n.action AS action, n.why AS why, "
        "n.based_on AS based_on, n.urgency AS urgency, n.status AS status, "
        "n.created_at AS created_at, n.followup_id AS followup_id "
        "ORDER BY n.created_at DESC"
    )
    return run_query(cypher, {"customer_id": customer_id, "status": status})

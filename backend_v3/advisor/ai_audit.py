"""
AI insight auditability — Stage 4.

"For every AI insight record: customer, agent, timestamp, source, model,
output, confidence, human decision."

Rather than introduce a parallel audit store, this reads the three places
Gemini already touches the product and normalizes them into one shape:

  - PendingMemory   (conversation_intelligence extraction -> memory_model
                     approve/reject) — human_decision is the memory's own
                     status field, which already IS the human decision.
  - NextBestAction  (next_best_action generation -> accept/reject)
  - Briefing views  (briefing_service generation) — a briefing has no
                     accept/reject step, so human_decision is 'viewed'
                     rather than blank; confidence is not meaningful for
                     a synthesized document the way it is for a single
                     extracted fact, so it is left null rather than
                     invented.

This keeps the audit trail truthful to what actually happened instead of
maintaining a second copy of the same facts that could drift out of sync.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.config import GEMINI_MODEL


def _memory_rows(customer_id: str | None) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    where = "WHERE c.customer_id = $customer_id " if customer_id else ""
    rows = run_query(
        f"MATCH (c:Customer)-[:HAS_PENDING_MEMORY]->(m:PendingMemory) {where}"
        "RETURN c.customer_id AS customer_id, c.name AS customer_name, c.advisor_name AS agent, "
        "m.memory_id AS record_id, m.memory_type AS insight_type, m.value AS output, "
        "m.evidence AS source, m.confidence AS confidence, m.created_at AS timestamp, "
        "m.status AS human_decision",
        {"customer_id": customer_id},
    )
    for row in rows:
        row["kind"] = "memory_extraction"
        row["model"] = GEMINI_MODEL
    return rows


def _nba_rows(customer_id: str | None) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    where = "WHERE c.customer_id = $customer_id " if customer_id else ""
    rows = run_query(
        f"MATCH (c:Customer)-[:HAS_NBA_PROPOSAL]->(n:NextBestAction) {where}"
        "RETURN c.customer_id AS customer_id, c.name AS customer_name, c.advisor_name AS agent, "
        "n.proposal_id AS record_id, 'next_best_action' AS insight_type, n.action AS output, "
        "n.based_on AS source, n.urgency AS confidence, n.created_at AS timestamp, "
        "n.status AS human_decision",
        {"customer_id": customer_id},
    )
    for row in rows:
        row["kind"] = "next_best_action"
        row["model"] = GEMINI_MODEL
        # NextBestAction has no numeric confidence field (urgency instead);
        # null is honest rather than inventing a number.
        row["confidence"] = None
    return rows


def _briefing_rows(customer_id: str | None) -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    filter_clause = "AND c.customer_id = $customer_id " if customer_id else ""
    rows = run_query(
        "MATCH (c:Customer) WHERE c.last_prepared_date IS NOT NULL "
        + filter_clause
        + "RETURN c.customer_id AS customer_id, c.name AS customer_name, c.advisor_name AS agent, "
        "c.last_prepared_at AS timestamp",
        {"customer_id": customer_id},
    )
    out = []
    for row in rows:
        out.append({
            **row,
            "kind": "meeting_briefing",
            "record_id": f"briefing_{row['customer_id']}_{row['timestamp']}",
            "insight_type": "briefing",
            "output": "Meeting briefing generated (who_is_customer, what_changed, suggested_questions, discussion areas)",
            "source": "full customer context",
            "model": GEMINI_MODEL,
            "confidence": None,
            "human_decision": "viewed",
        })
    return out


def list_ai_audit_trail(customer_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    rows = _memory_rows(customer_id) + _nba_rows(customer_id) + _briefing_rows(customer_id)
    rows.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    return rows[:limit]


def ai_kpis() -> dict[str, Any]:
    """AI-category KPIs — summary_acceptance, memory approval/rejection,
    correction rate, recommendation acceptance — all counted from the
    same real rows list_ai_audit_trail reads, never fabricated."""
    memories = _memory_rows(None)
    nba = _nba_rows(None)

    decided_memories = [m for m in memories if m["human_decision"] != "pending"]
    accepted = sum(1 for m in decided_memories if m["human_decision"] == "accepted")
    edited = sum(1 for m in decided_memories if m["human_decision"] == "edited")
    rejected = sum(1 for m in decided_memories if m["human_decision"] == "rejected")
    decided_count = len(decided_memories)

    decided_nba = [n for n in nba if n["human_decision"] != "pending"]
    nba_accepted = sum(1 for n in decided_nba if n["human_decision"] == "accepted")

    return {
        "memory_proposals_total": len(memories),
        "memory_proposals_decided": decided_count,
        "memory_approval_rate": round(100 * accepted / decided_count) if decided_count else None,
        "memory_rejection_rate": round(100 * rejected / decided_count) if decided_count else None,
        "memory_correction_rate": round(100 * edited / decided_count) if decided_count else None,
        "next_best_action_total": len(nba),
        "next_best_action_decided": len(decided_nba),
        "recommendation_acceptance_rate": round(100 * nba_accepted / len(decided_nba)) if decided_nba else None,
    }

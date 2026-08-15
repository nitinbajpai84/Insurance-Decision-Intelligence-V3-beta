"""
Business KPI dashboard — Stage 4.

Every number here is computed from real graph/DuckDB state at request
time, not fabricated or hardcoded. Where this system genuinely cannot
measure something yet (e.g. "customer complaints" has no complaints
intake anywhere in the product), the KPI is returned as `null` with a
`reason` explaining the gap, rather than inventing a plausible-looking
number — a fabricated guardrail metric would be worse than an honestly
missing one.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _agent_kpis() -> dict[str, Any]:
    from backend_v3.advisor.customer_service import list_customer_summaries
    from backend_v3.advisor.followups import list_followups
    from backend_v3.graph_store.neo4j_client import run_query

    customers = list_customer_summaries()
    advisors = {c.get("advisor_name") for c in customers if c.get("advisor_name")}

    prepared_rows = run_query(
        "MATCH (c:Customer) WHERE c.last_prepared_date IS NOT NULL RETURN count(c) AS n", {}
    )
    prepared_count = prepared_rows[0]["n"] if prepared_rows else 0
    adoption_pct = round(100 * prepared_count / len(customers)) if customers else None

    all_followups = list_followups()
    completed = sum(1 for f in all_followups if f["status"] == "completed")
    completion_pct = round(100 * completed / len(all_followups)) if all_followups else None

    return {
        "active_agents": len(advisors) or None,
        "ai_meeting_preparation_adoption_percent": adoption_pct,
        "customers_prepared": prepared_count,
        "customers_total": len(customers),
        "average_preparation_time_seconds": None,
        "average_preparation_time_reason": "Not instrumented — briefing generation does not currently record request duration.",
        "followup_completion_percent": completion_pct,
        "followups_total": len(all_followups),
        "followups_completed": completed,
    }


def _customer_kpis() -> dict[str, Any]:
    """Aggregate coverage/freshness across every customer in two queries
    total, not two per customer.

    The original version called compute_coverage()/compute_freshness()
    in a loop — each of those does 5-6 Neo4j round trips, a Qdrant
    semantic search, and 2 DuckDB queries for one customer's *authoritative*
    view (correct, and still what Customer 360 uses). For a fleet-wide
    average, presence-in-the-graph is the same real signal without the
    per-customer network cost, so this reimplements the same nine
    categories and the same freshness threshold as bulk Cypher instead.
    """
    from backend_v3.advisor.customer_service import list_customer_summaries
    from backend_v3.advisor.knowledge_coverage import FRESHNESS_STALE_DAYS
    from backend_v3.graph_store.neo4j_client import run_query

    customers = list_customer_summaries()

    coverage_rows = run_query(
        "MATCH (c:Customer) "
        "OPTIONAL MATCH (c)-[:HAS_FAMILY_MEMBER]->(fam) "
        "OPTIONAL MATCH (c)-[:HAS_GOAL]->(g) "
        "OPTIONAL MATCH (c)-[:HAS_NEED]->(n) "
        "OPTIONAL MATCH (c)-[:OWNS]->(p) "
        "OPTIONAL MATCH (c)-[:DISCUSSED]->(t) "
        "OPTIONAL MATCH (c)-[:EXPERIENCED]->(e) "
        "OPTIONAL MATCH (c)-[:HAD_MEETING]->(m) "
        "OPTIONAL MATCH (c)-[:HAD_CONVERSATION]->(conv) "
        "RETURN c.customer_id AS customer_id, c.life_stage AS life_stage, "
        "count(DISTINCT fam) AS family_n, count(DISTINCT g) AS goals_n, "
        "count(DISTINCT n) AS needs_n, count(DISTINCT p) AS policy_n, "
        "count(DISTINCT t) AS topic_n, count(DISTINCT e) AS event_n, "
        "count(DISTINCT m) AS meeting_n, count(DISTINCT conv) AS conversation_n",
        {},
    )

    coverage_percents = []
    total_needs = 0
    total_events = 0
    total_conversations = 0
    for row in coverage_rows:
        present = [
            True,  # Profile — the customer exists
            bool(row["family_n"]),
            bool(row["life_stage"]),
            bool(row["policy_n"]),  # Financial
            bool(row["goals_n"]),
            bool(row["needs_n"]),
            bool(row["topic_n"]),  # Preferences
            bool(row["event_n"]),  # Recent events
            bool(row["meeting_n"]) or bool(row["conversation_n"]),  # Relationship history
        ]
        coverage_percents.append(round(100 * sum(present) / len(present)))
        total_needs += row["needs_n"]
        total_events += row["event_n"]
        total_conversations += row["conversation_n"]

    avg_coverage = round(sum(coverage_percents) / len(coverage_percents)) if coverage_percents else None

    freshness_rows = run_query(
        "MATCH (:Customer)-[r]->(n) "
        "WHERE type(r) IN ['HAS_GOAL','HAS_NEED','EXPERIENCED','CONCERNED_ABOUT','HAS_FAMILY_MEMBER'] "
        "  AND r.created_at IS NOT NULL "
        "RETURN r.created_at AS created_at",
        {},
    )
    from backend_v3.advisor.knowledge_coverage import _months_ago

    stale = current = 0
    for row in freshness_rows:
        months = _months_ago(row["created_at"])
        if months is None:
            continue
        if months * 30 >= FRESHNESS_STALE_DAYS:
            stale += 1
        else:
            current += 1
    freshness_pct = round(100 * current / (stale + current)) if (stale + current) else None

    return {
        "average_knowledge_coverage_percent": avg_coverage,
        "average_memory_freshness_percent": freshness_pct,
        "total_conversations_captured": total_conversations,
        "total_needs_identified": total_needs,
        "total_life_events_recorded": total_events,
        "customers_total": len(customers),
    }


def _ai_kpis() -> dict[str, Any]:
    from backend_v3.advisor.ai_audit import ai_kpis

    base = ai_kpis()
    return {
        "summary_acceptance_percent": None,
        "summary_acceptance_reason": "Briefings have no explicit accept/reject step — advisors act on them directly rather than approving the summary itself.",
        "memory_approval_rate_percent": base["memory_approval_rate"],
        "memory_rejection_rate_percent": base["memory_rejection_rate"],
        "memory_correction_rate_percent": base["memory_correction_rate"],
        "recommendation_acceptance_rate_percent": base["recommendation_acceptance_rate"],
        "memory_proposals_total": base["memory_proposals_total"],
        "memory_proposals_decided": base["memory_proposals_decided"],
        "next_best_action_total": base["next_best_action_total"],
        "next_best_action_decided": base["next_best_action_decided"],
    }


def _business_kpis() -> dict[str, Any]:
    from backend_v3.advisor.followups import list_followups
    from backend_v3.graph_store.neo4j_client import run_query

    meetings_rows = run_query("MATCH (m:CalendarEvent) RETURN count(m) AS n", {})
    matched_rows = run_query("MATCH (m:CalendarEvent {match_status:'matched'}) RETURN count(m) AS n", {})
    nba_rows = run_query("MATCH (n:NextBestAction) RETURN count(n) AS n", {})

    return {
        "calendar_meetings_ingested": meetings_rows[0]["n"] if meetings_rows else 0,
        "calendar_meetings_matched_to_customer": matched_rows[0]["n"] if matched_rows else 0,
        "opportunities_identified": nba_rows[0]["n"] if nba_rows else 0,
        "followups_created": len(list_followups()),
        "conversions_tracked": None,
        "conversions_reason": "No product-sale or policy-conversion event exists in this schema yet.",
    }


def _guardrail_kpis() -> dict[str, Any]:
    """Guardrails this system can actually measure today, stated
    honestly where it cannot."""
    from backend_v3.advisor.ai_audit import ai_kpis

    base = ai_kpis()
    return {
        "memory_rejection_rate_percent": base["memory_rejection_rate"],
        "memory_rejection_rate_note": "A rejected AI proposal is the closest signal this product has to 'incorrect information caught before it became truth.'",
        "customer_complaints": None,
        "customer_complaints_reason": "No complaints intake exists in this product.",
        "recommendation_rejection_rate_percent": (
            round(100 - base["recommendation_acceptance_rate"]) if base["recommendation_acceptance_rate"] is not None else None
        ),
        "consent_exceptions": None,
        "consent_exceptions_reason": "No consent-exception tracking exists yet — email/WhatsApp ingestion enforce consent at connection time but do not log denials.",
    }


def get_kpi_dashboard() -> dict[str, Any]:
    return {
        "agent": _agent_kpis(),
        "customer": _customer_kpis(),
        "ai": _ai_kpis(),
        "business": _business_kpis(),
        "guardrails": _guardrail_kpis(),
    }

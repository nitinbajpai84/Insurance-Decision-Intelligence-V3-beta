"""
Project the underwriting spine from DuckDB into the context graph.

Division of labour, deliberately:

  DuckDB answers "is this rule leaking?" -- a portfolio aggregate over tens of
  thousands of rows, which is what a columnar store is for.

  Neo4j answers "why was THIS policy accepted?" -- a short walk from a claim
  back through the policy, the decision, and the rule version that governed it.
  That walk is what makes a single case explainable to an underwriter.

Only the advisor's own book is projected. Mirroring all 12,000 policies would
duplicate the warehouse into the graph for no gain: nothing traverses a policy
the advisor does not hold.
"""
from __future__ import annotations

from typing import Any

from backend_v3.graph_store.neo4j_client import run_query, run_write
from backend_v3.structured_store.duckdb_client import get_connection


def _graph_policy_ids() -> list[str]:
    return [
        r["pid"]
        for r in run_query("MATCH (p:Policy) RETURN p.policy_id AS pid")
        if r.get("pid")
    ]


def sync_underwriting_spine() -> dict[str, int]:
    """
    Mirror rules, decisions and claims for policies already in the graph.

    Idempotent -- MERGE on stable ids, so re-running updates in place rather
    than duplicating.
    """
    policy_ids = _graph_policy_ids()
    if not policy_ids:
        return {"rules": 0, "decisions": 0, "claims": 0, "policies": 0}

    con = get_connection()
    try:
        rules = [
            {
                "rule_id": r[0], "rule_key": r[1], "version": r[2], "name": r[3],
                "action": r[4], "status": r[5],
                "effective_from": r[6].isoformat() if r[6] else None,
                "effective_to": r[7].isoformat() if r[7] else None,
            }
            for r in con.execute(
                "select rule_id, rule_key, version, name, action, status,"
                " effective_from, effective_to from uw_rules"
            ).fetchall()
        ]

        placeholders = ",".join(["?"] * len(policy_ids))
        decisions = [
            {
                "policy_id": r[0],
                "rule_id": r[1],
                "props": {
                    "decision_id": r[2],
                    "application_id": r[3],
                    "decision_status": r[4],
                    "risk_class": r[5],
                    "risk_score": r[6],
                    "auto_decided": bool(r[7]) if r[7] is not None else None,
                    "leaked_cohort": bool(r[8]) if r[8] is not None else False,
                    "decision_date": r[9].isoformat() if r[9] else None,
                    "rating_factor": r[10],
                },
            }
            for r in con.execute(
                f"""
                select p.policy_id, ud.rule_id_applied, ud.underwriting_decision_id,
                       ud.application_id, ud.decision_status, ud.risk_class, ud.risk_score,
                       ud.auto_decided, ud.leaked_cohort, ud.decision_date, ud.rating_factor
                from policies p
                join underwriting_decisions ud on ud.application_id = p.application_id
                where p.policy_id in ({placeholders})
                """,
                policy_ids,
            ).fetchall()
        ]

        claims = [
            {
                "policy_id": r[0],
                "props": {
                    "claim_id": r[1],
                    "claim_number": r[2],
                    "claim_status": r[3],
                    "loss_cause": r[4],
                    "paid_amount": r[5],
                    "policy_duration_months": r[6],
                    "loss_date": r[7].isoformat() if r[7] else None,
                },
            }
            for r in con.execute(
                f"""
                select policy_id, claim_id, claim_number, claim_status, loss_cause,
                       paid_amount, policy_duration_months, loss_date
                from claims where policy_id in ({placeholders})
                """,
                policy_ids,
            ).fetchall()
        ]
    finally:
        con.close()

    if rules:
        run_write(
            "UNWIND $rows AS r "
            "MERGE (ur:UnderwritingRule {rule_id: r.rule_id}) "
            "SET ur.rule_key = r.rule_key, ur.version = r.version, ur.name = r.name, "
            "    ur.action = r.action, ur.status = r.status, "
            "    ur.effective_from = r.effective_from, ur.effective_to = r.effective_to",
            {"rows": rules},
        )

    if decisions:
        run_write(
            "UNWIND $rows AS d "
            "MATCH (p:Policy {policy_id: d.policy_id}) "
            "MERGE (ud:UnderwritingDecision {decision_id: d.props.decision_id}) "
            "SET ud += d.props "
            "MERGE (ud)-[:ISSUED]->(p) "
            "WITH ud, d WHERE d.rule_id IS NOT NULL "
            "MATCH (ur:UnderwritingRule {rule_id: d.rule_id}) "
            "MERGE (ud)-[:APPLIED_RULE]->(ur)",
            {"rows": decisions},
        )

    if claims:
        run_write(
            "UNWIND $rows AS c "
            "MATCH (p:Policy {policy_id: c.policy_id}) "
            "MERGE (cl:Claim {claim_id: c.props.claim_id}) "
            "SET cl += c.props "
            "MERGE (p)-[:HAS_CLAIM]->(cl)",
            {"rows": claims},
        )

    return {
        "policies": len(policy_ids),
        "rules": len(rules),
        "decisions": len(decisions),
        "claims": len(claims),
    }


def trace_claim_to_underwriting(claim_id: str) -> dict[str, Any] | None:
    """
    Walk a claim back to the decision and rule version that accepted the risk.

    This is the per-case half of the claims-to-underwriting loop: not "is the
    rule leaking" but "on what basis did we take this particular risk".
    """
    rows = run_query(
        "MATCH (cl:Claim {claim_id: $claim_id})<-[:HAS_CLAIM]-(p:Policy) "
        "OPTIONAL MATCH (ud:UnderwritingDecision)-[:ISSUED]->(p) "
        "OPTIONAL MATCH (ud)-[:APPLIED_RULE]->(ur:UnderwritingRule) "
        "OPTIONAL MATCH (c:Customer)-[:OWNS]->(p) "
        "RETURN cl.claim_id AS claim_id, cl.loss_date AS loss_date, "
        "       cl.policy_duration_months AS duration_months, cl.paid_amount AS paid_amount, "
        "       p.policy_id AS policy_id, p.product_name AS product_name, "
        "       c.customer_id AS customer_id, c.name AS customer_name, "
        "       ud.decision_id AS decision_id, ud.decision_status AS decision_status, "
        "       ud.risk_score AS risk_score, ud.risk_class AS risk_class, "
        "       ud.auto_decided AS auto_decided, ud.leaked_cohort AS leaked_cohort, "
        "       ud.application_id AS application_id, "
        "       ur.rule_id AS rule_id, ur.rule_key AS rule_key, ur.version AS rule_version, "
        "       ur.name AS rule_name, ur.effective_from AS rule_effective_from, "
        "       ur.effective_to AS rule_effective_to, ur.status AS rule_status "
        "LIMIT 1",
        {"claim_id": claim_id},
    )
    return rows[0] if rows else None


def spine_stats() -> dict[str, Any]:
    """What is actually projected, for the health check and for tests."""
    row = run_query(
        "OPTIONAL MATCH (ur:UnderwritingRule) WITH count(ur) AS rules "
        "OPTIONAL MATCH (ud:UnderwritingDecision) WITH rules, count(ud) AS decisions "
        "OPTIONAL MATCH (:UnderwritingDecision)-[i:ISSUED]->(:Policy) "
        "WITH rules, decisions, count(i) AS issued_links "
        "OPTIONAL MATCH (:Policy)-[h:HAS_CLAIM]->(:Claim) "
        "RETURN rules, decisions, issued_links, count(h) AS claim_links"
    )
    return row[0] if row else {}

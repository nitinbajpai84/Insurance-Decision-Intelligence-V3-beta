"""
Evidence-to-decision underwriting copilot (U1).

The system recommends; an underwriter decides. Every recommendation carries the
rule versions it evaluated and why each one did or did not fire, so a referral
arrives already argued rather than as a bare score. Overrides are first-class:
they are the signal that the rules and the humans disagree, and they are logged
as such.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from backend_v3.risk import decision_log
from backend_v3.risk.rules_store import list_rules
from backend_v3.structured_store.duckdb_client import get_connection

# Decisions an underwriter can record. Keep in step with seed_risk_chain.
TERMINAL_DECISIONS = (
    "approved_standard",
    "approved_rated",
    "approved_exclusion",
    "postponed",
    "declined",
)

_CASE_SELECT = """
select a.application_id, a.application_number, a.application_date, a.application_status,
       a.requested_premium, a.requested_sum_assured, a.medical_required,
       a.customer_id, pt.display_name, c.customer_segment, c.risk_tier,
       a.product_id, pr.product_name, pr.line_of_business,
       ud.underwriting_decision_id, ud.decision_status, ud.risk_score, ud.risk_class,
       ud.rating_factor, ud.exclusion_applied, ud.auto_decided, ud.rule_id_applied,
       ud.decision_date, ud.underwriting_reason
from applications a
join underwriting_decisions ud on ud.application_id = a.application_id
left join customers c on c.customer_id = a.customer_id
left join parties   pt on pt.party_id = c.party_id
left join products  pr on pr.product_id = a.product_id
"""


def _row_to_case(row: tuple) -> dict[str, Any]:
    return {
        "application_id": row[0],
        "application_number": row[1],
        "application_date": row[2].isoformat() if row[2] else None,
        "application_status": row[3],
        "requested_premium": row[4],
        "requested_sum_assured": row[5],
        "medical_required": bool(row[6]) if row[6] is not None else None,
        "customer_id": row[7],
        "customer_name": row[8],
        "customer_segment": row[9],
        "risk_tier": row[10],
        "product_id": row[11],
        "product_name": row[12],
        "line_of_business": row[13],
        "decision_id": row[14],
        "decision_status": row[15],
        "risk_score": row[16],
        "risk_class": row[17],
        "rating_factor": row[18],
        "exclusion_applied": bool(row[19]) if row[19] is not None else None,
        "auto_decided": bool(row[20]) if row[20] is not None else None,
        "rule_id_applied": row[21],
        "decision_date": row[22].isoformat() if row[22] else None,
        "underwriting_reason": row[23],
    }


# --------------------------------------------------------------------------
# rule evaluation
# --------------------------------------------------------------------------

def evaluate(risk_score: float, on: date | None = None) -> dict[str, Any]:
    """
    Run the rules in force on `on` against a score.

    Returns the recommendation and a trace of every rule considered -- including
    the ones that did not fire. An underwriter needs to see what was ruled out,
    not only what was chosen; "no rule mentioned it" and "a rule considered it
    and declined to act" are different statements.
    """
    when = on or date.today()
    considered: list[dict[str, Any]] = []
    decline_hit = stp_hit = None

    for rule in list_rules():
        frm = date.fromisoformat(rule["effective_from"]) if rule["effective_from"] else None
        to = date.fromisoformat(rule["effective_to"]) if rule["effective_to"] else None
        in_force = (frm is None or frm <= when) and (to is None or to >= when)
        cond = rule.get("condition") or {}
        threshold = cond.get("value") if isinstance(cond, dict) else None

        fired = False
        if in_force and threshold is not None:
            if rule["action"] == "decline" and risk_score >= threshold:
                fired, decline_hit = True, rule
            elif rule["action"] == "auto_approve" and risk_score < threshold:
                fired, stp_hit = True, rule

        considered.append({
            "rule_id": rule["rule_id"],
            "rule_key": rule["rule_key"],
            "version": rule["version"],
            "name": rule["name"],
            "action": rule["action"],
            "threshold": threshold,
            "in_force_on": when.isoformat(),
            "in_force": in_force,
            "fired": fired,
            "why": _explain(rule, threshold, risk_score, in_force, fired),
        })

    if decline_hit:
        decision, governing = "declined", decline_hit
    elif stp_hit:
        decision, governing = "approved_standard", stp_hit
    else:
        decision = "refer"
        governing = next(
            (r for r in list_rules() if r["action"] == "refer" and r["status"] == "active"), None
        )

    return {
        "risk_score": risk_score,
        "recommendation": decision,
        "requires_underwriter": decision == "refer",
        "governing_rule_id": governing["rule_id"] if governing else None,
        "governing_rule": f"{governing['rule_key']} v{governing['version']}" if governing else None,
        "evaluated_on": when.isoformat(),
        "trace": considered,
    }


def _explain(rule: dict, threshold: float | None, score: float, in_force: bool, fired: bool) -> str:
    if not in_force:
        window = f"{rule['effective_from']} to {rule['effective_to'] or 'present'}"
        return f"Not in force on this date (applies {window})."
    if threshold is None:
        return "No numeric threshold; applies as the fallback band."
    op = ">=" if rule["action"] == "decline" else "<"
    verdict = "fired" if fired else "did not fire"
    return f"Score {score:.3f} {op} {threshold} is {str(fired).lower()}, so it {verdict}."


# --------------------------------------------------------------------------
# queue and case detail
# --------------------------------------------------------------------------

def list_cases(
    status: str | None = None,
    awaiting_only: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    The underwriting queue.

    `awaiting_only` narrows to cases the rules referred to a human and nobody
    has decided yet -- the actual work list, as opposed to the audit trail of
    everything already decided.
    """
    clauses, params = [], []
    if awaiting_only:
        clauses.append("ud.decision_status = 'pending_review'")
    elif status:
        clauses.append("ud.decision_status = ?")
        params.append(status)

    sql = _CASE_SELECT
    if clauses:
        sql += " where " + " and ".join(clauses)
    # Riskiest first: a queue sorted by arrival buries the cases that matter.
    sql += " order by ud.risk_score desc nulls last, a.application_date desc limit ?"
    params.append(limit)

    con = get_connection()
    try:
        return [_row_to_case(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def get_case(application_id: str) -> dict[str, Any] | None:
    """One case, with its recommendation and full decision trail."""
    con = get_connection()
    try:
        row = con.execute(
            _CASE_SELECT + " where a.application_id = ?", [application_id]
        ).fetchone()
    finally:
        con.close()
    if not row:
        return None

    case = _row_to_case(row)
    decided_on = (
        date.fromisoformat(case["application_date"]) if case["application_date"] else None
    )
    if case["risk_score"] is not None:
        case["assessment"] = evaluate(case["risk_score"], on=decided_on)
    case["trail"] = decision_log.decision_trail(application_id)
    case["policy"] = _issued_policy(application_id)
    return case


def _issued_policy(application_id: str) -> dict[str, Any] | None:
    con = get_connection()
    try:
        row = con.execute(
            """
            select p.policy_id, p.policy_number, p.policy_status, p.effective_date,
                   p.annual_premium,
                   (select count(*) from claims c where c.policy_id = p.policy_id) as claim_count
            from policies p where p.application_id = ?
            """,
            [application_id],
        ).fetchone()
    finally:
        con.close()
    if not row:
        return None
    return {
        "policy_id": row[0],
        "policy_number": row[1],
        "policy_status": row[2],
        "effective_date": row[3].isoformat() if row[3] else None,
        "annual_premium": row[4],
        "claim_count": row[5],
    }


# --------------------------------------------------------------------------
# the human decision
# --------------------------------------------------------------------------

def record_decision(
    application_id: str,
    decision: str,
    *,
    actor: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """
    Record an underwriter's decision.

    If it contradicts what the rules recommended, it is logged as an override
    with its reason. That disagreement is the most informative event the system
    produces -- it is how the rules learn they are wrong.
    """
    if decision not in TERMINAL_DECISIONS:
        raise ValueError(f"unknown decision {decision!r}; expected one of {TERMINAL_DECISIONS}")

    case = get_case(application_id)
    if case is None:
        raise LookupError(f"no such application: {application_id}")

    recommended = (case.get("assessment") or {}).get("recommendation")
    # "refer" is a request for judgement, not a recommendation to contradict.
    is_override = recommended not in (None, "refer") and recommended != decision
    if is_override and not reason:
        raise ValueError("overriding the recommendation requires a reason")

    con = get_connection(read_only=False)
    try:
        con.execute(
            """
            update underwriting_decisions
               set decision_status = ?, auto_decided = false, underwriting_reason = ?
             where application_id = ?
            """,
            [decision, reason or f"Underwriter decision by {actor}", application_id],
        )
        con.commit()
    finally:
        con.close()

    event = decision_log.append_event(
        application_id,
        "overridden" if is_override else "underwriter_decision",
        decision=decision,
        risk_score=case.get("risk_score"),
        rules_fired=[case["assessment"]["governing_rule_id"]] if case.get("assessment") else [],
        actor=actor,
        actor_type="underwriter",
        is_override=is_override,
        override_reason=reason if is_override else None,
    )
    return {
        "application_id": application_id,
        "decision": decision,
        "recommended": recommended,
        "was_override": is_override,
        "event": event,
    }


def queue_summary() -> dict[str, Any]:
    """Counts for the queue header."""
    con = get_connection()
    try:
        row = con.execute(
            """
            select
              count(*) filter (where decision_status = 'pending_review') as awaiting,
              count(*) filter (where auto_decided = true)                as auto_decided,
              count(*)                                                   as total,
              round(avg(risk_score), 4)                                  as avg_score
            from underwriting_decisions
            """
        ).fetchone()
    finally:
        con.close()
    awaiting, auto, total, avg = row
    return {
        "awaiting_review": awaiting,
        "auto_decided": auto,
        "total_cases": total,
        "straight_through_rate": round(auto / total, 4) if total else None,
        "average_risk_score": avg,
    }

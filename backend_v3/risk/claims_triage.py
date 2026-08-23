"""
Claims triage and early warning (C1).

Same discipline as the advisor priority model: additive point weights, every
one tied to a reason an assessor can check against the claim record. No fitted
model, no opaque score. If the queue says a claim needs attention, it says why,
and the assessor can disagree with the stated reason rather than with a number.

The early-duration signal deliberately crosses domains. A loss inside the
contestable window is not just a claims fact -- it is a question about the
underwriting decision that accepted the risk, and the reason text names the
rule version that did it. That is the claims-to-underwriting loop showing up at
the level of a single case.

Deliberately NOT a signal: "no assessment recorded". Every open claim in this
book lacks one, because assessments are only written when a claim closes, so it
would fire on all 651 and discriminate nothing. Ageing is used instead.
"""
from __future__ import annotations

from typing import Any

from backend_v3.advisor.prioritization import TODAY
from backend_v3.structured_store.duckdb_client import get_connection

# Additive and transparent -- the total is a sum of stated reasons.
#
# Duration is graduated rather than a single flag. In a book this young almost
# every open claim falls inside the 24-month contestable window, so one flat
# signal fired on 92% of the queue and discriminated nothing. Splitting it into
# a sharp early band, a softer contestable band, and a separate straight-through
# overlay restores the ranking -- and makes the underwriting question explicit
# rather than buried inside a generic "early claim" label.
_WEIGHTS = {
    "unresolved_fraud": 32,
    "litigation": 26,
    "early_duration": 22,
    "long_open": 18,
    "stp_early_claim": 16,
    "large_reserve": 14,
    "contestable_period": 10,
    "catastrophe": 10,
}

CONTESTABLE_MONTHS = 24      # industry-standard contestability window
EARLY_DURATION_MONTHS = 12   # the sharper signal inside it
LONG_OPEN_DAYS = 180

HIGH_TIER = 70
MEDIUM_TIER = 40

# Signals that escalate on their own, whatever the total. A fraud indicator or
# an active litigation is a referral decision, not a scoring one -- letting a
# low total bury either of those would be wrong however tidy the arithmetic.
_ESCALATING_SIGNALS = ("unresolved_fraud", "litigation")

_OPEN_CLAIMS_SQL = """
with fraud as (
  select claim_id,
         count(*)              as open_indicators,
         max(indicator_score)  as top_score,
         string_agg(distinct indicator_type, ', ') as indicator_types
  from claim_fraud_indicators
  where resolved_flag = false
  group by claim_id
)
select
  c.claim_id, c.claim_number, c.claim_status, c.loss_date, c.report_date,
  c.loss_cause, c.paid_amount, c.reserve_amount,
  c.litigation_flag, c.catastrophe_flag, c.policy_duration_months,
  c.customer_id, pt.display_name as customer_name,
  p.policy_id, p.policy_number, pr.product_name, pr.line_of_business,
  ud.application_id, ud.rule_id_applied, ud.auto_decided, ud.risk_score,
  ud.decision_status, r.rule_key, r.version as rule_version,
  date_diff('day', c.report_date, ?) as days_open,
  coalesce(f.open_indicators, 0) as open_indicators,
  f.indicator_types
from claims c
left join fraud f              on f.claim_id = c.claim_id
left join policies p           on p.policy_id = c.policy_id
left join products pr          on pr.product_id = p.product_id
left join underwriting_decisions ud on ud.application_id = p.application_id
left join uw_rules r           on r.rule_id = ud.rule_id_applied
left join customers cu         on cu.customer_id = c.customer_id
left join parties pt           on pt.party_id = cu.party_id
where c.claim_status = 'open'
"""


def _reserve_threshold(con) -> float:
    """
    The 90th percentile reserve across open claims.

    A fixed currency threshold would be wrong the moment the book changes; the
    signal that matters is "large relative to what we normally reserve".
    """
    row = con.execute(
        "select quantile_cont(reserve_amount, 0.9) from claims where claim_status = 'open'"
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else float("inf")


def _score_row(row: dict[str, Any], reserve_p90: float) -> dict[str, Any]:
    reasons: list[dict[str, Any]] = []
    score = 0

    def add(signal: str, text: str) -> None:
        nonlocal score
        score += _WEIGHTS[signal]
        reasons.append({"signal": signal, "points": _WEIGHTS[signal], "text": text})

    if row["open_indicators"]:
        n = row["open_indicators"]
        types = row.get("indicator_types") or "unspecified"
        add(
            "unresolved_fraud",
            f"{n} unresolved fraud indicator{'s' if n != 1 else ''} on file ({types})",
        )

    if row["litigation_flag"]:
        add("litigation", "Claim is in litigation")

    dur = row.get("policy_duration_months")
    if dur is not None and dur <= CONTESTABLE_MONTHS:
        # Name the underwriting decision -- this is the loop, at case level.
        if row.get("rule_key"):
            how = "auto-approved" if row.get("auto_decided") else "underwriter-approved"
            provenance = (
                f"; policy {how} under {row['rule_key']} v{row['rule_version']}"
                + (f" at score {row['risk_score']:.2f}" if row.get("risk_score") is not None else "")
            )
        else:
            provenance = ""

        if dur <= EARLY_DURATION_MONTHS:
            add("early_duration", f"Loss at month {dur}, inside the first year{provenance}")
        else:
            add(
                "contestable_period",
                f"Loss at month {dur}, inside the {CONTESTABLE_MONTHS}m contestable window{provenance}",
            )

        # An early claim on a straight-through-approved policy is the specific
        # question the rules have to answer for: nobody looked at this risk.
        if dur <= EARLY_DURATION_MONTHS and row.get("auto_decided"):
            add(
                "stp_early_claim",
                "Early loss on a straight-through approval -- no underwriter reviewed this risk",
            )

    days_open = row.get("days_open")
    if days_open is not None and days_open >= LONG_OPEN_DAYS:
        add("long_open", f"Open {days_open} days without resolution")

    reserve = row.get("reserve_amount")
    if reserve is not None and reserve >= reserve_p90:
        add(
            "large_reserve",
            f"Reserve S${reserve:,.0f} is in the top 10% of open claims",
        )

    if row["catastrophe_flag"]:
        add("catastrophe", "Flagged as a catastrophe event")

    escalated = next(
        (r["signal"] for r in reasons if r["signal"] in _ESCALATING_SIGNALS), None
    )
    if escalated or score >= HIGH_TIER:
        tier = "high"
    elif score >= MEDIUM_TIER:
        tier = "medium"
    else:
        tier = "low"

    return {
        "claim_id": row["claim_id"],
        "claim_number": row["claim_number"],
        "customer_id": row["customer_id"],
        "customer_name": row["customer_name"],
        "policy_id": row["policy_id"],
        "policy_number": row["policy_number"],
        "product_name": row["product_name"],
        "line_of_business": row["line_of_business"],
        "loss_cause": row["loss_cause"],
        "loss_date": row["loss_date"].isoformat() if row["loss_date"] else None,
        "report_date": row["report_date"].isoformat() if row["report_date"] else None,
        "days_open": days_open,
        "policy_duration_months": dur,
        "paid_amount": row["paid_amount"],
        "reserve_amount": reserve,
        "litigation_flag": bool(row["litigation_flag"]),
        "catastrophe_flag": bool(row["catastrophe_flag"]),
        "open_fraud_indicators": row["open_indicators"],
        "underwriting": {
            "application_id": row.get("application_id"),
            "rule_key": row.get("rule_key"),
            "rule_version": row.get("rule_version"),
            "auto_decided": bool(row["auto_decided"]) if row.get("auto_decided") is not None else None,
            "risk_score": row.get("risk_score"),
            "decision_status": row.get("decision_status"),
        }
        if row.get("application_id")
        else None,
        "score": score,
        "tier": tier,
        "escalated_by": escalated,
        "reasons": reasons,
    }


def triage_open_claims(limit: int = 100) -> list[dict[str, Any]]:
    """
    Every open claim, scored and ordered by how much attention it needs.

    One query for the claims and one for the reserve percentile -- no per-claim
    round trips. The fraud counts come in as a pre-aggregated CTE rather than a
    correlated subquery, which at this table size is the difference between a
    hash join and a nested loop.
    """
    con = get_connection()
    try:
        reserve_p90 = _reserve_threshold(con)
        cur = con.execute(_OPEN_CLAIMS_SQL, [TODAY])
        columns = [d[0] for d in cur.description]
        rows = [dict(zip(columns, r)) for r in cur.fetchall()]
    finally:
        con.close()

    scored = [_score_row(r, reserve_p90) for r in rows]
    scored.sort(key=lambda c: (c["score"], c["days_open"] or 0), reverse=True)
    return scored[:limit]


def triage_summary() -> dict[str, Any]:
    """Counts for the queue header, derived from the same scoring pass."""
    scored = triage_open_claims(limit=10_000)
    by_tier = {"high": 0, "medium": 0, "low": 0}
    for c in scored:
        by_tier[c["tier"]] += 1

    signal_counts: dict[str, int] = {}
    for c in scored:
        for r in c["reasons"]:
            signal_counts[r["signal"]] = signal_counts.get(r["signal"], 0) + 1

    return {
        "open_claims": len(scored),
        "needs_attention": by_tier["high"] + by_tier["medium"],
        "by_tier": by_tier,
        "signal_counts": signal_counts,
        "total_reserve": round(sum(c["reserve_amount"] or 0 for c in scored), 2),
        "weights": _WEIGHTS,
    }


def get_triaged_claim(claim_id: str) -> dict[str, Any] | None:
    """One claim's triage view, scored identically to the queue."""
    con = get_connection()
    try:
        reserve_p90 = _reserve_threshold(con)
        cur = con.execute(
            _OPEN_CLAIMS_SQL.replace(
                "where c.claim_status = 'open'", "where c.claim_id = ?"
            ),
            [TODAY, claim_id],
        )
        columns = [d[0] for d in cur.description]
        row = cur.fetchone()
    finally:
        con.close()
    if not row:
        return None
    return _score_row(dict(zip(columns, row)), reserve_p90)

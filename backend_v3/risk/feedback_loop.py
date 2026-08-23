"""
Claims-to-underwriting feedback loop (C3).

The question this answers is the one a reinsurer actually asks: not "which
claims need attention" and not "which segments are diverging", but *is a rule
letting through risk it should not*. Claims triage shows it one case at a time;
this aggregates the cases back onto the rule version that accepted them.

METHOD -- WHY IT IS NOT A RAW PERCENTAGE
----------------------------------------
Comparing raw early-claim percentages across rule versions is invalid here, and
getting it wrong is easy. UW-AUTO-STP v2 took effect in October 2024, so its
policies have had at most ~22 months of exposure and *cannot yet* have produced
a late-duration claim. Measured naively, the tightened rule looks worse than
the loose one purely from censoring -- the first version of this analysis said
exactly that, with the sign inverted.

So: policies are only counted once they have carried a full early window of
exposure, and the measure is early claims per 1,000 such policies. That puts
both cohorts on the same footing.

WHAT THE SIGNAL IS
------------------
UW-AUTO-STP v1 auto-approved anything scoring below 0.55; v2 tightened that to
0.42. Applicants scoring in between were straight-through approved under v1 and
referred to a human under v2 -- the "leaked band". If the rule was leaking,
that band claims early at a materially higher rate than the rest of the
straight-through book.

The pattern is present in this synthetic data by construction. It demonstrates
that the loop detects a leak; it is not evidence about any real portfolio.
"""
from __future__ import annotations

from typing import Any

from backend_v3.advisor.prioritization import TODAY
from backend_v3.structured_store.duckdb_client import get_connection

EARLY_WINDOW_M = 12       # a claim inside this many months counts as early
MIN_EXPOSURE_M = 12       # a policy must have carried at least this to count
MATERIAL_LIFT = 1.3       # below this, a difference is not worth acting on

_COHORT_CTE = f"""
with cohort as (
  select
    ud.rule_id_applied,
    coalesce(r.rule_key || ' v' || cast(r.version as varchar), 'no rule') as rule_label,
    coalesce(ud.leaked_cohort, false) as leaked,
    ud.risk_score,
    date_diff('month', p.effective_date,
              least(coalesce(p.expiration_date, DATE '{TODAY.isoformat()}'),
                    DATE '{TODAY.isoformat()}')) as exposure_m,
    c.policy_duration_months as claim_dur
  from policies p
  join underwriting_decisions ud on ud.application_id = p.application_id
  left join uw_rules r on r.rule_id = ud.rule_id_applied
  left join claims c on c.policy_id = p.policy_id
  where ud.auto_decided = true
)
"""


def _rate_rows(group_expr: str, extra_where: str = "") -> list[tuple]:
    sql = f"""
    {_COHORT_CTE}
    select {group_expr} as cell,
           count(*) as policies,
           sum(case when claim_dur <= {EARLY_WINDOW_M} then 1 else 0 end) as early_claims,
           round(1000.0 * sum(case when claim_dur <= {EARLY_WINDOW_M} then 1 else 0 end)
                 / nullif(count(*), 0), 1) as per_1000
    from cohort
    where exposure_m >= {MIN_EXPOSURE_M} {extra_where}
    group by 1
    order by 1
    """
    con = get_connection()
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def method() -> dict[str, Any]:
    """The methodology, stated alongside every number that depends on it."""
    return {
        "measure": "early claims per 1,000 policies",
        "early_window_months": EARLY_WINDOW_M,
        "minimum_exposure_months": MIN_EXPOSURE_M,
        "material_lift": MATERIAL_LIFT,
        "why_exposure_matched": (
            "Rule versions took effect at different times, so their policies have had different "
            "amounts of time to produce a claim. Comparing raw early-claim percentages would make "
            "the newer, tighter rule look worse purely from censoring. Only policies that have "
            f"carried at least {MIN_EXPOSURE_M} months of exposure are counted."
        ),
        "caveat": (
            "The leakage pattern in this data is present by construction. It shows the loop "
            "detects a leak; it is not evidence about a real portfolio."
        ),
    }


def by_rule_version() -> list[dict[str, Any]]:
    return [
        {"rule": r[0], "policies": r[1], "early_claims": r[2], "per_1000": r[3]}
        for r in _rate_rows("rule_label")
    ]


def by_score_band() -> list[dict[str, Any]]:
    """
    Incidence by where the score sat relative to the two thresholds.

    The middle band is the one that changed treatment between versions, so it
    is the band the comparison actually turns on.
    """
    band = (
        "case when risk_score < 0.42 then 'below 0.42 (STP under both)' "
        "     when risk_score < 0.55 then '0.42-0.55 (STP under v1, referred under v2)' "
        "     else '0.55+ (referred under both)' end"
    )
    return [
        {"band": r[0], "policies": r[1], "early_claims": r[2], "per_1000": r[3]}
        for r in _rate_rows(band)
    ]


def leakage_finding() -> dict[str, Any]:
    """
    The headline: does the band that changed treatment claim early more often?
    """
    rows = _rate_rows("leaked")
    rates = {bool(r[0]): {"policies": r[1], "early_claims": r[2], "per_1000": r[3]} for r in rows}
    leaked = rates.get(True)
    rest = rates.get(False)

    if not leaked or not rest or not rest["per_1000"]:
        return {"detected": False, "reason": "not enough exposure-matched policies to compare"}

    lift = leaked["per_1000"] / rest["per_1000"]
    detected = lift >= MATERIAL_LIFT
    return {
        "detected": detected,
        "lift": round(lift, 2),
        "leaked_cohort": leaked,
        "comparison_cohort": rest,
        "headline": (
            f"Policies auto-approved under UW-AUTO-STP v1 that v2 would have referred claim "
            f"within {EARLY_WINDOW_M} months at {leaked['per_1000']} per 1,000, against "
            f"{rest['per_1000']} per 1,000 for the rest of the straight-through book "
            f"-- {lift:.2f}x."
            if detected
            else
            f"No material difference: {leaked['per_1000']} vs {rest['per_1000']} per 1,000 "
            f"({lift:.2f}x, below the {MATERIAL_LIFT}x threshold)."
        ),
        "implication": (
            "The tightening from 0.55 to 0.42 is supported by the claims that followed: the band "
            "it removed from straight-through processing is the band that went on to claim early."
            if detected else
            "The evidence does not support treating this band differently."
        ),
    }


def cases_behind_the_leak(limit: int = 25) -> list[dict[str, Any]]:
    """
    The individual claims driving the finding.

    An aggregate that cannot be opened is hard to trust; this is the drill-down
    to the actual policies, each of which links to its underwriting case.
    """
    sql = f"""
    select c.claim_id, c.claim_number, c.policy_duration_months,
           c.paid_amount + c.reserve_amount as incurred,
           c.loss_cause, c.claim_status,
           p.policy_number, pr.product_name,
           ud.application_id, ud.risk_score, ud.decision_status,
           pt.display_name as customer_name
    from claims c
    join policies p on p.policy_id = c.policy_id
    join underwriting_decisions ud on ud.application_id = p.application_id
    left join products pr on pr.product_id = p.product_id
    left join customers cu on cu.customer_id = c.customer_id
    left join parties pt on pt.party_id = cu.party_id
    where ud.leaked_cohort = true
      and c.policy_duration_months <= {EARLY_WINDOW_M}
    order by c.policy_duration_months, incurred desc
    limit ?
    """
    con = get_connection()
    try:
        cur = con.execute(sql, [limit])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()


def loop_report() -> dict[str, Any]:
    """Everything the loop screen needs, in one call."""
    return {
        "method": method(),
        "finding": leakage_finding(),
        "by_rule_version": by_rule_version(),
        "by_score_band": by_score_band(),
        "cases": cases_behind_the_leak(),
    }

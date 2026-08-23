"""
Actual-vs-expected experience monitoring (P1).

WHAT "EXPECTED" MEANS HERE -- READ THIS FIRST
---------------------------------------------
An A/E ratio is only as meaningful as the expected basis behind it, and this
system has no industry mortality or morbidity table. Rather than invent one and
present it as reasonable, expected is derived from the book's own aggregate
experience: the portfolio-wide incurred-to-earned ratio over the observation
window. A segment's A/E is its loss ratio divided by that baseline.

That is a real technique -- relative experience analysis against an internal
baseline -- and it answers the question this screen is actually for: which
segments are diverging from the rest of the book. Every response carries the
basis so a reader can see exactly what they are being compared against.

WHAT IT CANNOT TELL YOU
-----------------------
It measures relative divergence, not absolute rate adequacy. If the whole book
were underpriced by thirty percent, every segment would still read A/E = 1.00.
Answering adequacy needs a priced basis -- a real expected table from pricing
or a reinsurer's own experience study -- and that is the first thing to swap in
if this were pointed at a live portfolio. `basis()` says so in the payload
rather than leaving it implied.

CREDIBILITY
-----------
A segment with four claims will swing wildly and means nothing. Cells below
MIN_CLAIMS_TO_FLAG are reported but never flagged as diverging, and each cell
carries a credibility weight on the square-root rule (a simplified
limited-fluctuation approach, not full classical credibility).
"""
from __future__ import annotations

import math
from typing import Any

from backend_v3.structured_store.duckdb_client import get_connection

# Below this, a cell is shown but never flagged -- it cannot carry the weight.
MIN_CLAIMS_TO_FLAG = 30
# Claim count at which a cell is treated as fully credible.
FULL_CREDIBILITY_CLAIMS = 200
# How far A/E must sit from 1.00 before it is worth a reader's attention.
DIVERGENCE_THRESHOLD = 0.15

# `derivation` records whether a cut is emergent or circular.
#
# The synthetic data was calibrated by rescaling claim severity per line of
# business to a target loss ratio, so the line-of-business cut necessarily
# reproduces that input -- it is an assumption reflected back, not a finding.
# Every other cut falls out of the frequency model and was never tuned, so
# divergence there is genuinely emergent. Anyone reading these numbers is
# entitled to know which is which, and burying that in a docstring nobody
# opens would be the wrong place for it.
_DIMENSIONS = {
    "line_of_business": {
        "label": "Line of business",
        "derivation": "calibrated",
        "derivation_note": (
            "Claim severity was rescaled per line of business to a target loss ratio when the "
            "synthetic book was built, so this cut restates that assumption rather than "
            "discovering anything."
        ),
        "premium_expr": "pr.line_of_business",
        "claim_expr": "pr.line_of_business",
        "premium_join": "join products pr on pr.product_id = po.product_id",
        "claim_join": "join products pr on pr.product_id = po.product_id",
    },
    "duration_band": {
        "label": "Policy duration",
        "derivation": "emergent",
        "derivation_note": "Falls out of the claim frequency model; never tuned to a target.",
        # Duration is a property of each earned-premium month, not of the
        # policy: a policy contributes exposure to every band it has lived
        # through. Bucketing by the policy's current age would mis-assign it.
        "premium_expr": (
            "case when date_diff('month', po.effective_date, pm.premium_period_start) <= 12 then '0-12m' "
            "     when date_diff('month', po.effective_date, pm.premium_period_start) <= 24 then '13-24m' "
            "     else '25m+' end"
        ),
        "claim_expr": (
            "case when c.policy_duration_months <= 12 then '0-12m' "
            "     when c.policy_duration_months <= 24 then '13-24m' "
            "     else '25m+' end"
        ),
        "premium_join": "",
        "claim_join": "",
    },
    "channel": {
        "label": "Distribution channel",
        "derivation": "emergent",
        "derivation_note": "Falls out of the claim frequency model; never tuned to a target.",
        "premium_expr": "po.source_channel",
        "claim_expr": "po.source_channel",
        "premium_join": "",
        "claim_join": "",
    },
    "risk_class": {
        "label": "Underwriting risk class",
        "derivation": "emergent",
        "derivation_note": "Falls out of the claim frequency model; never tuned to a target.",
        "premium_expr": "ud.risk_class",
        "claim_expr": "ud.risk_class",
        "premium_join": "join underwriting_decisions ud on ud.application_id = po.application_id",
        "claim_join": "join underwriting_decisions ud on ud.application_id = po.application_id",
    },
    "rule_version": {
        "label": "Underwriting rule in force",
        "derivation": "emergent",
        "derivation_note": "Falls out of the claim frequency model; never tuned to a target.",
        "premium_expr": "coalesce(r.rule_key || ' v' || cast(r.version as varchar), 'no rule recorded')",
        "claim_expr": "coalesce(r.rule_key || ' v' || cast(r.version as varchar), 'no rule recorded')",
        "premium_join": (
            "join underwriting_decisions ud on ud.application_id = po.application_id "
            "left join uw_rules r on r.rule_id = ud.rule_id_applied"
        ),
        "claim_join": (
            "join underwriting_decisions ud on ud.application_id = po.application_id "
            "left join uw_rules r on r.rule_id = ud.rule_id_applied"
        ),
    },
}


def basis() -> dict[str, Any]:
    """
    The expected basis, stated explicitly so it can be argued with.

    Anyone reading an A/E number should be able to see in one place what the
    denominator is and where it came from.
    """
    con = get_connection()
    try:
        row = con.execute(
            """
            select
              (select sum(earned_premium_amount) from premiums)            as earned,
              (select sum(paid_amount + reserve_amount) from claims)       as incurred,
              (select count(*) from claims)                                as claims,
              (select min(premium_period_start) from premiums)             as window_from,
              (select max(premium_period_end) from premiums)               as window_to
            """
        ).fetchone()
    finally:
        con.close()

    earned, incurred, claims, w_from, w_to = row
    return {
        "method": "portfolio_baseline",
        "description": (
            "Expected is this book's own portfolio-wide incurred-to-earned ratio over the "
            "observation window. It is not an industry mortality or morbidity table."
        ),
        "limitation": (
            "This measures relative divergence between segments, not absolute rate adequacy. "
            "A uniformly underpriced book would still read A/E = 1.00 everywhere."
        ),
        "baseline_loss_ratio": round(incurred / earned, 4) if earned else None,
        "earned_premium": round(earned or 0, 2),
        "incurred_claims": round(incurred or 0, 2),
        "claim_count": claims,
        "window_from": w_from.isoformat() if w_from else None,
        "window_to": w_to.isoformat() if w_to else None,
        "min_claims_to_flag": MIN_CLAIMS_TO_FLAG,
        "divergence_threshold": DIVERGENCE_THRESHOLD,
    }


def _credibility(claims: int) -> float:
    """Square-root rule, capped at 1.0. A simplification, and labelled as one."""
    if claims <= 0:
        return 0.0
    return round(min(1.0, math.sqrt(claims / FULL_CREDIBILITY_CLAIMS)), 3)


def experience_by(dimension: str) -> dict[str, Any]:
    """Loss ratio and A/E for every cell of one dimension."""
    if dimension not in _DIMENSIONS:
        raise ValueError(f"unknown dimension {dimension!r}; expected one of {sorted(_DIMENSIONS)}")
    d = _DIMENSIONS[dimension]

    sql = f"""
    with earned as (
      select {d['premium_expr']} as cell, sum(pm.earned_premium_amount) as earned
      from premiums pm
      join policies po on po.policy_id = pm.policy_id
      {d['premium_join']}
      group by 1
    ), incurred as (
      select {d['claim_expr']} as cell,
             sum(c.paid_amount + c.reserve_amount) as incurred,
             count(*) as claims
      from claims c
      join policies po on po.policy_id = c.policy_id
      {d['claim_join']}
      group by 1
    )
    select e.cell, e.earned, coalesce(i.incurred, 0), coalesce(i.claims, 0)
    from earned e left join incurred i on i.cell is not distinct from e.cell
    where e.earned > 0
    order by e.earned desc
    """

    con = get_connection()
    try:
        rows = con.execute(sql).fetchall()
    finally:
        con.close()

    b = basis()
    baseline = b["baseline_loss_ratio"] or 0

    cells = []
    for cell, earned, incurred, claims in rows:
        lr = (incurred / earned) if earned else 0
        ae = (lr / baseline) if baseline else None
        credible = claims >= MIN_CLAIMS_TO_FLAG
        diverging = bool(credible and ae is not None and abs(ae - 1.0) >= DIVERGENCE_THRESHOLD)
        cells.append({
            "cell": cell if cell is not None else "unclassified",
            "earned_premium": round(earned, 2),
            "incurred_claims": round(incurred, 2),
            "claim_count": claims,
            "loss_ratio": round(lr, 4),
            "actual_vs_expected": round(ae, 3) if ae is not None else None,
            "credibility": _credibility(claims),
            "credible": credible,
            "diverging": diverging,
            "direction": None if not diverging else ("adverse" if ae > 1 else "favourable"),
        })

    return {
        "dimension": dimension,
        "label": d["label"],
        "derivation": d["derivation"],
        "derivation_note": d["derivation_note"],
        "basis": b,
        "cells": cells,
    }


def experience_overview() -> dict[str, Any]:
    """Every dimension at once, plus whatever is diverging across all of them."""
    dimensions = [experience_by(name) for name in _DIMENSIONS]
    flagged = [
        {**c, "dimension": d["dimension"], "dimension_label": d["label"]}
        for d in dimensions
        for c in d["cells"]
        if c["diverging"]
    ]
    flagged.sort(key=lambda c: abs((c["actual_vs_expected"] or 1) - 1), reverse=True)
    return {
        "basis": basis(),
        "dimensions": dimensions,
        "diverging": flagged,
    }

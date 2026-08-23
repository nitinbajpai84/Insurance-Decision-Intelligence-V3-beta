"""
Rebuild the underwriting -> policy -> claim spine.

WHY THIS EXISTS
---------------
The inherited seed data had three breaks that made the risk chain unusable:

  1. `underwriting_decisions` was orphaned. Its application_id/customer_id were
     UUIDs from an older generator, while `applications`/`customers` use the
     app_00000 / cust_00000 scheme. The join returned zero rows.
  2. `applications` had no path to `policies` (policies.opportunity_id is NULL
     for every row), so an accepted risk could not be traced to the policy it
     became.
  3. Claim timing was not a duration curve. Losses fell between month -7 and
     +2 relative to policy effective date -- some *before* the policy existed --
     so "early-duration claim" carried no signal at all.

This script rebuilds the spine so that every policy traces back to the
application and underwriting decision that accepted it, and every claim sits at
a plausible policy duration.

THE SEEDED PATTERN -- READ THIS BEFORE DEMOING
----------------------------------------------
A rule-leakage pattern is deliberately planted so the claims-to-underwriting
feedback loop has something real to find:

  UW-AUTO-STP v1 (2023-07-01 .. 2024-09-30) auto-approved anything scoring
  below 0.55. v2 (2024-10-01 onward) tightened that to 0.42.

Applicants scoring in the 0.42-0.55 band were therefore straight-through
approved under v1 and referred to a human under v2. Because the score is a
noisy read of a latent true risk that also drives claim incidence, the v1
cohort goes on to claim early at a materially higher rate.

That is a genuine, discoverable signal -- but it is synthetic BY CONSTRUCTION.
It demonstrates that the loop works. It is not evidence about any real book,
and must never be presented as one.

Usage:
    venv\\Scripts\\python.exe database/seed_risk_chain.py          # rebuild
    venv\\Scripts\\python.exe database/seed_risk_chain.py --verify # checks only

Deterministic: seeded RNG, so repeated runs reproduce the same spine.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = str(SCRIPT_DIR / "insurance_v3.duckdb")

SEED = 42
TODAY = date(2026, 8, 23)

# Rule thresholds. The v1 -> v2 tightening is the planted leak.
STP_MAX_V1 = 0.55
STP_MAX_V2 = 0.42
REFER_MAX = 0.75  # above this, decline
V2_EFFECTIVE = date(2024, 10, 1)
V1_EFFECTIVE = date(2023, 7, 1)

# Share of the book that never became a policy (declined/postponed/withdrawn).
NON_ISSUED_RATIO = 0.20

# Annual premium bands by line of business, for applications that never issued
# and so have no policy to inherit a premium from.
PREMIUM_BAND = {
    "Health": (600, 3500),
    "Savings": (2400, 18000),
    "Protection": (400, 2600),
    "Investment": (3600, 30000),
}

rng = random.Random(SEED)


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

DDL = [
    """
    CREATE TABLE IF NOT EXISTS uw_rules (
      rule_id        VARCHAR PRIMARY KEY,
      rule_key       VARCHAR NOT NULL,
      version        INTEGER NOT NULL,
      name           VARCHAR,
      description    VARCHAR,
      condition_json JSON,
      action         VARCHAR,
      effective_from DATE,
      effective_to   DATE,
      status         VARCHAR,
      created_by     VARCHAR,
      created_at     TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS uw_decision_log (
      log_id          VARCHAR PRIMARY KEY,
      application_id  VARCHAR,
      event_seq       INTEGER,
      event_type      VARCHAR,
      decided_at      TIMESTAMP,
      decision        VARCHAR,
      risk_score      DOUBLE,
      rules_fired     JSON,
      actor           VARCHAR,
      actor_type      VARCHAR,
      is_override     BOOLEAN,
      override_reason VARCHAR,
      created_at      TIMESTAMP
    )
    """,
]

# Columns added to existing tables. Additive only -- nothing is dropped.
ALTERS = [
    ("policies", "application_id", "VARCHAR"),
    ("underwriting_decisions", "risk_score", "DOUBLE"),
    ("underwriting_decisions", "rule_id_applied", "VARCHAR"),
    ("underwriting_decisions", "auto_decided", "BOOLEAN"),
    ("underwriting_decisions", "leaked_cohort", "BOOLEAN"),
    ("claims", "policy_duration_months", "INTEGER"),
]


def ensure_schema(con) -> None:
    for stmt in DDL:
        con.execute(stmt)
    for table, col, coltype in ALTERS:
        existing = {
            r[0]
            for r in con.execute(
                "select column_name from information_schema.columns where table_name = ?",
                [table],
            ).fetchall()
        }
        if col not in existing:
            con.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {coltype}')
            print(f"  + {table}.{col}")


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------

def build_rules() -> list[tuple]:
    now = datetime.now()
    mk = lambda rid, key, ver, name, desc, cond, act, frm, to, status: (
        rid, key, ver, name, desc, json.dumps(cond), act, frm, to, status, "uw_governance", now
    )
    return [
        mk(
            "rule_stp_v1", "UW-AUTO-STP", 1,
            "Straight-through approval band",
            "Auto-approve applications scoring below 0.55 without underwriter review.",
            {"field": "risk_score", "op": "<", "value": STP_MAX_V1},
            "auto_approve", V1_EFFECTIVE, V2_EFFECTIVE - timedelta(days=1), "superseded",
        ),
        mk(
            "rule_stp_v2", "UW-AUTO-STP", 2,
            "Straight-through approval band (tightened)",
            "Auto-approve threshold tightened to 0.42 after early-duration claim review.",
            {"field": "risk_score", "op": "<", "value": STP_MAX_V2},
            "auto_approve", V2_EFFECTIVE, None, "active",
        ),
        mk(
            "rule_refer_v1", "UW-REFER", 1,
            "Manual referral band",
            "Refer to an underwriter when the score sits between the STP threshold and 0.75.",
            {"field": "risk_score", "op": "between", "upper": REFER_MAX},
            "refer", V1_EFFECTIVE, None, "active",
        ),
        mk(
            "rule_decline_v1", "UW-DECLINE", 1,
            "Decline threshold",
            "Decline applications scoring above 0.75.",
            {"field": "risk_score", "op": ">=", "value": REFER_MAX},
            "decline", V1_EFFECTIVE, None, "active",
        ),
    ]


def stp_threshold_on(d: date) -> tuple[float, str]:
    """The auto-approve threshold in force on a given date, and the rule id."""
    if d < V2_EFFECTIVE:
        return STP_MAX_V1, "rule_stp_v1"
    return STP_MAX_V2, "rule_stp_v2"


# --------------------------------------------------------------------------
# risk model
# --------------------------------------------------------------------------

def draw_true_risk() -> float:
    """Latent risk in [0,1], skewed low -- most applicants are standard."""
    return min(1.0, max(0.0, rng.betavariate(2.2, 4.0)))


def observed_score(true_risk: float) -> float:
    """What underwriting sees: the latent risk plus assessment noise."""
    return min(0.999, max(0.001, true_risk + rng.gauss(0, 0.09)))


def decide(risk_score: float, app_date: date) -> tuple[str, str, bool, bool]:
    """
    Returns (decision_status, rule_id_applied, auto_decided, leaked).

    `leaked` marks a case auto-approved under the loose v1 threshold that the
    current v2 threshold would have sent to a human instead.
    """
    stp_max, stp_rule = stp_threshold_on(app_date)
    if risk_score >= REFER_MAX:
        return "declined", "rule_decline_v1", True, False
    if risk_score < stp_max:
        leaked = risk_score >= STP_MAX_V2 and stp_rule == "rule_stp_v1"
        return "approved_standard", stp_rule, True, leaked
    # referral band -- an underwriter decides
    roll = rng.random()
    if roll < 0.55:
        return "approved_rated", "rule_refer_v1", False, False
    if roll < 0.72:
        return "approved_exclusion", "rule_refer_v1", False, False
    if roll < 0.88:
        return "declined", "rule_refer_v1", False, False
    return "postponed", "rule_refer_v1", False, False


def risk_class_for(true_risk: float) -> str:
    if true_risk < 0.25:
        return "low"
    if true_risk < 0.50:
        return "medium"
    if true_risk < 0.72:
        return "high"
    return "very_high"


# --------------------------------------------------------------------------
# claim timing
# --------------------------------------------------------------------------

EARLY_WINDOW_M = 12  # "early duration" = a claim inside the first 12 months


def claim_propensity(true_risk: float, lob: str, leaked: bool, exposure_months: int) -> float:
    """
    Relative weight for selecting which policies go on to claim.

    Exposure is a factor because incidence scales with time at risk. Without it
    the sample over-represents recently-written policies, which then makes every
    rule version written recently look like it produces early claims.
    """
    base = {"Health": 3.2, "Protection": 1.0, "Investment": 0.35, "Savings": 0.4}.get(lob, 0.8)
    w = base * (0.45 + 2.6 * true_risk) * (exposure_months / 12.0)
    if leaked:
        w *= 2.4
    return w


def draw_duration_months(lob: str, exposure_months: int, leaked: bool) -> int:
    """
    Months from policy effective date to loss date.

    Health claims recur through the policy year after a short waiting period.
    Life-type covers show few early claims -- which is exactly why an early
    cluster is worth investigating.

    A policy exposed for less than the early window can only ever produce an
    early claim. That is censoring, not signal, and the measurement side has to
    exclude those policies rather than this function pretending otherwise.
    """
    if exposure_months <= 1:
        return 1

    if lob == "Health":
        return max(1, min(exposure_months, int(rng.uniform(1, exposure_months + 1))))

    # Life-type: hazard rises with duration, so early claims are the exception.
    early_chance = 0.30 if leaked else 0.08
    if rng.random() < early_chance:
        return rng.randint(1, min(EARLY_WINDOW_M, exposure_months))
    if exposure_months <= EARLY_WINDOW_M:
        return rng.randint(1, exposure_months)
    return rng.randint(EARLY_WINDOW_M + 1, exposure_months)


# --------------------------------------------------------------------------
# main rebuild
# --------------------------------------------------------------------------

def rebuild(con) -> None:
    print("[schema] ensuring risk-chain tables")
    ensure_schema(con)

    print("[rules] loading versioned rule store")
    con.execute("DELETE FROM uw_rules")
    con.executemany(
        "INSERT INTO uw_rules VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", build_rules()
    )

    print("[load] reading policies and products")
    lob_by_product = {
        r[0]: r[1] for r in con.execute("select product_id, line_of_business from products").fetchall()
    }
    policies = con.execute(
        """
        select policy_id, customer_id, agent_id, product_id,
               effective_date, expiration_date, annual_premium
        from policies
        order by policy_id
        """
    ).fetchall()
    print(f"       {len(policies):,} policies")

    now = datetime.now()
    applications: list[tuple] = []
    decisions: list[tuple] = []
    log_rows: list[tuple] = []
    policy_app: list[tuple] = []          # (application_id, policy_id)
    policy_meta: dict[str, dict] = {}     # policy_id -> risk facts, for claim timing

    def log(app_id, seq, etype, when, decision, score, rules, actor, actor_type,
            is_override=False, reason=None):
        log_rows.append((
            f"log_{len(log_rows):06d}", app_id, seq, etype, when, decision, score,
            json.dumps(rules), actor, actor_type, is_override, reason, now,
        ))

    # ---- issued business: one application + decision per policy ----
    print("[gen] applications and underwriting decisions for issued policies")
    for i, (pol_id, cust_id, agent_id, prod_id, eff, exp, ann_prem) in enumerate(policies):
        app_id = f"uwapp_{i:06d}"
        app_date = eff - timedelta(days=rng.randint(10, 45))
        decision_date = app_date + timedelta(days=rng.randint(1, 9))

        true_risk = draw_true_risk()
        score = observed_score(true_risk)
        status, rule_id, auto, leaked = decide(score, app_date)

        # An issued policy implies acceptance -- resample until the rules accept.
        guard = 0
        while status in ("declined", "postponed") and guard < 40:
            true_risk = draw_true_risk()
            score = observed_score(true_risk)
            status, rule_id, auto, leaked = decide(score, app_date)
            guard += 1
        if status in ("declined", "postponed"):
            status, rule_id, auto, leaked = "approved_rated", "rule_refer_v1", False, False

        lob = lob_by_product.get(prod_id, "Protection")
        rating = 1.0 if status == "approved_standard" else round(rng.uniform(1.25, 2.4), 2)

        applications.append((
            app_id, f"UWAPP-{i:06d}", None, None, None, cust_id, agent_id, prod_id,
            app_date, "issued", ann_prem, ann_prem * rng.uniform(8, 25),
            score >= 0.35, json.dumps({"channel": "spine_rebuild"}), now, now,
        ))
        decisions.append((
            f"uwdec_{i:06d}", app_id, cust_id, prod_id, decision_date, status,
            risk_class_for(true_risk), rating, status == "approved_exclusion",
            f"Score {score:.2f} against {rule_id}", json.dumps({"true_risk": round(true_risk, 4)}),
            now, now, round(score, 4), rule_id, auto, leaked,
        ))
        policy_app.append((app_id, pol_id))
        policy_meta[pol_id] = {
            "true_risk": true_risk, "leaked": leaked, "lob": lob,
            "eff": eff, "exp": exp, "cust": cust_id,
        }

        seq_when = datetime.combine(decision_date, datetime.min.time())
        log(app_id, 1, "scored", seq_when, None, round(score, 4), [rule_id], "risk_engine", "system")
        if auto:
            log(app_id, 2, "auto_approved", seq_when, status, round(score, 4), [rule_id], "risk_engine", "system")
        else:
            log(app_id, 2, "referred", seq_when, "refer", round(score, 4), ["rule_refer_v1"], "risk_engine", "system")
            log(app_id, 3, "underwriter_decision",
                seq_when + timedelta(days=rng.randint(1, 5)), status, round(score, 4),
                ["rule_refer_v1"], f"uw_{rng.randint(1, 12):02d}", "underwriter")

    # ---- non-issued business: declines, postponements, withdrawals ----
    n_non_issued = int(len(policies) * NON_ISSUED_RATIO)
    print(f"[gen] {n_non_issued:,} non-issued applications (declined / postponed)")
    customers = [r[0] for r in con.execute("select customer_id from customers").fetchall()]
    product_ids = list(lob_by_product.keys())
    base = len(policies)

    for j in range(n_non_issued):
        i = base + j
        app_id = f"uwapp_{i:06d}"
        app_date = TODAY - timedelta(days=rng.randint(30, 1100))
        decision_date = app_date + timedelta(days=rng.randint(1, 12))

        # Skew this population riskier -- that is why it did not issue.
        true_risk = min(1.0, draw_true_risk() + rng.uniform(0.10, 0.38))
        score = observed_score(true_risk)
        status, rule_id, auto, leaked = decide(score, app_date)
        if status.startswith("approved"):
            status, rule_id, auto = "withdrawn", "rule_refer_v1", False

        cust_id = rng.choice(customers)
        prod_id = rng.choice(product_ids)

        # A declined application still asked for a specific amount -- you request
        # cover, then get refused. Leaving these null made the queue look like
        # the applicant had not said what they wanted.
        lob = lob_by_product.get(prod_id, "Protection")
        lo, hi = PREMIUM_BAND.get(lob, (600, 4000))
        req_premium = round(rng.uniform(lo, hi), 2)
        req_sum_assured = round(req_premium * rng.uniform(8, 25), 2)

        applications.append((
            app_id, f"UWAPP-{i:06d}", None, None, None, cust_id, None, prod_id,
            app_date, status, req_premium, req_sum_assured, score >= 0.35,
            json.dumps({"channel": "spine_rebuild"}), now, now,
        ))
        decisions.append((
            f"uwdec_{i:06d}", app_id, cust_id, prod_id, decision_date, status,
            risk_class_for(true_risk), 1.0, False,
            f"Score {score:.2f} against {rule_id}", json.dumps({"true_risk": round(true_risk, 4)}),
            now, now, round(score, 4), rule_id, auto, False,
        ))
        seq_when = datetime.combine(decision_date, datetime.min.time())
        log(app_id, 1, "scored", seq_when, None, round(score, 4), [rule_id], "risk_engine", "system")
        log(app_id, 2, "underwriter_decision", seq_when, status, round(score, 4),
            [rule_id], f"uw_{rng.randint(1, 12):02d}", "underwriter")

    print(f"[write] {len(applications):,} applications, {len(decisions):,} decisions, {len(log_rows):,} log events")
    con.execute("DELETE FROM applications")
    con.executemany("INSERT INTO applications VALUES (" + ",".join(["?"] * 16) + ")", applications)
    con.execute("DELETE FROM underwriting_decisions")
    con.executemany("INSERT INTO underwriting_decisions VALUES (" + ",".join(["?"] * 17) + ")", decisions)
    con.execute("DELETE FROM uw_decision_log")
    con.executemany("INSERT INTO uw_decision_log VALUES (" + ",".join(["?"] * 13) + ")", log_rows)

    print("[link] attaching policies to their applications")
    con.execute("CREATE OR REPLACE TEMP TABLE _pa (application_id VARCHAR, policy_id VARCHAR)")
    con.executemany("INSERT INTO _pa VALUES (?,?)", policy_app)
    con.execute(
        "UPDATE policies SET application_id = _pa.application_id FROM _pa WHERE policies.policy_id = _pa.policy_id"
    )

    retime_claims(con)
    print("[done] spine rebuilt")


def retime_claims(con) -> None:
    """
    Re-assign claims to policies and re-time them onto duration curves.

    Reads every fact it needs back out of the database rather than from the
    generation loop's memory, so this step can be re-run on its own against an
    already-built underwriting spine (--claims-only).
    """
    print("[claims] re-assigning claims to policies and re-timing onto duration curves")

    rows = con.execute(
        """
        select p.policy_id, p.customer_id, p.effective_date, p.expiration_date,
               pr.line_of_business,
               coalesce(ud.leaked_cohort, false) as leaked,
               cast(json_extract(ud.decision_payload, '$.true_risk') as double) as true_risk
        from policies p
        join products pr on pr.product_id = p.product_id
        join underwriting_decisions ud on ud.application_id = p.application_id
        """
    ).fetchall()
    print(f"         {len(rows):,} policies with an underwriting decision")

    policy_meta: dict[str, dict] = {}
    weighted: list[tuple[str, float]] = []
    for pol_id, cust, eff, exp, lob, leaked, true_risk in rows:
        if true_risk is None:
            continue
        end = min(exp or TODAY, TODAY)
        if months_between(eff, end) < 1:
            continue
        exposure = months_between(eff, end)
        policy_meta[pol_id] = {
            "cust": cust, "eff": eff, "exp": exp, "lob": lob,
            "leaked": bool(leaked), "true_risk": float(true_risk),
        }
        weighted.append(
            (pol_id, claim_propensity(float(true_risk), lob, bool(leaked), exposure))
        )

    claim_ids = [r[0] for r in con.execute("select claim_id from claims order by claim_id").fetchall()]
    chosen = weighted_sample_without_replacement(weighted, len(claim_ids))
    print(f"         {len(chosen):,} claiming policies selected from {len(weighted):,} eligible")

    updates = []
    for claim_id, pol_id in zip(claim_ids, chosen):
        m = policy_meta[pol_id]
        exposure = max(1, months_between(m["eff"], min(m["exp"] or TODAY, TODAY)))
        dur = draw_duration_months(m["lob"], exposure, m["leaked"])
        loss = add_months(m["eff"], dur)
        if loss > TODAY:
            loss = TODAY - timedelta(days=rng.randint(1, 45))
            dur = max(1, months_between(m["eff"], loss))
        report = min(loss + timedelta(days=rng.randint(2, 28)), TODAY)
        updates.append((pol_id, m["cust"], loss, report, dur, claim_id))

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _cu (
          policy_id VARCHAR, customer_id VARCHAR, loss_date DATE,
          report_date DATE, dur INTEGER, claim_id VARCHAR
        )
        """
    )
    con.executemany("INSERT INTO _cu VALUES (?,?,?,?,?,?)", updates)
    con.execute(
        """
        UPDATE claims SET
          policy_id = _cu.policy_id,
          customer_id = _cu.customer_id,
          loss_date = _cu.loss_date,
          report_date = _cu.report_date,
          policy_duration_months = _cu.dur,
          close_date = CASE WHEN claims.close_date IS NULL THEN NULL
                            ELSE _cu.report_date + INTERVAL 30 DAY END
        FROM _cu WHERE claims.claim_id = _cu.claim_id
        """
    )

    # policy_coverage_id still points at the claim's previous policy. Repoint it
    # via a hash join against one coverage per policy -- a correlated subquery
    # here degrades to a nested loop over 36k coverage rows and never finishes.
    print("[claims] repointing coverage references")
    con.execute(
        """
        UPDATE claims SET policy_coverage_id = cov.policy_coverage_id
        FROM (
          select policy_id, min(policy_coverage_id) as policy_coverage_id
          from policy_coverage group by policy_id
        ) cov
        WHERE cov.policy_id = claims.policy_id
        """
    )
    con.commit()


def seed_pending_queue(con, n: int = 120) -> None:
    """
    Leave a slice of referred cases genuinely undecided.

    Without this every application already has an outcome and the underwriting
    queue is a historical report rather than a work list. These are cases the
    rules referred and no underwriter has picked up yet: the copilot's actual
    job. Their `underwriter_decision` events are removed so the trail matches
    the state -- a case cannot be pending and already decided.
    """
    print(f"[pending] moving {n} referred cases back to awaiting review")
    ids = [
        r[0]
        for r in con.execute(
            """
            select application_id from underwriting_decisions
            where auto_decided = false and decision_status <> 'pending_review'
            order by decision_date desc limit ?
            """,
            [n],
        ).fetchall()
    ]
    if not ids:
        print("         none available")
        return

    placeholders = ",".join(["?"] * len(ids))
    con.execute(
        f"update underwriting_decisions set decision_status = 'pending_review' "
        f"where application_id in ({placeholders})",
        ids,
    )
    con.execute(
        f"update applications set application_status = 'pending_review' "
        f"where application_id in ({placeholders})",
        ids,
    )
    con.execute(
        f"delete from uw_decision_log where event_type = 'underwriter_decision' "
        f"and application_id in ({placeholders})",
        ids,
    )
    con.commit()
    print(f"         {len(ids)} cases awaiting an underwriter")


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def add_months(d: date, months: int) -> date:
    y, m = divmod((d.year * 12 + d.month - 1) + months, 12)
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m])
    return date(y, m + 1, day)


def weighted_sample_without_replacement(weighted: list[tuple[str, float]], k: int) -> list[str]:
    """Efraimidis-Spirakis: one exponential key per item, take the k smallest."""
    keyed = []
    for item, w in weighted:
        if w <= 0:
            continue
        keyed.append((rng.expovariate(1.0) / w, item))
    keyed.sort(key=lambda t: t[0])
    return [item for _, item in keyed[:k]]


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

def verify(con) -> bool:
    print("\n=== verification ===")
    ok = True

    def check(label, got, want, comparator="=="):
        nonlocal ok
        passed = got == want if comparator == "==" else (got >= want)
        ok = ok and passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}: {got}")

    joined = con.execute("""
        select count(*) from underwriting_decisions ud
        join applications a on a.application_id = ud.application_id
    """).fetchone()[0]
    total_dec = con.execute("select count(*) from underwriting_decisions").fetchone()[0]
    check("UW decisions joined to applications", joined, total_dec)

    pol_linked = con.execute("select count(*) from policies where application_id is not null").fetchone()[0]
    pol_total = con.execute("select count(*) from policies").fetchone()[0]
    check("policies linked to an application", pol_linked, pol_total)

    chain = con.execute("""
        select count(*) from claims c
        join policies p on p.policy_id = c.policy_id
        join applications a on a.application_id = p.application_id
        join underwriting_decisions ud on ud.application_id = a.application_id
    """).fetchone()[0]
    claims_total = con.execute("select count(*) from claims").fetchone()[0]
    check("claims traceable to a UW decision", chain, claims_total)

    neg = con.execute("""
        select count(*) from claims c join policies p on p.policy_id = c.policy_id
        where c.loss_date < p.effective_date
    """).fetchone()[0]
    check("claims dated before their policy started", neg, 0)

    # Exposure-matched incidence. Comparing raw early-claim percentages across
    # rule versions is invalid here: v2 took effect Oct-2024, so v2 policies
    # cannot yet have produced a late claim and would look worse purely from
    # censoring. Restricting to policies with at least a full early window of
    # exposure puts both cohorts on the same footing.
    cohort_sql = """
      with cohort as (
        select ud.rule_id_applied,
               coalesce(ud.leaked_cohort, false) as leaked,
               date_diff('month', p.effective_date,
                         least(coalesce(p.expiration_date, DATE '2026-08-23'), DATE '2026-08-23')) as exposure_m,
               c.policy_duration_months as claim_dur
        from policies p
        join underwriting_decisions ud on ud.application_id = p.application_id
        left join claims c on c.policy_id = p.policy_id
        where ud.auto_decided = true
      )
      select {group_col},
             count(*) as policies,
             sum(case when claim_dur <= 12 then 1 else 0 end) as early_claims,
             round(1000.0 * sum(case when claim_dur <= 12 then 1 else 0 end) / count(*), 1) as per_1000
      from cohort
      where exposure_m >= 12
      group by 1 order by 1
    """

    print("\n  early-duration claims per 1,000 policies (>=12 months exposure, 12-month window):")
    print("  by rule version in force at decision:")
    for r in con.execute(cohort_sql.format(group_col="rule_id_applied")).fetchall():
        print(f"    {r[0]:<16} {r[1]:>6,} policies   {r[2]:>4} early   {r[3]:>6} per 1,000")

    print("\n  by leaked cohort (auto-approved under v1, would refer under v2):")
    leak_rates = {}
    for r in con.execute(cohort_sql.format(group_col="leaked")).fetchall():
        leak_rates[bool(r[0])] = r[3]
        print(f"    leaked={str(bool(r[0])):<6} {r[1]:>6,} policies   {r[2]:>4} early   {r[3]:>6} per 1,000")

    if True in leak_rates and False in leak_rates:
        lift = leak_rates[True] / leak_rates[False] if leak_rates[False] else 0
        passed = lift > 1.3
        ok = ok and passed
        print(f"\n  [{'PASS' if passed else 'FAIL'}] leaked cohort lift: {lift:.2f}x "
              f"(expect >1.3x -- the planted signal must actually be detectable)")

    print(f"\n  rules in store: {con.execute('select count(*) from uw_rules').fetchone()[0]}")
    print(f"  decision log events: {con.execute('select count(*) from uw_decision_log').fetchone()[0]:,}")
    print(f"\n=== {'ALL CHECKS PASSED' if ok else 'CHECKS FAILED'} ===")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="run checks only, no rebuild")
    ap.add_argument(
        "--claims-only", action="store_true",
        help="re-time claims against an already-built underwriting spine",
    )
    ap.add_argument(
        "--pending-only", action="store_true",
        help="refresh the awaiting-review queue without rebuilding anything else",
    )
    args = ap.parse_args()

    con = duckdb.connect(DB_PATH, read_only=False)
    try:
        if args.pending_only:
            seed_pending_queue(con)
        elif args.claims_only:
            retime_claims(con)
        elif not args.verify:
            rebuild(con)
            seed_pending_queue(con)
        return 0 if verify(con) else 1
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())

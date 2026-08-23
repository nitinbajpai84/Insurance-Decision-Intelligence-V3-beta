"""
Enrich the context graph so more than one customer has a story worth showing.

WHY
---
Auditing the graph turned up an uneven picture:

  * The ten cust_* customers each carry 14-19 knowledge-graph edges. John Kemp
    only *looked* uniquely rich because he had 75 conversations against
    everyone else's zero or one -- his other dimensions matched theirs.
  * The ten csv_adv_* customers, imported from CRM, had zero knowledge-graph
    edges. Several of them (Marcus Tan, Priya Raman, Grace Lim, Samuel Wee)
    sit at the top of My Day's meeting list, so an advisor clicks straight
    into an empty graph.
  * Four Claim nodes existed as bare stubs carrying only a claim_id, because
    graph_sync only enriches claims whose policy is in the advisor's book.
    They are not junk -- each has an ingested Document attached -- so they are
    filled in from DuckDB rather than deleted.

WHAT THIS DOES NOT DO
---------------------
It does not invent policies for the csv_adv_* customers. They have no row in
the policy administration store, and a Policy node with no premium, no
coverage and no claims behind it is exactly the hollow node this exercise is
meant to remove. A CRM-imported contact whose policies have not yet been
matched is the honest model, and the product already tells that story through
onboarding and the import flow.

Every node written here carries its full property set. Nothing is created with
placeholder or missing fields.

Idempotent: MERGE on stable keys, so re-running updates in place.

Usage:
    venv\\Scripts\\python.exe database/seed_graph_enrichment.py
    venv\\Scripts\\python.exe database/seed_graph_enrichment.py --verify
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.graph_store.neo4j_client import run_query, run_write
from backend_v3.structured_store.duckdb_client import get_connection

SOURCE_NOTES = "advisor_notes"
SOURCE_CONVO = "conversation_notes"

# --------------------------------------------------------------------------
# CRM-imported customers: a coherent story each, not scattered facts
# --------------------------------------------------------------------------

CRM_CUSTOMERS: dict[str, dict] = {
    "csv_adv_1001": {  # Marcus Tan -- portfolio review on the calendar
        "family": [
            {"name": "Serene Tan", "relationship": "spouse"},
            {"name": "Ethan Tan", "relationship": "son"},
        ],
        "life_events": [
            {"description": "Promoted to regional director", "date": "2026-02-11", "category": "career"},
            {"description": "Bought a resale flat in Bishan", "date": "2025-09-04", "category": "property"},
        ],
        "goals": [
            {"description": "Retire at 60 with S$8,000 monthly income", "category": "retirement"},
            {"description": "Fund Ethan's university education overseas", "category": "education"},
        ],
        "needs": [
            {"description": "Mortgage protection following the Bishan flat purchase", "category": "Protection"},
        ],
        "concerns": ["Retirement income adequacy", "Mortgage exposure on a single income"],
        "conversations": [
            {
                "date": "2026-08-18",
                "interaction_type": "call",
                "summary": "Marcus confirmed the promotion came with a higher variable component, so his "
                           "guaranteed income has not risen as much as the headline. Wants the retirement "
                           "projection rerun on base salary only before committing to a larger regular premium.",
            },
            {
                "date": "2026-07-02",
                "interaction_type": "meeting",
                "summary": "Reviewed the Bishan purchase. Outstanding loan runs 22 years and there is no "
                           "mortgage-reducing cover in place. Marcus asked what happens to Serene and Ethan "
                           "if he were unable to work, and agreed to look at term cover matched to the loan.",
            },
        ],
    },
    "csv_adv_1002": {  # Priya Raman -- education funding discussion
        "family": [
            {"name": "Arun Raman", "relationship": "spouse"},
            {"name": "Meera Raman", "relationship": "daughter"},
        ],
        "life_events": [
            {"description": "Daughter Meera started primary school", "date": "2026-01-06", "category": "family"},
            {"description": "Returned to full-time work after parental leave", "date": "2025-11-18", "category": "career"},
        ],
        "goals": [
            {"description": "Build an education fund for Meera through to university", "category": "education"},
            {"description": "Hold six months of household expenses as an emergency buffer", "category": "savings"},
        ],
        "needs": [
            {"description": "Critical illness cover sized for a dual-income household", "category": "Protection"},
        ],
        "concerns": ["Education cost inflation", "Loss of one income during recovery from illness"],
        "conversations": [
            {
                "date": "2026-08-20",
                "interaction_type": "call",
                "summary": "Priya has been quoted materially higher fees for Meera's enrichment programme than "
                           "she budgeted. Asked whether to increase the regular savings contribution now or "
                           "wait until Arun's bonus in Q1. Wants a comparison of both before deciding.",
            },
            {
                "date": "2026-06-11",
                "interaction_type": "meeting",
                "summary": "Now that Priya is back full-time the household depends on two incomes rather than "
                           "one. Existing critical illness cover was sized when she was on leave and no longer "
                           "reflects the replacement cost of her salary.",
            },
        ],
    },
    "csv_adv_1004": {  # Grace Lim
        "family": [
            {"name": "Wei Sheng Lim", "relationship": "spouse"},
            {"name": "Lim Ah Choo", "relationship": "mother"},
        ],
        "life_events": [
            {"description": "Mother moved in following a fall at home", "date": "2026-03-22", "category": "family"},
            {"description": "Started a small F&B business", "date": "2025-07-15", "category": "career"},
        ],
        "goals": [
            {"description": "Cover eldercare costs without drawing down retirement savings", "category": "healthcare"},
            {"description": "Separate business and personal finances cleanly", "category": "planning"},
        ],
        "needs": [
            {"description": "Long-term care cover for her mother's ongoing mobility needs", "category": "Health"},
        ],
        "concerns": ["Eldercare and nursing costs", "Irregular income from the business"],
        "conversations": [
            {
                "date": "2026-08-16",
                "interaction_type": "meeting",
                "summary": "Grace is now the primary carer for her mother and has cut back business hours. "
                           "Household income is both lower and less predictable. Asked whether her existing "
                           "regular premium commitments can be made more flexible rather than lapsed.",
            },
            {
                "date": "2026-05-09",
                "interaction_type": "call",
                "summary": "Discussed her mother's post-fall care costs, currently paid out of pocket. Grace was "
                           "not aware long-term care cover existed as a distinct product and asked what could "
                           "still be underwritten at her mother's age.",
            },
        ],
    },
    "csv_adv_1005": {  # Samuel Wee
        "family": [
            {"name": "Rachel Wee", "relationship": "spouse"},
        ],
        "life_events": [
            {"description": "Married Rachel", "date": "2025-12-06", "category": "family"},
            {"description": "Relocated from Kuala Lumpur to Singapore", "date": "2026-04-02", "category": "relocation"},
        ],
        "goals": [
            {"description": "Buy a first home within three years", "category": "property"},
            {"description": "Consolidate Malaysian and Singapore policies into one plan", "category": "planning"},
        ],
        "needs": [
            {"description": "Review of cross-border coverage gaps created by the relocation", "category": "Protection"},
        ],
        "concerns": ["Cross-border policy gaps", "Housing affordability as a new resident"],
        "conversations": [
            {
                "date": "2026-08-21",
                "interaction_type": "call",
                "summary": "Samuel still holds two Malaysian policies and is unsure whether they pay out on a "
                           "Singapore claim. Wants a plain reading of what is covered where before deciding "
                           "whether to keep, convert or replace them.",
            },
            {
                "date": "2026-06-27",
                "interaction_type": "meeting",
                "summary": "First full review since the move. Samuel and Rachel are saving toward a flat and "
                           "want to know how much protection to carry while their savings are concentrated in "
                           "a housing deposit rather than liquid reserves.",
            },
        ],
    },
}

# Conversations for existing customers who had facts but no dialogue, so the
# graph does not look alive for exactly one person.
EXISTING_CUSTOMER_CONVERSATIONS: dict[str, list[dict]] = {
    "cust_01655": [  # Judy Chase -- husband laid off, tuition funding gap
        {
            "date": "2026-08-19",
            "interaction_type": "call",
            "summary": "Robert is still job-hunting and Judy is now covering household costs alone. She asked "
                       "whether the tuition top-up for Tyler can be deferred a semester without losing the "
                       "place, and what happens to her premiums if the gap runs longer than expected.",
        },
        {
            "date": "2026-07-24",
            "interaction_type": "meeting",
            "summary": "Confirmed the shortfall on Tyler's tuition and accommodation at roughly S$20,000. Judy "
                       "would rather not surrender any policy to fund it and asked what options exist short of that.",
        },
    ],
    "cust_00851": [  # Jonathan Franklin -- retirement, legacy
        {
            "date": "2026-08-12",
            "interaction_type": "meeting",
            "summary": "Jonathan wants his policy structure simplified before he retires -- he holds several "
                       "small contracts and cannot tell what each one does. Asked for a single view of what "
                       "pays out, when, and to whom.",
        },
        {
            "date": "2026-06-30",
            "interaction_type": "call",
            "summary": "Raised leaving something for Rachel's new household separately from the main estate. "
                       "Wants to understand whether that is better handled through beneficiary nominations "
                       "or a separate policy.",
        },
    ],
    "cust_01038": [  # Megan Jackson
        {
            "date": "2026-08-15",
            "interaction_type": "call",
            "summary": "Megan asked for a straightforward explanation of what her current cover pays out on, "
                       "having found the annual statement hard to read. No change requested yet -- she wants "
                       "to understand the position first.",
        },
    ],
}


def enrich_customer(customer_id: str, facts: dict) -> int:
    """Write one customer's facts. Returns the number of nodes merged."""
    written = 0

    if facts.get("family"):
        run_write(
            "MATCH (c:Customer {customer_id: $cid}) UNWIND $rows AS r "
            "MERGE (f:FamilyMember {customer_id: $cid, name: r.name}) "
            "SET f.relationship = r.relationship "
            "MERGE (c)-[e:HAS_FAMILY_MEMBER]->(f) "
            "SET e.source = $source, e.confidence = 1.0, e.created_at = $today",
            {"cid": customer_id, "rows": facts["family"], "source": SOURCE_NOTES, "today": TODAY_ISO},
        )
        written += len(facts["family"])

    if facts.get("life_events"):
        run_write(
            "MATCH (c:Customer {customer_id: $cid}) UNWIND $rows AS r "
            "MERGE (l:LifeEvent {customer_id: $cid, description: r.description}) "
            "SET l.date = r.date, l.category = r.category "
            "MERGE (c)-[e:EXPERIENCED]->(l) "
            "SET e.source = $source, e.confidence = 1.0, e.created_at = $today",
            {"cid": customer_id, "rows": facts["life_events"], "source": SOURCE_NOTES, "today": TODAY_ISO},
        )
        written += len(facts["life_events"])

    if facts.get("goals"):
        run_write(
            "MATCH (c:Customer {customer_id: $cid}) UNWIND $rows AS r "
            "MERGE (g:Goal {customer_id: $cid, description: r.description}) "
            "SET g.category = r.category "
            "MERGE (c)-[e:HAS_GOAL]->(g) "
            "SET e.source = $source, e.confidence = 1.0, e.created_at = $today",
            {"cid": customer_id, "rows": facts["goals"], "source": SOURCE_NOTES, "today": TODAY_ISO},
        )
        written += len(facts["goals"])

    if facts.get("needs"):
        run_write(
            "MATCH (c:Customer {customer_id: $cid}) UNWIND $rows AS r "
            "MERGE (n:Need {customer_id: $cid, description: r.description}) "
            "SET n.category = r.category "
            "MERGE (c)-[e:HAS_NEED]->(n) "
            "SET e.source = $source, e.confidence = 1.0, e.created_at = $today",
            {"cid": customer_id, "rows": facts["needs"], "source": SOURCE_NOTES, "today": TODAY_ISO},
        )
        written += len(facts["needs"])

    if facts.get("concerns"):
        run_write(
            "MATCH (c:Customer {customer_id: $cid}) UNWIND $rows AS name "
            "MERGE (t:Topic {name: name}) "
            "MERGE (c)-[e:CONCERNED_ABOUT]->(t) "
            "SET e.source = $source, e.confidence = 1.0, e.created_at = $today",
            {"cid": customer_id, "rows": facts["concerns"], "source": SOURCE_CONVO, "today": TODAY_ISO},
        )
        written += len(facts["concerns"])

    written += add_conversations(customer_id, facts.get("conversations", []))
    return written


def add_conversations(customer_id: str, conversations: list[dict]) -> int:
    if not conversations:
        return 0
    run_write(
        "MATCH (c:Customer {customer_id: $cid}) UNWIND $rows AS r "
        "MERGE (v:Conversation {customer_id: $cid, date: r.date}) "
        "SET v.summary = r.summary, v.interaction_type = r.interaction_type "
        "MERGE (c)-[:HAD_CONVERSATION]->(v)",
        {"cid": customer_id, "rows": conversations},
    )
    return len(conversations)


def fill_claim_stubs() -> int:
    """
    Complete Claim nodes that carry only an id.

    They arrived through document ingestion, which knows a claim reference but
    none of the claim's own facts. Where DuckDB has that claim, copy its
    properties across rather than leaving a node that renders as blanks.
    """
    stubs = [
        r["id"]
        for r in run_query("MATCH (c:Claim) WHERE c.claim_number IS NULL RETURN c.claim_id AS id")
    ]
    if not stubs:
        return 0

    con = get_connection()
    try:
        placeholders = ",".join(["?"] * len(stubs))
        rows = con.execute(
            f"""
            select claim_id, claim_number, claim_status, loss_cause, loss_date,
                   paid_amount, reserve_amount, policy_duration_months
            from claims where claim_id in ({placeholders})
            """,
            stubs,
        ).fetchall()
    finally:
        con.close()

    payload = [
        {
            "claim_id": r[0], "claim_number": r[1], "claim_status": r[2], "loss_cause": r[3],
            "loss_date": r[4].isoformat() if r[4] else None,
            "paid_amount": r[5], "reserve_amount": r[6], "policy_duration_months": r[7],
        }
        for r in rows
    ]
    if payload:
        run_write(
            "UNWIND $rows AS r MATCH (c:Claim {claim_id: r.claim_id}) SET c += r",
            {"rows": payload},
        )

    unmatched = set(stubs) - {p["claim_id"] for p in payload}
    if unmatched:
        # Genuinely external references (a document naming a claim this system
        # has no record of). Left alone -- inventing facts for them would be
        # worse than an honestly sparse node.
        print(f"  left {len(unmatched)} stub(s) with no DuckDB record: {sorted(unmatched)}")
    return len(payload)


TODAY_ISO = "2026-08-15"  # matches prioritization.TODAY, the app-wide demo date


def run() -> None:
    print("[enrich] CRM-imported customers")
    for cid, facts in CRM_CUSTOMERS.items():
        n = enrich_customer(cid, facts)
        name = run_query("MATCH (c:Customer {customer_id:$cid}) RETURN c.name AS n", {"cid": cid})
        label = name[0]["n"] if name else "(missing)"
        print(f"  {cid:<16} {label:<18} +{n} nodes")

    print("\n[enrich] conversations for existing customers")
    for cid, convos in EXISTING_CUSTOMER_CONVERSATIONS.items():
        n = add_conversations(cid, convos)
        name = run_query("MATCH (c:Customer {customer_id:$cid}) RETURN c.name AS n", {"cid": cid})
        label = name[0]["n"] if name else "(missing)"
        print(f"  {cid:<16} {label:<18} +{n} conversations")

    print("\n[repair] claim stubs")
    print(f"  filled {fill_claim_stubs()} claim node(s) from DuckDB")


def verify() -> bool:
    print("\n=== verification ===")
    ok = True

    edges = ("HAS_FAMILY_MEMBER", "EXPERIENCED", "HAS_GOAL", "HAS_NEED", "OWNS", "HAD_CONVERSATION", "CONCERNED_ABOUT")
    rows = run_query(
        "MATCH (c:Customer) OPTIONAL MATCH (c)-[r]->() "
        "WHERE type(r) IN $edges "
        "RETURN c.customer_id AS cid, c.name AS name, count(r) AS n ORDER BY n DESC",
        {"edges": list(edges)},
    )
    print("  knowledge-graph edges per customer:")
    empty = 0
    for r in rows:
        flag = "  <- empty" if r["n"] == 0 else ""
        if r["n"] == 0:
            empty += 1
        print(f"    {r['n']:>4}  {r['cid']:<16} {r['name']}{flag}")

    with_convos = run_query(
        "MATCH (:Customer)-[:HAD_CONVERSATION]->(v:Conversation) "
        "RETURN count(DISTINCT v.customer_id) AS c"
    )[0]["c"]
    passed = with_convos >= 4
    ok = ok and passed
    print(f"\n  [{'PASS' if passed else 'FAIL'}] customers with conversation history: {with_convos} (want >= 4)")

    stubs = run_query("MATCH (c:Claim) WHERE c.claim_number IS NULL RETURN count(c) AS c")[0]["c"]
    print(f"  [INFO] claim nodes still without a claim_number: {stubs}")

    # What matters for a fact node is that it renders and that it belongs to
    # someone -- not that it carries a denormalised customer_id. Older
    # Conversation nodes identify purely by their relationship, which is the
    # more correct model; an earlier version of this check demanded the
    # property and failed 77 perfectly good nodes.
    orphans = run_query(
        "MATCH (n) WHERE (n:FamilyMember OR n:LifeEvent OR n:Goal OR n:Need OR n:Conversation) "
        "AND NOT (:Customer)-->(n) RETURN count(n) AS c"
    )[0]["c"]
    passed = orphans == 0
    ok = ok and passed
    print(f"  [{'PASS' if passed else 'FAIL'}] fact nodes not reachable from any customer: {orphans}")

    blank = run_query(
        "MATCH (n) WHERE "
        "(n:FamilyMember AND n.name IS NULL) OR "
        "(n:LifeEvent AND n.description IS NULL) OR "
        "(n:Goal AND n.description IS NULL) OR "
        "(n:Need AND n.description IS NULL) OR "
        "(n:Conversation AND n.summary IS NULL) OR "
        "(n:Topic AND n.name IS NULL) "
        "RETURN count(n) AS c"
    )[0]["c"]
    passed = blank == 0
    ok = ok and passed
    print(f"  [{'PASS' if passed else 'FAIL'}] fact nodes with no content to display: {blank}")

    print(f"\n=== {'ALL CHECKS PASSED' if ok else 'CHECKS FAILED'} ===")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="checks only, no writes")
    args = ap.parse_args()
    if not args.verify:
        run()
    return 0 if verify() else 1


if __name__ == "__main__":
    sys.exit(main())

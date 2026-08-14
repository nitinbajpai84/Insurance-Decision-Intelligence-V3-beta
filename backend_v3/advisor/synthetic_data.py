"""
Synthetic enrichment for 10 real V2 customers, turning them into advisor
demo profiles: family, life stage, goals, needs, life events, meetings,
owned-policy relationships, concerns/discussed topics, and past
conversation notes.

Grounding: customer_id, name, segment, lifecycle_stage, risk_tier, and every
policy come from the real insurance_v3.duckdb data (unchanged, per
docs/ARCHITECTURE.md). Everything else here is synthetic-but-realistic
content authored on top of that real backbone, since V2 never had this
dimension.

Neo4j is the "relationship brain": Customer -[:HAS_GOAL]-> Goal,
-[:HAS_NEED]-> Need, -[:OWNS]-> Policy (lightweight — policy_id links back
to DuckDB for the authoritative premium/status figures), -[:EXPERIENCED]->
LifeEvent, -[:HAD_MEETING]-> Meeting, -[:CONCERNED_ABOUT]-> Topic,
-[:DISCUSSED]-> Topic, -[:HAS_FAMILY_MEMBER]-> FamilyMember.

Qdrant ("semantic memory") holds embedded conversation-note chunks per
customer, retrievable by meaning even when the advisor's question doesn't
use the customer's own words.

This IS the "advisor approves -> customer memory" step from the product's
core loop, run manually instead of from a conversation-extraction pipeline
(that pipeline is explicitly out of scope for Milestone 1) — but the node
shapes are the same ones that pipeline would write later.

Run: venv\\Scripts\\python.exe -m backend_v3.advisor.synthetic_data
Idempotent: every write is MERGE-based.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ADVISOR_NAME = "Nitin Bajpai"
# Timestamp written onto every seeded relationship's `created_at` provenance
# property (see the note above the relationship-writing loop below).
SEEDED_AT = "2026-08-15"

CUSTOMERS = {
    "cust_00570": {  # John Kemp
        "life_stage": "Young family — recently became a parent, dual-income household",
        "family": [
            {"name": "Sarah Kemp", "relationship": "spouse"},
            {"name": "Ella Kemp", "relationship": "daughter"},
        ],
        "goals": [
            {"description": "Build an education fund for daughter Ella", "category": "education"},
            {"description": "Review life coverage adequacy following his promotion", "category": "protection"},
        ],
        "needs": [
            {"description": "Adequate life protection for a single-income scenario if John were unable to work", "category": "Protection"},
        ],
        "concerns": ["Family financial security", "Ella's future education costs"],
        "discussed": ["Life coverage increase", "Education savings plan"],
        "life_events": [
            {"description": "Daughter Ella was born", "date": "2024-03-10", "category": "family"},
            {"description": "Promoted to Senior Engineering Manager", "date": "2026-05-01", "category": "career"},
        ],
        "meetings": [
            {"date": "2025-11-14", "summary": "Annual review. Discussed increasing life coverage after Ella's birth; John deferred the decision, wanted to think about budget."},
            {"date": "2026-03-02", "summary": "Follow-up call. John confirmed interest in an education savings plan but hasn't committed yet."},
        ],
        "conversations": [
            "John mentioned he's been stressed about balancing his new management role with family time. He said his top priority right now is making sure Ella is financially secure if anything happens to him, since Sarah's income alone wouldn't cover the mortgage. He was hesitant about the top-up premium though — said he wants to see the numbers laid out clearly before committing to anything.",
            "During the March call John brought up that his company just did a round of promotions and he got Senior Engineering Manager — a nice raise. He asked whether that changes what we should be doing with his existing policies now that his income is higher. He also mentioned Sarah is considering going back to work part-time next year once Ella starts preschool.",
        ],
    },
    "cust_01655": {  # Judy Chase
        "life_stage": "Pre-college planning — teenage son entering his final year of high school",
        "family": [
            {"name": "Robert Chase", "relationship": "spouse"},
            {"name": "Tyler Chase", "relationship": "son"},
        ],
        "goals": [
            {"description": "Fund Tyler's university tuition starting 2027", "category": "education"},
            {"description": "Reassess the lapsed investment policy", "category": "investment"},
        ],
        "needs": [
            {"description": "Funding-gap coverage for Tyler's tuition given rising costs", "category": "Education"},
        ],
        "concerns": ["University affordability", "Regret over the lapsed policy"],
        "discussed": ["Reinstating PRULink Vantage", "Education funding options"],
        "life_events": [
            {"description": "Son Tyler accepted into an engineering program, enrolling 2027", "date": "2026-04-01", "category": "family"},
            {"description": "Let PRULink Vantage lapse during a home renovation cash-flow crunch", "date": "2026-01-15", "category": "financial"},
        ],
        "meetings": [
            {"date": "2025-09-20", "summary": "Discussed the lapsed policy — Judy said budget was tight because of home renovations."},
            {"date": "2026-02-10", "summary": "Judy shared Tyler's college acceptance news and asked about funding options."},
        ],
        "conversations": [
            "Judy expressed real anxiety about being able to fund Tyler's university without dipping into her and Robert's retirement savings. She did the maths herself and it's tighter than she expected given tuition inflation.",
            "Judy brought up, almost apologetically, that she regrets letting the PRULink Vantage policy lapse during the renovation. She asked directly whether it could be reinstated or whether that ship has sailed.",
        ],
    },
    "cust_01038": {  # Megan Jackson
        "life_stage": "Career-focused professional, currently supporting aging parents",
        "family": [
            {"name": "Diane Jackson", "relationship": "mother"},
        ],
        "goals": [
            {"description": "Diversify investment holdings currently concentrated in PRULink Global Elite", "category": "investment"},
            {"description": "Consider critical illness coverage given a new family health history", "category": "protection"},
        ],
        "needs": [
            {"description": "Critical illness protection given hereditary risk exposure", "category": "Protection"},
        ],
        "concerns": ["Father's Parkinson's diagnosis", "Portfolio concentration risk"],
        "discussed": ["Critical illness coverage", "Fund diversification"],
        "life_events": [
            {"description": "Father diagnosed with early-stage Parkinson's disease", "date": "2026-02-01", "category": "family"},
            {"description": "Received a year-end bonus, considering a lump-sum policy top-up", "date": "2026-01-10", "category": "financial"},
        ],
        "meetings": [
            {"date": "2025-10-05", "summary": "Annual review."},
            {"date": "2026-02-20", "summary": "Megan shared her father's diagnosis and asked about critical illness coverage for herself given hereditary risk."},
        ],
        "conversations": [
            "Megan was visibly concerned about her father's Parkinson's diagnosis and asked pointed questions about whether it has a hereditary component, and whether she should get ahead of it with critical illness cover for herself now rather than waiting.",
            "Megan flagged, somewhat offhand, that three of her policies are all the same PRULink Global Elite fund and wondered out loud whether that's too concentrated — she said she'd never really looked at her portfolio holistically before.",
        ],
    },
    "cust_03177": {  # Anthony Moyer
        "life_stage": "Recently divorced, co-parenting, rebuilding his financial plan independently",
        "family": [
            {"name": "Maya Moyer", "relationship": "daughter"},
            {"name": "Jacob Moyer", "relationship": "son"},
        ],
        "goals": [
            {"description": "Update beneficiary designations following the divorce", "category": "estate_planning"},
            {"description": "Build an independent emergency fund", "category": "savings"},
        ],
        "needs": [
            {"description": "Corrected beneficiary designations reflecting the current family situation", "category": "Protection"},
        ],
        "concerns": ["Children's financial protection", "Outdated beneficiary designations"],
        "discussed": ["Beneficiary updates", "Post-divorce financial restructuring"],
        "life_events": [
            {"description": "Divorce finalized", "date": "2025-12-01", "category": "family"},
            {"description": "Moved to a 50/50 custody arrangement for Maya and Jacob", "date": "2026-01-20", "category": "family"},
        ],
        "meetings": [
            {"date": "2026-01-08", "summary": "First meeting post-divorce. Flagged that beneficiary designations still list his ex-spouse."},
            {"date": "2026-04-15", "summary": "Check-in — beneficiary update still pending."},
        ],
        "conversations": [
            "Anthony was clearly still adjusting to the divorce and admitted he hadn't gotten around to updating his beneficiaries even though we'd flagged it twice already — he said it 'felt too final' and he'd been avoiding it.",
            "He was firm that his main priority now is making sure Maya and Jacob are both protected if anything happens to him, independent of how the rest of the settlement plays out.",
        ],
    },
    "cust_00851": {  # Jonathan Franklin
        "life_stage": "Pre-retirement, high net worth, reassessing legacy planning",
        "family": [
            {"name": "Patricia Franklin", "relationship": "spouse"},
            {"name": "Rachel Franklin", "relationship": "daughter"},
        ],
        "goals": [
            {"description": "Legacy and estate planning ahead of retirement in roughly 5 years", "category": "estate_planning"},
            {"description": "Explore a gifting strategy to support Rachel's new household", "category": "wealth_transfer"},
        ],
        "needs": [
            {"description": "Simplified policy structure ahead of retirement", "category": "Retirement"},
        ],
        "concerns": ["Retirement timeline", "Legacy for Rachel's new household"],
        "discussed": ["Policy consolidation", "Retirement planning"],
        "life_events": [
            {"description": "Daughter Rachel got married", "date": "2025-11-08", "category": "family"},
            {"description": "No advisor contact in 14 months — account has gone dormant", "date": "2026-01-01", "category": "engagement"},
        ],
        "meetings": [
            {"date": "2024-09-12", "summary": "Last recorded meeting before the account went dormant."},
        ],
        "conversations": [
            "In the last meeting over a year ago, Jonathan mentioned he was starting to think seriously about retiring in the next five years and wanted to talk about consolidating his various policies into a cleaner structure — but we never followed up and the account went dormant.",
        ],
    },
    "cust_00040": {  # Kimberly Schmidt
        "life_stage": "Established professional, newly engaged, beginning to think about family planning",
        "family": [
            {"name": "David Ong", "relationship": "partner (engaged)"},
        ],
        "goals": [
            {"description": "Explore life insurance changes ahead of the wedding", "category": "protection"},
            {"description": "Reinstate or replace the lapsed WealthLink Plus policy", "category": "investment"},
        ],
        "needs": [
            {"description": "Life coverage review ahead of marriage and future family planning", "category": "Protection"},
        ],
        "concerns": ["Payment reliability after relocation", "Future family planning"],
        "discussed": ["Missed payment resolution", "Engagement and future planning"],
        "life_events": [
            {"description": "Got engaged to David", "date": "2026-03-14", "category": "family"},
            {"description": "WealthLink Plus lapsed after a missed payment during relocation", "date": "2025-12-01", "category": "financial"},
        ],
        "meetings": [
            {"date": "2026-01-15", "summary": "Discussed the relocation and the missed payment that caused the lapse."},
            {"date": "2026-04-02", "summary": "Kimberly shared her engagement news."},
        ],
        "conversations": [
            "Kimberly was excited about the engagement and asked in passing whether they should start thinking about life insurance changes now that they're planning a future together — but said she'd rather revisit it properly after the wedding date is set.",
            "She apologized for the missed payment that caused the WealthLink Plus lapse and asked us to make sure it doesn't happen again, mentioning the relocation had been chaotic.",
        ],
    },
    "cust_04280": {  # Clifford Chavez
        "life_stage": "Mid-career, two teenagers, balancing multiple financial priorities",
        "family": [
            {"name": "Denise Chavez", "relationship": "spouse"},
            {"name": "Marcus Chavez", "relationship": "son"},
            {"name": "Ava Chavez", "relationship": "daughter"},
        ],
        "goals": [
            {"description": "Check university savings trajectory against target for both children", "category": "education"},
            {"description": "Review health policy adequacy following Marcus's surgery", "category": "health"},
        ],
        "needs": [
            {"description": "Confirmed health coverage adequacy for the whole family", "category": "Healthcare"},
        ],
        "concerns": ["Whether education savings will hit target for both children"],
        "discussed": ["Marcus's surgery claim experience", "University savings projection"],
        "life_events": [
            {"description": "Son Marcus had an appendectomy, fully recovered", "date": "2026-02-14", "category": "health"},
            {"description": "Family relocated to a larger home", "date": "2025-10-01", "category": "lifestyle"},
        ],
        "meetings": [
            {"date": "2025-11-01", "summary": "Post-move check-in."},
            {"date": "2026-03-01", "summary": "Discussed Marcus's surgery — health policy performed well, no issues with the claim."},
        ],
        "conversations": [
            "Clifford was relieved the health policy covered Marcus's surgery smoothly and specifically said he appreciated how easy the claims process was — he said it reinforced his confidence in staying with us long-term.",
            "He asked for a projection of whether their current savings pace will actually hit the target for both kids' university funds, since Ava will be starting only a few years after Marcus.",
        ],
    },
    "cust_02143": {  # Jody Hernandez
        "life_stage": "Expecting their first child — early family-formation stage",
        "family": [
            {"name": "Marcus Hernandez", "relationship": "spouse"},
        ],
        "goals": [
            {"description": "Review health coverage ahead of the baby's arrival", "category": "health"},
            {"description": "Decide when to start an education fund for the child", "category": "education"},
        ],
        "needs": [
            {"description": "Health coverage review ahead of the baby's arrival", "category": "Healthcare"},
        ],
        "concerns": ["Timing of a new education fund", "Coverage adequacy before the birth"],
        "discussed": ["Pregnancy-related coverage questions", "Education fund timing"],
        "life_events": [
            {"description": "Announced pregnancy, due September 2026", "date": "2026-04-10", "category": "family"},
        ],
        "meetings": [
            {"date": "2026-04-20", "summary": "First meeting after sharing the pregnancy news."},
        ],
        "conversations": [
            "Jody and Marcus were both really excited sharing the pregnancy news and asked a lot of questions about what changes to their health coverage they should be thinking about before the baby arrives.",
            "Jody specifically asked whether they should wait until after the birth to set up an education fund, or start now while they're already thinking about it.",
        ],
    },
    "cust_02879": {  # Billy Perry
        "life_stage": "Single professional, active-investor mindset, newly variable income",
        "family": [],
        "goals": [
            {"description": "Reassess risk-adjusted investment mix given more active investing", "category": "investment"},
            {"description": "Understand why PRUProtect II lapsed and whether a replacement is needed", "category": "protection"},
        ],
        "needs": [
            {"description": "Protection structure resilient to variable, non-payroll income", "category": "Protection"},
        ],
        "concerns": ["Income variability from the side business", "Lapsed protection policy"],
        "discussed": ["Reinstating protection coverage", "Side-business income impact"],
        "life_events": [
            {"description": "Changed employer; payroll deduction gap caused PRUProtect II to lapse", "date": "2026-01-05", "category": "financial"},
            {"description": "Started a side business", "date": "2025-09-01", "category": "career"},
        ],
        "meetings": [
            {"date": "2025-09-15", "summary": "Discussed the new side business and increased income variability."},
            {"date": "2026-01-20", "summary": "Flagged the lapsed protection policy."},
        ],
        "conversations": [
            "Billy mentioned his side business has been taking off and his income is now more variable month to month — part of why the automatic payment for PRUProtect II failed after he switched banks for payroll reasons.",
            "He said he wants a policy structure that's more resilient to that kind of hiccup going forward, since he doesn't expect his income pattern to become more predictable any time soon.",
        ],
    },
    "cust_04676": {  # Kerri Smith
        "life_stage": "Post-bereavement, now sole financial decision-maker, adult son financially independent",
        "family": [
            {"name": "Daniel Smith", "relationship": "son"},
        ],
        "goals": [
            {"description": "Simplify her policy structure now that she manages finances independently", "category": "consolidation"},
            {"description": "Update the estate plan to reflect her current family structure", "category": "estate_planning"},
        ],
        "needs": [
            {"description": "Estate plan reflecting her current, post-bereavement family structure", "category": "Retirement"},
        ],
        "concerns": ["Estate plan accuracy", "Readiness to make decisions"],
        "discussed": ["Policy consolidation", "Estate plan update"],
        "life_events": [
            {"description": "Husband passed away", "date": "2025-06-20", "category": "family"},
            {"description": "Son Daniel moved out and became financially self-sufficient", "date": "2026-02-01", "category": "family"},
        ],
        "meetings": [
            {"date": "2025-08-05", "summary": "First meeting after the bereavement — kept brief, Kerri wasn't ready to discuss details."},
            {"date": "2026-03-10", "summary": "Follow-up — Kerri felt more ready to engage."},
        ],
        "conversations": [
            "In August Kerri was still processing the loss and asked us to keep things simple and not push any decisions — we agreed to check back in a few months rather than press her.",
            "By March she said she felt more settled and ready to actually look at consolidating everything and making sure her plan reflects her life now, as the sole decision-maker.",
        ],
    },
}


def _policies_by_customer(con, customer_ids: list[str]) -> dict[str, list[dict]]:
    ph = ",".join("?" for _ in customer_ids)
    rows = con.execute(
        f"select pol.customer_id, pol.policy_id, prod.product_name, prod.line_of_business "
        f"from policies pol join products prod on prod.product_id = pol.product_id "
        f"where pol.customer_id in ({ph})",
        customer_ids,
    ).fetchall()
    out: dict[str, list[dict]] = {}
    for customer_id, policy_id, product_name, line_of_business in rows:
        out.setdefault(customer_id, []).append(
            {"policy_id": policy_id, "product_name": product_name, "line_of_business": line_of_business}
        )
    return out


def seed() -> None:
    from backend_v3.graph_store.neo4j_client import run_write
    from backend_v3.ingestion.ocr import embed_text
    from backend_v3.structured_store.duckdb_client import get_connection
    from backend_v3.vector_store.qdrant_client import ensure_collection, upsert_points

    con = get_connection()
    customer_ids = list(CUSTOMERS.keys())
    real_names = {
        r[0]: r[1]
        for r in con.execute(
            f"select c.customer_id, p.display_name from customers c join parties p on p.party_id = c.party_id "
            f"where c.customer_id in ({','.join('?' for _ in customer_ids)})",
            customer_ids,
        ).fetchall()
    }
    policies = _policies_by_customer(con, customer_ids)
    con.close()

    ensure_collection("advisor_conversations")

    for customer_id, data in CUSTOMERS.items():
        name = real_names.get(customer_id, customer_id)
        print(f"[seed] {customer_id} ({name})")

        run_write(
            "MERGE (c:Customer {customer_id: $customer_id}) "
            "SET c.name = $name, c.life_stage = $life_stage, c.advisor_name = $advisor_name",
            {"customer_id": customer_id, "name": name, "life_stage": data["life_stage"], "advisor_name": ADVISOR_NAME},
        )
        run_write(
            "MATCH (c:Customer {customer_id: $customer_id}) "
            "MERGE (a:Advisor {name: $advisor_name}) "
            "MERGE (a)-[:ADVISES]->(c)",
            {"customer_id": customer_id, "advisor_name": ADVISOR_NAME},
        )

        # Every relationship below carries provenance (source/confidence/created_at)
        # on the relationship itself, not just the node — this is what lets the
        # briefing service cite "where did this come from" per insight, and is the
        # same shape a future conversation-extraction pipeline would write (with a
        # real conversation_id and a confidence < 1.0 pending advisor approval,
        # instead of this seed's already-curated advisor_notes / confidence 1.0).
        for fam in data["family"]:
            run_write(
                "MATCH (c:Customer {customer_id: $customer_id}) "
                "MERGE (f:FamilyMember {name: $name, customer_id: $customer_id}) "
                "SET f.relationship = $relationship "
                "MERGE (c)-[r:HAS_FAMILY_MEMBER]->(f) "
                "SET r.source = 'advisor_notes', r.confidence = 1.0, r.created_at = $seeded_at",
                {"customer_id": customer_id, "name": fam["name"], "relationship": fam["relationship"], "seeded_at": SEEDED_AT},
            )

        for goal in data["goals"]:
            run_write(
                "MATCH (c:Customer {customer_id: $customer_id}) "
                "MERGE (g:Goal {description: $description, customer_id: $customer_id}) "
                "SET g.category = $category "
                "MERGE (c)-[r:HAS_GOAL]->(g) "
                "SET r.source = 'advisor_notes', r.confidence = 1.0, r.created_at = $seeded_at",
                {"customer_id": customer_id, "description": goal["description"], "category": goal["category"], "seeded_at": SEEDED_AT},
            )

        for need in data["needs"]:
            run_write(
                "MATCH (c:Customer {customer_id: $customer_id}) "
                "MERGE (n:Need {description: $description, customer_id: $customer_id}) "
                "SET n.category = $category "
                "MERGE (c)-[r:HAS_NEED]->(n) "
                "SET r.source = 'advisor_notes', r.confidence = 1.0, r.created_at = $seeded_at",
                {"customer_id": customer_id, "description": need["description"], "category": need["category"], "seeded_at": SEEDED_AT},
            )

        for policy in policies.get(customer_id, []):
            run_write(
                "MATCH (c:Customer {customer_id: $customer_id}) "
                "MERGE (p:Policy {policy_id: $policy_id}) "
                "SET p.product_name = $product_name, p.line_of_business = $line_of_business "
                "MERGE (c)-[r:OWNS]->(p) "
                "SET r.source = 'policy_system', r.confidence = 1.0, r.created_at = $seeded_at",
                {"customer_id": customer_id, "seeded_at": SEEDED_AT, **policy},
            )

        for event in data["life_events"]:
            run_write(
                "MATCH (c:Customer {customer_id: $customer_id}) "
                "MERGE (e:LifeEvent {description: $description, customer_id: $customer_id}) "
                "SET e.date = $date, e.category = $category "
                "MERGE (c)-[r:EXPERIENCED]->(e) "
                "SET r.source = 'advisor_notes', r.confidence = 1.0, r.created_at = $seeded_at",
                {"customer_id": customer_id, "description": event["description"], "date": event["date"], "category": event["category"], "seeded_at": SEEDED_AT},
            )

        for meeting in data["meetings"]:
            run_write(
                "MATCH (c:Customer {customer_id: $customer_id}) "
                "MERGE (m:Meeting {date: $date, customer_id: $customer_id}) "
                "SET m.summary = $summary "
                "MERGE (c)-[r:HAD_MEETING]->(m) "
                "SET r.source = 'meeting_log', r.confidence = 1.0, r.created_at = $seeded_at",
                {"customer_id": customer_id, "date": meeting["date"], "summary": meeting["summary"], "seeded_at": SEEDED_AT},
            )

        for topic in data["concerns"]:
            run_write(
                "MATCH (c:Customer {customer_id: $customer_id}) "
                "MERGE (t:Topic {name: $topic}) "
                "MERGE (c)-[r:CONCERNED_ABOUT]->(t) "
                "SET r.source = 'conversation_notes', r.confidence = 1.0, r.created_at = $seeded_at",
                {"customer_id": customer_id, "topic": topic, "seeded_at": SEEDED_AT},
            )

        for topic in data["discussed"]:
            run_write(
                "MATCH (c:Customer {customer_id: $customer_id}) "
                "MERGE (t:Topic {name: $topic}) "
                "MERGE (c)-[r:DISCUSSED]->(t) "
                "SET r.source = 'conversation_notes', r.confidence = 1.0, r.created_at = $seeded_at",
                {"customer_id": customer_id, "topic": topic, "seeded_at": SEEDED_AT},
            )

        points = []
        for i, note in enumerate(data["conversations"]):
            vector = embed_text(note)
            points.append({
                "id": str(uuid.uuid4()),
                "vector": vector,
                "payload": {"customer_id": customer_id, "customer_name": name, "note_index": i, "text": note},
            })
        if points:
            upsert_points("advisor_conversations", points)

    print(f"[seed] done — {len(CUSTOMERS)} customers")


if __name__ == "__main__":
    seed()

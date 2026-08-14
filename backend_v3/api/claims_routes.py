"""
Claims endpoints: structured facts from DuckDB, merged with whatever
unstructured documents/entities/flags have been ingested for that claim
into Neo4j. This merge is the actual point of V3 — a claim now carries both
its system-of-record fields AND what the graph layer knows about it.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.structured_store.duckdb_client import get_connection

router = APIRouter(tags=["claims"])

LIST_SQL = """
select
  c.claim_id, c.claim_number, c.claim_status, c.loss_date, c.report_date,
  c.loss_cause, c.paid_amount, c.reserve_amount, c.litigation_flag,
  p.display_name as customer_name,
  count(f.claim_fraud_indicator_id) filter (where f.resolved_flag = false) as open_fraud_indicators
from claims c
left join customers cu on cu.customer_id = c.customer_id
left join parties p on p.party_id = cu.party_id
left join claim_fraud_indicators f on f.claim_id = c.claim_id
group by c.claim_id, c.claim_number, c.claim_status, c.loss_date, c.report_date,
         c.loss_cause, c.paid_amount, c.reserve_amount, c.litigation_flag, p.display_name
order by c.report_date desc
limit ?
"""

DETAIL_SQL = """
select
  c.claim_id, c.claim_number, c.claim_status, c.loss_date, c.report_date, c.close_date,
  c.loss_cause, c.loss_description, c.paid_amount, c.reserve_amount,
  c.litigation_flag, c.catastrophe_flag,
  p.display_name as customer_name, p.email as customer_email,
  c.policy_id, c.assigned_agent_id
from claims c
left join customers cu on cu.customer_id = c.customer_id
left join parties p on p.party_id = cu.party_id
where c.claim_id = ?
"""

FRAUD_SQL = """
select claim_fraud_indicator_id, indicator_date, indicator_type, indicator_source,
       indicator_score, severity, resolved_flag, resolution_outcome
from claim_fraud_indicators
where claim_id = ?
order by indicator_date desc
"""


@router.get("/claims")
def list_claims(limit: int = 50):
    con = get_connection()
    try:
        cols = [d[0] for d in con.execute(LIST_SQL, [limit]).description]
        rows = con.execute(LIST_SQL, [limit]).fetchall()
        return [dict(zip(cols, r)) for r in rows]
    finally:
        con.close()


@router.get("/claims/{claim_id}")
def get_claim(claim_id: str):
    con = get_connection()
    try:
        row = con.execute(DETAIL_SQL, [claim_id]).fetchone()
        if not row:
            raise HTTPException(404, f"Claim {claim_id} not found")
        cols = [d[0] for d in con.execute(DETAIL_SQL, [claim_id]).description]
        claim = dict(zip(cols, row))

        fraud_cols = [d[0] for d in con.execute(FRAUD_SQL, [claim_id]).description]
        fraud_rows = con.execute(FRAUD_SQL, [claim_id]).fetchall()
        claim["fraud_indicators"] = [dict(zip(fraud_cols, r)) for r in fraud_rows]
    finally:
        con.close()

    from backend_v3.graph_store.neo4j_client import run_query

    docs = run_query(
        """
        MATCH (d:Document)-[:BELONGS_TO]->(c:Claim {claim_id: $claim_id})
        OPTIONAL MATCH (p:Party)-[:MENTIONED_IN]->(d)
        OPTIONAL MATCH (f:Flag)-[:RAISED_BY]->(d)
        RETURN d.doc_id AS doc_id, d.doc_type AS doc_type, d.extraction_confidence AS confidence,
               collect(DISTINCT p.name) AS parties, collect(DISTINCT f.description) AS flags
        """,
        {"claim_id": claim_id},
    )
    claim["ingested_documents"] = docs
    return claim

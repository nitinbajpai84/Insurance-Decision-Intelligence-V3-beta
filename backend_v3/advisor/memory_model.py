"""
Customer Memory model — Milestone 2 (Remember My Customer).

A PendingMemory node is a proposed fact extracted from a conversation,
NOT yet part of the customer's truth. It carries:

  customer_id, memory_type, value, category, source (conversation_<id>),
  evidence (verbatim quote), confidence, created_at, last_verified_at,
  status (pending | accepted | rejected | edited)

Only on approval does it get promoted into a real graph fact — a Goal,
Need, LifeEvent, or Topic node, written with the SAME
MERGE + relationship-provenance pattern synthetic_data.py uses for the
Milestone 1 seed data. This is deliberate: it means Milestone 1's
retrieval.py and briefing_service.py need ZERO changes to pick up
Milestone 2 updates — an approved memory just becomes another row
retrieval.py already knows how to read.

Conflict detection is intentionally simple and explainable rather than a
black box: a new goal/need is flagged as a possible conflict if an
existing goal/need of the same category already exists for this customer.
The advisor decides what to do with a conflict — the system never
overwrites automatically (rule #7 in the Milestone 2 spec).
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MEMORY_TYPES = ("life_event", "goal", "need", "concern", "preference", "objection", "commitment", "follow_up")

# memory_type -> which existing node label/relationship a conflict check
# and an approval-promotion should target. preference/objection/commitment
# don't have a node shape to promote into, so they stay as
# PendingMemory-only facts once approved (still queryable, just not
# merged into a dedicated node). follow_up promotes into :FollowUp
# (followups.py) rather than Goal/Need/LifeEvent/Topic, since it needs its
# own lifecycle — due date, assignment, completion — the others don't.
_PROMOTABLE = {"life_event", "goal", "need", "concern"}
_PROMOTABLE_TO_FOLLOWUP = {"follow_up"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_conflict(customer_id: str, memory_type: str, category: str | None) -> dict[str, Any] | None:
    """Returns the conflicting existing fact if one exists, else None."""
    if memory_type not in ("goal", "need") or not category:
        return None
    from backend_v3.graph_store.neo4j_client import run_query

    label = "Goal" if memory_type == "goal" else "Need"
    rel = "HAS_GOAL" if memory_type == "goal" else "HAS_NEED"
    rows = run_query(
        f"MATCH (c:Customer {{customer_id: $customer_id}})-[:{rel}]->(n:{label}) "
        f"WHERE toLower(n.category) = toLower($category) "
        f"RETURN n.description AS description, n.category AS category LIMIT 1",
        {"customer_id": customer_id, "category": category},
    )
    return rows[0] if rows else None


def create_pending_memory(
    customer_id: str,
    memory_type: str,
    value: str,
    evidence: str,
    confidence: float,
    conversation_id: str,
    category: str | None = None,
) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_write

    memory_id = str(uuid.uuid4())
    now = _now()
    conflict = check_conflict(customer_id, memory_type, category)

    run_write(
        "MATCH (c:Customer {customer_id: $customer_id}) "
        "CREATE (m:PendingMemory {"
        "  memory_id: $memory_id, customer_id: $customer_id, memory_type: $memory_type, "
        "  value: $value, category: $category, source: $source, evidence: $evidence, "
        "  confidence: $confidence, created_at: $now, last_verified_at: $now, status: 'pending', "
        "  has_conflict: $has_conflict, conflict_with: $conflict_with"
        "}) "
        "MERGE (c)-[:HAS_PENDING_MEMORY]->(m)",
        {
            "customer_id": customer_id, "memory_id": memory_id, "memory_type": memory_type,
            "value": value, "category": category, "source": f"conversation_{conversation_id}",
            "evidence": evidence, "confidence": confidence, "now": now,
            "has_conflict": conflict is not None,
            "conflict_with": conflict["description"] if conflict else None,
        },
    )
    return {
        "memory_id": memory_id, "customer_id": customer_id, "memory_type": memory_type,
        "value": value, "category": category, "evidence": evidence, "confidence": confidence,
        "status": "pending", "has_conflict": conflict is not None,
        "conflict_with": conflict["description"] if conflict else None,
    }


def get_pending_memories(customer_id: str, status: str = "pending") -> list[dict[str, Any]]:
    from backend_v3.graph_store.neo4j_client import run_query

    return run_query(
        "MATCH (c:Customer {customer_id: $customer_id})-[:HAS_PENDING_MEMORY]->(m:PendingMemory) "
        "WHERE $status = 'all' OR m.status = $status "
        "RETURN m.memory_id AS memory_id, m.memory_type AS memory_type, m.value AS value, "
        "m.category AS category, m.evidence AS evidence, m.confidence AS confidence, "
        "m.status AS status, m.created_at AS created_at, m.has_conflict AS has_conflict, "
        "m.conflict_with AS conflict_with "
        "ORDER BY m.created_at DESC",
        {"customer_id": customer_id, "status": status},
    )


def _promote_to_graph_fact(customer_id: str, memory_type: str, value: str, category: str | None, conversation_id: str, confidence: float) -> None:
    from backend_v3.graph_store.neo4j_client import run_write

    now = _now()
    source = f"conversation_{conversation_id}"
    if memory_type == "life_event":
        run_write(
            "MATCH (c:Customer {customer_id: $customer_id}) "
            "MERGE (e:LifeEvent {description: $value, customer_id: $customer_id}) "
            "SET e.date = $today, e.category = coalesce($category, 'general') "
            "MERGE (c)-[r:EXPERIENCED]->(e) "
            "SET r.source = $source, r.confidence = $confidence, r.created_at = $now",
            {"customer_id": customer_id, "value": value, "category": category, "source": source,
             "confidence": confidence, "now": now, "today": now[:10]},
        )
    elif memory_type == "goal":
        run_write(
            "MATCH (c:Customer {customer_id: $customer_id}) "
            "MERGE (g:Goal {description: $value, customer_id: $customer_id}) "
            "SET g.category = coalesce($category, 'general') "
            "MERGE (c)-[r:HAS_GOAL]->(g) "
            "SET r.source = $source, r.confidence = $confidence, r.created_at = $now",
            {"customer_id": customer_id, "value": value, "category": category, "source": source,
             "confidence": confidence, "now": now},
        )
    elif memory_type == "need":
        run_write(
            "MATCH (c:Customer {customer_id: $customer_id}) "
            "MERGE (n:Need {description: $value, customer_id: $customer_id}) "
            "SET n.category = coalesce($category, 'general') "
            "MERGE (c)-[r:HAS_NEED]->(n) "
            "SET r.source = $source, r.confidence = $confidence, r.created_at = $now",
            {"customer_id": customer_id, "value": value, "category": category, "source": source,
             "confidence": confidence, "now": now},
        )
    elif memory_type == "concern":
        run_write(
            "MATCH (c:Customer {customer_id: $customer_id}) "
            "MERGE (t:Topic {name: $value}) "
            "MERGE (c)-[r:CONCERNED_ABOUT]->(t) "
            "SET r.source = $source, r.confidence = $confidence, r.created_at = $now",
            {"customer_id": customer_id, "value": value, "source": source, "confidence": confidence, "now": now},
        )


def approve_memory(memory_id: str, edited_value: str | None = None) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_query, run_write

    rows = run_query("MATCH (m:PendingMemory {memory_id: $memory_id}) RETURN m", {"memory_id": memory_id})
    if not rows:
        raise ValueError(f"Pending memory {memory_id} not found")
    mem = dict(rows[0]["m"])

    final_value = edited_value.strip() if edited_value and edited_value.strip() else mem["value"]
    new_status = "edited" if edited_value and edited_value.strip() and edited_value.strip() != mem["value"] else "accepted"

    run_write(
        "MATCH (m:PendingMemory {memory_id: $memory_id}) "
        "SET m.status = $status, m.value = $final_value, m.last_verified_at = $now",
        {"memory_id": memory_id, "status": new_status, "final_value": final_value, "now": _now()},
    )

    followup_id = None
    if mem["memory_type"] in _PROMOTABLE:
        conversation_id = mem["source"].replace("conversation_", "", 1)
        _promote_to_graph_fact(
            mem["customer_id"], mem["memory_type"], final_value, mem.get("category"),
            conversation_id, mem["confidence"],
        )
    elif mem["memory_type"] in _PROMOTABLE_TO_FOLLOWUP:
        from backend_v3.advisor.followups import create_followup

        created = create_followup(
            customer_id=mem["customer_id"],
            title=final_value,
            source=mem["source"],
            evidence=mem.get("evidence"),
            confidence=mem["confidence"],
        )
        followup_id = created["followup_id"]

    promoted = mem["memory_type"] in _PROMOTABLE or mem["memory_type"] in _PROMOTABLE_TO_FOLLOWUP
    return {
        "memory_id": memory_id, "status": new_status, "value": final_value,
        "promoted": promoted, "followup_id": followup_id,
    }


def reject_memory(memory_id: str) -> dict[str, Any]:
    from backend_v3.graph_store.neo4j_client import run_write

    run_write(
        "MATCH (m:PendingMemory {memory_id: $memory_id}) SET m.status = 'rejected', m.last_verified_at = $now",
        {"memory_id": memory_id, "now": _now()},
    )
    return {"memory_id": memory_id, "status": "rejected"}


def list_all_pending_memories(limit: int = 20) -> list[dict[str, Any]]:
    """Pending memories across every customer, for My Day's
    "memory updates awaiting approval" panel — a single advisor's queue,
    not something Customer 360's per-customer view exposes."""
    from backend_v3.graph_store.neo4j_client import run_query

    return run_query(
        "MATCH (c:Customer)-[:HAS_PENDING_MEMORY]->(m:PendingMemory {status: 'pending'}) "
        "RETURN m.memory_id AS memory_id, c.customer_id AS customer_id, c.name AS customer_name, "
        "m.memory_type AS memory_type, m.value AS value, m.category AS category, "
        "m.evidence AS evidence, m.confidence AS confidence, m.created_at AS created_at, "
        "m.has_conflict AS has_conflict, m.conflict_with AS conflict_with "
        "ORDER BY m.created_at DESC LIMIT $limit",
        {"limit": limit},
    )


def get_memory_timeline(customer_id: str) -> list[dict[str, Any]]:
    """Every memory event (pending, accepted, edited, rejected) for the
    Customer Memory Timeline UI, newest first."""
    from backend_v3.graph_store.neo4j_client import run_query

    return run_query(
        "MATCH (c:Customer {customer_id: $customer_id})-[:HAS_PENDING_MEMORY]->(m:PendingMemory) "
        "RETURN m.memory_id AS memory_id, m.memory_type AS memory_type, m.value AS value, "
        "m.status AS status, m.confidence AS confidence, m.created_at AS created_at, "
        "m.last_verified_at AS last_verified_at, m.source AS source "
        "ORDER BY m.created_at DESC",
        {"customer_id": customer_id},
    )

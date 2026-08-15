"""
Customer Knowledge Coverage and Memory Freshness — Stage 4.

Coverage answers "how much do we actually know about this customer,
across the categories that matter." Nine categories, matching the spec:
Profile, Family, Life stage, Financial (portfolio), Goals, Needs,
Preferences, Recent events, Relationship history (meetings/conversations).
Each is present/absent from real graph data — never an AI judgment about
how complete the picture "feels."

Freshness answers a different question: of what we know, how recently
was each fact actually verified. `created_at` on a relationship is the
best proxy this schema has for "last verified" (a re-approval or a
Milestone 2 re-confirmation would bump it) — it is not a separate
verification workflow, so this is stated as an assumption in the field
name (`last_verified_at` sourced from `created_at`) rather than implying
a distinct human verification step that does not exist yet.

Stale facts are turned into discovery questions rather than assumptions,
per the spec's explicit instruction — e.g. "When did you last review
your retirement goal?" rather than assuming the 14-month-old figure is
still correct.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FRESHNESS_STALE_DAYS = 180  # matches prioritization.STALE_CONTACT_DAYS


def _months_ago(iso_date: str | None) -> int | None:
    if not iso_date:
        return None
    try:
        parsed = datetime.fromisoformat(str(iso_date).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(str(iso_date)[:10]), datetime.min.time())
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - parsed).days
    return max(days // 30, 0)


def _freshness_status(iso_date: str | None) -> str:
    if not iso_date:
        return "unknown"
    months = _months_ago(iso_date)
    if months is None:
        return "unknown"
    return "stale" if months * 30 >= FRESHNESS_STALE_DAYS else "current"


def compute_coverage(customer_id: str) -> dict[str, Any] | None:
    """Presence/absence across the nine spec categories, plus an overall
    percentage — categories weighted equally since none is more
    authoritative than another for "how well do we know this person."
    """
    from backend_v3.advisor.retrieval import assemble_customer_context

    ctx = assemble_customer_context(customer_id)
    if ctx is None:
        return None

    categories = [
        {
            "category": "Profile",
            "present": bool(ctx.get("name")),
            "detail": ctx.get("name") or None,
        },
        {
            "category": "Family",
            "present": bool(ctx["family"]),
            "detail": f"{len(ctx['family'])} member(s) recorded" if ctx["family"] else None,
        },
        {
            "category": "Life stage",
            "present": bool(ctx.get("life_stage")),
            "detail": ctx.get("life_stage") or None,
        },
        {
            "category": "Financial",
            "present": bool(ctx["portfolio"]),
            "detail": f"{len(ctx['portfolio'])} polic{'y' if len(ctx['portfolio']) == 1 else 'ies'} on file" if ctx["portfolio"] else None,
        },
        {
            "category": "Goals",
            "present": bool(ctx["goals"]),
            "detail": f"{len(ctx['goals'])} goal(s) recorded" if ctx["goals"] else None,
        },
        {
            "category": "Needs",
            "present": bool(ctx["needs"]),
            "detail": f"{len(ctx['needs'])} need(s) recorded" if ctx["needs"] else None,
        },
        {
            "category": "Preferences",
            "present": bool(ctx["discussed_topics"]),
            "detail": f"{len(ctx['discussed_topics'])} discussed topic(s)" if ctx["discussed_topics"] else None,
        },
        {
            "category": "Recent events",
            "present": bool(ctx["life_events"]),
            "detail": f"{len(ctx['life_events'])} life event(s) recorded" if ctx["life_events"] else None,
        },
        {
            "category": "Relationship history",
            "present": bool(ctx["meetings"]) or bool(ctx.get("relevant_conversations")),
            "detail": f"{len(ctx['meetings'])} meeting(s), {len(ctx.get('relevant_conversations') or [])} conversation excerpt(s)",
        },
    ]

    present_count = sum(1 for c in categories if c["present"])
    coverage_pct = round(100 * present_count / len(categories))
    missing = [c["category"] for c in categories if not c["present"]]

    return {
        "customer_id": customer_id,
        "name": ctx["name"],
        "coverage_percent": coverage_pct,
        "categories": categories,
        "missing_categories": missing,
    }


def compute_freshness(customer_id: str) -> dict[str, Any] | None:
    """Per-fact freshness, grouped the way the spec's example shows:
    'Income — Last verified: 14 months ago — Status: Stale.'"""
    from backend_v3.advisor.retrieval import get_customer_graph

    graph = get_customer_graph(customer_id)
    if graph is None:
        return None

    entries: list[dict[str, Any]] = []

    def _add(label: str, created_at: str | None, category: str):
        months = _months_ago(created_at)
        entries.append({
            "label": label,
            "category": category,
            "last_verified_at": created_at,
            "months_ago": months,
            "status": _freshness_status(created_at),
        })

    # Neo4j relationship provenance carries created_at but retrieval.py's
    # goal/need/family projections don't currently select it — query it
    # directly so freshness has real dates instead of guessing.
    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        "MATCH (c:Customer {customer_id: $customer_id})-[r]->(n) "
        "WHERE type(r) IN ['HAS_GOAL','HAS_NEED','EXPERIENCED','CONCERNED_ABOUT','HAS_FAMILY_MEMBER'] "
        "RETURN type(r) AS rel_type, coalesce(n.description, n.name, n.topic) AS label, "
        "r.created_at AS created_at",
        {"customer_id": customer_id},
    )
    entries = []
    label_by_type = {
        "HAS_GOAL": "Goal",
        "HAS_NEED": "Need",
        "EXPERIENCED": "Life event",
        "CONCERNED_ABOUT": "Concern",
        "HAS_FAMILY_MEMBER": "Family",
    }
    category_by_type = {
        "HAS_GOAL": "goals",
        "HAS_NEED": "needs",
        "EXPERIENCED": "recent_events",
        "CONCERNED_ABOUT": "concerns",
        "HAS_FAMILY_MEMBER": "family",
    }
    for row in rows:
        prefix = label_by_type.get(row["rel_type"], row["rel_type"])
        _add(f"{prefix}: {row['label']}", row.get("created_at"), category_by_type.get(row["rel_type"], "other"))

    stale = [e for e in entries if e["status"] == "stale"]
    discovery_questions = [_discovery_question(e) for e in stale]

    return {
        "customer_id": customer_id,
        "entries": sorted(entries, key=lambda e: e["months_ago"] if e["months_ago"] is not None else -1, reverse=True),
        "stale_count": len(stale),
        "current_count": sum(1 for e in entries if e["status"] == "current"),
        "discovery_questions": discovery_questions,
    }


def _discovery_question(entry: dict[str, Any]) -> str:
    """A stale fact becomes a question, not an assumption — the spec's
    explicit instruction."""
    months = entry["months_ago"]
    age = f"{months} months" if months is not None else "some time"
    return f"It's been {age} since we confirmed \"{entry['label']}\" — is that still accurate?"

"""
Meeting Preparation service — BE-6 in the product's architecture doc.

Design principle: Gemini is reasoning, not memory. Every FACTUAL section of
the briefing (portfolio, family, goals, needs, what the customer said,
prior concerns) is assembled directly from retrieval.py with NO Gemini
involvement — those sections are 100% grounded, confidence 1.0, sourced
straight from the relationship provenance in Neo4j/DuckDB/Qdrant.

Gemini is used ONLY for the genuinely interpretive pieces that need
synthesis over the retrieved facts: the executive summary, prioritizing
which life events matter most, and drafting suggested questions /
discussion areas. Every Gemini-generated item must cite which retrieved
fact it's based on (`based_on`) — no ungrounded suggestions.

No financial recommendations are ever generated — enforced both in the
prompt and by the response schema only having a "potential discussion
area" shape, never a "recommend product X" shape.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.config import GEMINI_API_KEY, GEMINI_MODEL

BRIEFING_SCHEMA = {
    "type": "object",
    "properties": {
        "who_is_customer": {"type": "string", "description": "2-3 sentence executive summary of who this customer is right now."},
        "what_changed": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "based_on": {"type": "string", "description": "Which specific life event this refers to."},
                },
                "required": ["description", "priority", "based_on"],
            },
        },
        "suggested_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "based_on": {"type": "string", "description": "Which retrieved fact or conversation prompted this question."},
                },
                "required": ["question", "based_on"],
            },
        },
        "potential_discussion_areas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "area": {"type": "string", "description": "A topic area to potentially discuss, e.g. 'Education funding review' — never a specific product name or 'sell X'."},
                    "why": {"type": "string"},
                    "based_on": {"type": "string"},
                },
                "required": ["area", "why", "based_on"],
            },
        },
    },
    "required": ["who_is_customer", "what_changed", "suggested_questions", "potential_discussion_areas"],
}

SYSTEM_INSTRUCTION = """You are an assistant helping a financial/insurance advisor prepare for a customer meeting.

You will be given everything currently known about the customer, retrieved from a knowledge graph, a portfolio system, and past conversation notes. You are reasoning over ALREADY-VERIFIED facts, not inventing new ones — every claim you make must be traceable to something in the provided context via the "based_on" field.

STRICT RULES:
1. Never make a financial product recommendation or say "the advisor should sell/offer X". Frame everything as a "potential discussion area" for the advisor to explore with the customer, not a decision already made.
2. Every item in what_changed, suggested_questions, and potential_discussion_areas MUST cite a specific based_on fact from the provided context. Do not invent life events, goals, or concerns not present in the context.
3. what_changed priority: "high" only for life events that are recent, financially significant, or directly connect to a stated goal/need/concern; "low" for minor or old events.
4. suggested_questions must contain EXACTLY 3 to 5 questions (never more than 5) — pick the most useful, genuinely specific ones rather than listing every possible angle. Each must be an open question an advisor could ask this specific customer, not a generic question that would apply to anyone.
5. If the context is thin (few facts), it is fine to return fewer items rather than padding with generic content."""


def _format_context_for_prompt(ctx: dict[str, Any]) -> str:
    def _bullets(items: list[str]) -> list[str]:
        return [f"  - {i}" for i in items] or ["  (none recorded)"]

    family_str = ", ".join(f"{f['name']} ({f['relationship']})" for f in ctx["family"]) or "none recorded"
    quote = chr(34)
    lines = [
        f"Customer: {ctx['name']}",
        f"Life stage: {ctx['life_stage']}",
        f"Family: {family_str}",
        "",
        "Goals:",
        *_bullets([f"{g['description']} (category: {g['category']})" for g in ctx["goals"]]),
        "Needs:",
        *_bullets([f"{n['description']} (category: {n['category']})" for n in ctx["needs"]]),
        "",
        "Life events (most recent first):",
        *_bullets([f"{e['date']}: {e['description']} (category: {e['category']})" for e in ctx["life_events"]]),
        "",
        "Concerns raised:",
        *_bullets([c["topic"] for c in ctx["concerns"]]),
        "Previously discussed topics:",
        *_bullets([d["topic"] for d in ctx["discussed_topics"]]),
        "",
        "Meeting history:",
        *_bullets([f"{m['date']}: {m['summary']}" for m in ctx["meetings"]]),
        "",
        "Portfolio:",
        *_bullets([f"{p['product_name']} ({p['line_of_business']}, {p['policy_status']}, SGD {p['annual_premium']:,.0f}/yr)" for p in ctx["portfolio"]]),
        "",
        "Relevant past conversation notes:",
        *_bullets([f"{quote}{c['text']}{quote}" for c in ctx["relevant_conversations"]]),
    ]
    return "\n".join(lines)


def _call_gemini(ctx: dict[str, Any]) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = _format_context_for_prompt(ctx)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=BRIEFING_SCHEMA,
        ),
    )
    return json.loads(response.text)


def prepare_meeting_briefing(customer_id: str) -> dict[str, Any] | None:
    """The BE-6 Meeting Intelligence Service entry point: Customer ID ->
    Neo4j relationships + Qdrant memories + DuckDB portfolio -> Gemini
    reasoning -> structured Meeting Brief."""
    from backend_v3.advisor.retrieval import assemble_customer_context

    ctx = assemble_customer_context(customer_id)
    if ctx is None:
        return None

    try:
        generated = _call_gemini(ctx)
    except Exception as exc:
        # Deterministic sections are still fully usable even if Gemini is
        # unavailable — degrade gracefully rather than failing the whole
        # briefing, and surface the error so the frontend can show it.
        generated = {
            "who_is_customer": None,
            "what_changed": [],
            "suggested_questions": [],
            "potential_discussion_areas": [],
            "_gemini_error": f"{type(exc).__name__}: {exc}",
        }

    return {
        "customer_id": ctx["customer_id"],
        "name": ctx["name"],
        "life_stage": {"value": ctx["life_stage"], "source": "advisor_notes", "confidence": 1.0},
        "who_is_customer": {
            "value": generated.get("who_is_customer"),
            "source": "ai_synthesized", "based_on": "full customer context",
        },
        "what_changed": [
            {**item, "source": "ai_synthesized"} for item in generated.get("what_changed", [])
        ],
        "what_matters": {
            "goals": ctx["goals"],
            "needs": ctx["needs"],
        },
        "what_they_said": ctx["relevant_conversations"],
        "what_to_remember": {
            "concerns": ctx["concerns"],
            "past_meetings": ctx["meetings"],
        },
        "suggested_questions": [
            {**item, "source": "ai_synthesized"} for item in generated.get("suggested_questions", [])
        ],
        "potential_discussion_areas": [
            {**item, "source": "ai_synthesized"} for item in generated.get("potential_discussion_areas", [])
        ],
        "portfolio": ctx["portfolio"],
        "family": ctx["family"],
        "gemini_error": generated.get("_gemini_error"),
    }

"""
BE-3 Conversation Intelligence Service — Milestone 2.

Transcript -> Gemini extraction -> structured items with evidence +
confidence. This is the ONLY place Gemini is allowed to propose new facts
about a customer (as opposed to briefing_service.py, which only reasons
over already-approved facts) — and even here, nothing it proposes becomes
customer truth until an advisor approves it via memory_model.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "2-4 sentence summary of what this conversation covered."},
        "extracted_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "enum": ["life_event", "goal", "need", "concern", "preference", "objection", "commitment", "follow_up"],
                    },
                    "value": {"type": "string", "description": "A clean, concise statement of the fact — not a raw quote."},
                    "evidence": {"type": "string", "description": "The verbatim (or near-verbatim) part of the transcript this is based on."},
                    "confidence": {"type": "number"},
                    "category": {"type": "string", "description": "e.g. education, protection, retirement, health, investment, estate_planning — omit if not applicable."},
                },
                "required": ["memory_type", "value", "evidence", "confidence"],
            },
        },
    },
    "required": ["summary", "extracted_items"],
}

SYSTEM_INSTRUCTION = """You are analyzing a transcript of a meeting between a financial/insurance advisor and their customer, to identify new information worth remembering about the customer.

For each distinct new fact you find, classify it as one of: life_event, goal, need, concern, preference, objection, commitment, follow_up.

STRICT RULES:
1. Only extract things actually said or clearly implied in the transcript — do not infer beyond what's there. evidence must be a real quote or close paraphrase from the transcript.
2. confidence should genuinely reflect how explicit/certain the statement was (0.9+ for something stated directly and unambiguously, 0.5-0.7 for something implied or hedged, below 0.5 for a weak inference) — don't default everything to a high number.
3. Do not extract generic pleasantries or things with no advisory relevance.
4. Do not make financial recommendations or product suggestions — you are extracting facts about the customer, not advising.
5. If nothing meaningful is in the transcript, return an empty extracted_items list rather than padding it."""


def analyze_conversation(transcript: str) -> dict[str, Any]:
    if not transcript or not transcript.strip():
        raise ValueError("Transcript is empty")

    from backend_v3.advisor.ai_service import generate_json

    return generate_json(
        contents=f"Transcript:\n\n{transcript}",
        system_instruction=SYSTEM_INSTRUCTION,
        response_schema=EXTRACTION_SCHEMA,
    )

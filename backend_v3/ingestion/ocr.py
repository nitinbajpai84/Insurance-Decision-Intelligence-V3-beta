"""
OCR + structured extraction for claims documents, via Gemini multimodal.

V2 used the deprecated google.generativeai SDK (see the FutureWarning it
prints on every startup). V3 is a fresh build, so this uses the current
google.genai SDK instead — no reason to carry over a dependency that's
already flagged for removal.

Why Gemini over Tesseract/spaCy for this: real-world claim documents are
messy scans, handwriting, tables — a multimodal LLM reads them far more
reliably than a classic OCR+NER pipeline, and we already have a paid,
working Gemini key. Tesseract remains a cheaper fallback worth adding later
if ingestion volume makes per-document LLM cost a real concern.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v3.config import GEMINI_API_KEY, GEMINI_VISION_MODEL

EXTRACTION_PROMPT = """You are extracting structured data from an insurance claims document.
Read the attached document (it may be a scanned form, a typed report, a photo of damage, or handwritten notes) and return ONLY a JSON object with this shape:

{
  "doc_type": "claim_form | medical_report | adjuster_note | damage_photo | correspondence | other",
  "full_text": "<the complete OCR'd text, or a description if it's primarily an image>",
  "extracted_fields": {
    "claim_number": "<if present, else null>",
    "dates": ["<any dates mentioned, ISO format if possible>"],
    "amounts": [{"label": "<what this amount is>", "value": <number>, "currency": "<e.g. SGD>"}],
    "parties": [{"name": "<person or org>", "role": "<claimant | adjuster | provider | witness | other>"}],
    "diagnosis_or_damage": "<medical diagnosis or damage description, if applicable>",
    "flags": ["<anything suspicious or notable worth a fraud/claims reviewer's attention>"]
  },
  "extraction_confidence": <0.0-1.0>
}

Return ONLY the JSON object, no markdown fences, no commentary."""


def extract_claim_document(file_bytes: bytes, mime_type: str) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_VISION_MODEL,
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            EXTRACTION_PROMPT,
        ],
    )
    text = (response.text or "").strip()
    # Defensive: strip markdown fences if the model adds them despite instructions.
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned non-JSON extraction output: {exc}\n---\n{text[:500]}")


def embed_text(text: str) -> list[float]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")

    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    result = client.models.embed_content(model="models/gemini-embedding-001", contents=text)
    return result.embeddings[0].values

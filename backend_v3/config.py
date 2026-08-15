"""
Meridian V3 (beta) — backend configuration.

Same env-driven pattern as V2's backend_v2/config.py: load .env, expose
typed constants, one source of truth. See docs/ARCHITECTURE.md for what
each service is for.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")


def _str(name: str, default: str) -> str:
    return os.environ.get(name, "").strip() or default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


# --- Gemini (reused from V2 for OCR/extraction + generation + embeddings) --
GEMINI_API_KEY: str = _str("GEMINI_API_KEY", "")
GEMINI_MODEL: str = _str("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_VISION_MODEL: str = _str("GEMINI_VISION_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL: str = _str("EMBEDDING_MODEL", "models/gemini-embedding-001")

# --- Structured business data (unchanged from V2) ---------------------------
DUCKDB_PATH: str = _str("DUCKDB_PATH", str(PROJECT_ROOT / "database" / "insurance_v3.duckdb"))
DUCKDB_CONFIG: dict[str, object] = {
    "memory_limit": _str("DUCKDB_MEMORY_LIMIT", "1GB"),
    "threads": _int("DUCKDB_THREADS", 2),
}

# --- Neo4j AuraDB (context graph) -------------------------------------------
# Get these from the AuraDB Free instance's connection details (downloaded
# once at creation time) or console.neo4j.io -> your instance -> Connect.
NEO4J_URI: str = _str("NEO4J_URI", "")
NEO4J_USER: str = _str("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = _str("NEO4J_PASSWORD", "")
NEO4J_DATABASE: str = _str("NEO4J_DATABASE", "neo4j")

# --- Qdrant Cloud (vector search) -------------------------------------------
QDRANT_URL: str = _str("QDRANT_URL", "")
QDRANT_API_KEY: str = _str("QDRANT_API_KEY", "")

# --- Integrations (Stage 2) --------------------------------------------------
# Fernet key protecting stored OAuth tokens. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Without it, OAuth providers refuse to connect rather than store a token
# in plaintext (see integrations/token_store.py).
INTEGRATION_ENCRYPTION_KEY: str = _str("INTEGRATION_ENCRYPTION_KEY", "")

# OAuth client credentials. A provider stays not_connected until its pair
# is present — registry.Provider.missing_config() reports which are absent.
GOOGLE_OAUTH_CLIENT_ID: str = _str("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET: str = _str("GOOGLE_OAUTH_CLIENT_SECRET", "")
MS_OAUTH_CLIENT_ID: str = _str("MS_OAUTH_CLIENT_ID", "")
MS_OAUTH_CLIENT_SECRET: str = _str("MS_OAUTH_CLIENT_SECRET", "")
MS_OAUTH_TENANT: str = _str("MS_OAUTH_TENANT", "common")
OAUTH_REDIRECT_BASE: str = _str("OAUTH_REDIRECT_BASE", "http://127.0.0.1:3011")

# Timezone meeting times are displayed in. Calendars deliver UTC (or an
# explicit offset); the advisor reads their own local clock, so rendering
# raw UTC would show a 10:00 SGT meeting as 02:00.
DISPLAY_TIMEZONE: str = _str("DISPLAY_TIMEZONE", "Asia/Singapore")

# How long raw communication content may be retained after ingestion.
# Email/chat bodies past this age are dropped; derived summaries persist.
COMMUNICATION_RETENTION_DAYS: int = _int("COMMUNICATION_RETENTION_DAYS", 90)

# --- API ----------------------------------------------------------------------
API_PORT: int = _int("API_PORT", 3011)
_cors_env = _str("CORS_ORIGINS", "")
if _cors_env == "*":
    CORS_ORIGINS: list[str] = ["*"]
elif _cors_env:
    CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    CORS_ORIGINS = ["http://localhost:3012", "http://127.0.0.1:3012"]


def require_neo4j() -> tuple[str, str, str]:
    if not (NEO4J_URI and NEO4J_PASSWORD):
        raise RuntimeError(
            "NEO4J_URI / NEO4J_PASSWORD not configured — create an AuraDB Free "
            "instance at console.neo4j.io and set them in backend_v3/.env"
        )
    return NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def require_qdrant() -> tuple[str, str]:
    if not (QDRANT_URL and QDRANT_API_KEY):
        raise RuntimeError(
            "QDRANT_URL / QDRANT_API_KEY not configured — create a free cluster "
            "at cloud.qdrant.io and set them in backend_v3/.env"
        )
    return QDRANT_URL, QDRANT_API_KEY

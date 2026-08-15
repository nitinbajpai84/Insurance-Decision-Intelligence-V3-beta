"""
Encrypted credential storage for integration tokens.

Tokens are encrypted with Fernet (AES-128-CBC + HMAC) before they touch
the graph, so a Neo4j dump never yields usable OAuth credentials. The key
comes from INTEGRATION_ENCRYPTION_KEY and is never written anywhere.

Guarantees this module makes:
  - a plaintext token is never persisted, and never returned by any API
    surface (only `load_token`, called server-side, decrypts);
  - `revoke` deletes the stored material rather than flagging it, so a
    disconnect actually destroys the credential.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class EncryptionUnavailable(RuntimeError):
    """Raised when a token operation is attempted with no configured key.

    Deliberately fatal: storing a credential in plaintext because a key is
    missing would be worse than refusing to connect.
    """


def _fernet():
    from cryptography.fernet import Fernet

    from backend_v3.config import INTEGRATION_ENCRYPTION_KEY

    if not INTEGRATION_ENCRYPTION_KEY:
        raise EncryptionUnavailable(
            "INTEGRATION_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and set it in .env before connecting an OAuth provider."
        )
    try:
        return Fernet(INTEGRATION_ENCRYPTION_KEY.encode())
    except Exception as exc:  # malformed key
        raise EncryptionUnavailable(f"INTEGRATION_ENCRYPTION_KEY is not a valid Fernet key: {exc}") from None


def encryption_available() -> bool:
    try:
        _fernet()
        return True
    except EncryptionUnavailable:
        return False


def save_token(provider: str, account: str, token: dict[str, Any]) -> None:
    """Encrypt and persist an OAuth token bundle for a provider."""
    import json

    from backend_v3.graph_store.neo4j_client import run_write

    blob = _fernet().encrypt(json.dumps(token).encode()).decode()
    run_write(
        "MERGE (t:IntegrationToken {provider: $provider}) "
        "SET t.account = $account, t.ciphertext = $blob, t.updated_at = $now, "
        "    t.expires_at = $expires_at",
        {
            "provider": provider,
            "account": account,
            "blob": blob,
            "now": datetime.now(timezone.utc).isoformat(),
            "expires_at": token.get("expires_at"),
        },
    )


def load_token(provider: str) -> dict[str, Any] | None:
    """Decrypt a stored token. Server-side callers only."""
    import json

    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        "MATCH (t:IntegrationToken {provider: $provider}) RETURN t.ciphertext AS ciphertext",
        {"provider": provider},
    )
    if not rows or not rows[0].get("ciphertext"):
        return None
    return json.loads(_fernet().decrypt(rows[0]["ciphertext"].encode()).decode())


def revoke_token(provider: str) -> bool:
    """Destroy stored credentials. Returns True if something was removed."""
    from backend_v3.graph_store.neo4j_client import run_write

    rows = run_write(
        "MATCH (t:IntegrationToken {provider: $provider}) "
        "WITH t, count(t) AS found DELETE t RETURN found",
        {"provider": provider},
    )
    return bool(rows and rows[0].get("found"))


def has_token(provider: str) -> bool:
    from backend_v3.graph_store.neo4j_client import run_query

    rows = run_query(
        "MATCH (t:IntegrationToken {provider: $provider}) RETURN count(t) AS c",
        {"provider": provider},
    )
    return bool(rows and rows[0]["c"])

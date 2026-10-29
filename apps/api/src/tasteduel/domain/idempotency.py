"""Canonical typed-body signatures, scoped to session and operation.

Gameplay services use these signatures for durable reservations and safe retries.
"""

import hashlib
import json
from uuid import UUID


def request_signature(session_id: UUID, operation: str, body: dict) -> str:
    canonical = json.dumps(
        {"session_id": str(session_id), "operation": operation, "body": body},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

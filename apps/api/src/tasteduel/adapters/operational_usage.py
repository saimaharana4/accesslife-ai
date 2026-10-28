"""Private numeric admission evidence; no credentials, identities or game facts."""

import hashlib
import json
import logging
import re

from sqlalchemy import text


def admitted_count(engine, scope: str, bucket: str) -> int:
    if not re.fullmatch(r"[a-f0-9]{64}", scope) or bucket not in {
        "qloo-requests-day", "vertex-requests-day",
    }:
        raise ValueError("Invalid operational counter scope")
    with engine.connect() as db:
        db.execute(text("SET LOCAL statement_timeout = '1000ms'"))
        db.execute(text("SELECT set_config('app.usage_scope', :scope, true)"), {"scope": scope})
        value = db.execute(text("""SELECT used FROM tasteduel.usage_budgets
            WHERE scope_hash=:scope AND bucket=:bucket AND expires_at>clock_timestamp()"""),
                           {"scope": scope, "bucket": bucket}).scalar_one_or_none()
    if value is None:
        return 0
    if type(value) is not int or not 0 <= value <= 10000:
        raise ValueError("Invalid operational counter value")
    return value


def log_admission_snapshot(engine, *, qloo_scope: str, project: str, model: str):
    """One startup observation; reservations are upper bounds on dispatched calls.

    No counter reset or admission occurs. Operator-only Cloud Run logs receive
    just counts, never the per-key fingerprint or a browser-visible endpoint.
    """
    try:
        vertex_scope = hashlib.sha256(f"vertex:{project}:{model}".encode()).hexdigest()
        facts = {"event": "provider_admission_snapshot", "available": True,
                 "qloo_admitted_day": admitted_count(engine, qloo_scope, "qloo-requests-day"),
                 "vertex_admitted_day": admitted_count(engine, vertex_scope, "vertex-requests-day")}
    except Exception:
        facts = {"event": "provider_admission_snapshot", "available": False}
    logging.getLogger("uvicorn.error").info("%s", json.dumps(facts, separators=(",", ":")))

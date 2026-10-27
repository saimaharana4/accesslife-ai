"""Atomic short-lived admission facts, with no IP, query, entity or answer data."""

from __future__ import annotations

import asyncio
import hashlib

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


class UsageDenied(Exception):
    pass


def reserve(db, scope: str, bucket: str, *, limit: int, seconds: int, amount: int = 1):
    """Reserve before execution; lower instance limits win until the window expires.

    Caller commits even if the later operation fails. No refunded retries. Each
    scope/bucket has exactly one rolling record, replacing its prior window.
    """
    db.execute(text("SELECT set_config('app.usage_scope', :scope, true)"), {"scope": scope})
    value = db.execute(
        text("""INSERT INTO tasteduel.usage_budgets
        (scope_hash,bucket,window_start,expires_at,used,limit_value)
        VALUES (:scope,:bucket,
          to_timestamp(floor(extract(epoch from clock_timestamp())/:seconds)*:seconds),
          to_timestamp((floor(extract(epoch from clock_timestamp())/:seconds)+1)*:seconds),
          :amount,:limit)
        ON CONFLICT (scope_hash,bucket) DO UPDATE SET
          used=CASE WHEN usage_budgets.expires_at<=clock_timestamp() THEN :amount
                    ELSE usage_budgets.used+:amount END,
          limit_value=CASE WHEN usage_budgets.expires_at<=clock_timestamp() THEN :limit
                           ELSE least(usage_budgets.limit_value,:limit) END,
          window_start=CASE WHEN usage_budgets.expires_at<=clock_timestamp() THEN EXCLUDED.window_start
                            ELSE usage_budgets.window_start END,
          expires_at=CASE WHEN usage_budgets.expires_at<=clock_timestamp() THEN EXCLUDED.expires_at
                          ELSE usage_budgets.expires_at END
        WHERE CASE WHEN usage_budgets.expires_at<=clock_timestamp() THEN :amount
                   ELSE usage_budgets.used+:amount END <=
          CASE WHEN usage_budgets.expires_at<=clock_timestamp() THEN :limit
               ELSE least(usage_budgets.limit_value,:limit) END
        RETURNING used"""),
        {"scope": scope, "bucket": bucket, "amount": amount, "limit": limit, "seconds": seconds},
    ).scalar_one_or_none()
    if value is None:
        raise UsageDenied()


class ModelDailyBudget:
    """IAM project/model-wide daily conservative reservations, shared across APIs."""

    def __init__(self, engine, *, project, model, requests=100, tokens=1_000_000):
        self.engine = engine
        self.scope = hashlib.sha256(f"vertex:{project}:{model}".encode()).hexdigest()
        self.requests, self.tokens = requests, tokens

    def _reserve(self, tokens):
        try:
            with self.engine.begin() as db:
                db.execute(text("SET LOCAL lock_timeout = '500ms'"))
                db.execute(text("SET LOCAL statement_timeout = '1000ms'"))
                reserve(db, self.scope, "vertex-requests-day", limit=self.requests, seconds=86400)
                reserve(db, self.scope, "vertex-tokens-day", limit=self.tokens, seconds=86400, amount=tokens)
        except (UsageDenied, SQLAlchemyError):
            from tasteduel.ports.curator import ModelUnavailable

            raise ModelUnavailable("VERTEX_DAILY_BUDGET_UNAVAILABLE") from None

    async def admit(self, tokens):
        await asyncio.to_thread(self._reserve, tokens)

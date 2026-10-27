"""Private shared admission and bounded request policy; not a Qloo quota assertion."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import time
import math
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from tasteduel.ports.qloo import ProviderFailure, QlooPort, QlooResult
from tasteduel.adapters.usage_budget import UsageDenied, reserve


class AdmissionDenied(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AdmissionStore(Protocol):
    async def admit(self, scope: str) -> None: ...
    async def record(self, scope: str, *, failed: bool, auth: bool = False) -> None: ...


@dataclass
class RequestBudget:
    max_requests: int = 6
    deadline_seconds: float = 20
    used: int = 0
    dispatched: int = 0
    started_at: float = field(default_factory=time.monotonic)
    denied: str | None = None

    def __post_init__(self):
        if (
            type(self.max_requests) is not int
            or not 1 <= self.max_requests <= 6
            or not math.isfinite(self.deadline_seconds)
            or not 0 < self.deadline_seconds <= 20
        ):
            raise ValueError("Request envelope exceeds the configured hard ceiling")

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline_seconds - (time.monotonic() - self.started_at))


_budget: ContextVar[RequestBudget | None] = ContextVar("qloo_request_budget", default=None)


class PostgresAdmissionStore:
    """Atomic per-key controls shared by Taste Duel instances using this database.

    The scope is a key fingerprint, never the key. RLS also isolates unrelated keys.
    A legacy service that bypasses this store is not covered by these controls.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        requests_per_minute: int = 30,
        spacing_seconds: float = 0.2,
        requests_per_day: int = 1000,
    ):
        if (
            type(requests_per_minute) is not int
            or not 1 <= requests_per_minute <= 120
            or not math.isfinite(spacing_seconds)
            or not 0.05 <= spacing_seconds <= 1
            or type(requests_per_day) is not int
            or not 1 <= requests_per_day <= 10000
        ):
            raise ValueError("Invalid shared admission limits")
        self.engine = engine
        self.limit = requests_per_minute
        self.spacing = spacing_seconds
        self.daily_limit = requests_per_day

    def _transaction(self, scope, *, admit=False, failed=False, auth=False):
        import re

        if not isinstance(scope, str) or not re.fullmatch(r"[a-f0-9]{64}", scope):
            raise AdmissionDenied("INVALID_PROVIDER_SCOPE")
        denial = None
        wait_seconds = 0
        try:
            with self.engine.begin() as db:
                db.execute(text("SET LOCAL lock_timeout = '500ms'"))
                db.execute(text("SET LOCAL statement_timeout = '1000ms'"))
                db.execute(text("SELECT set_config('app.provider_scope', :scope, true)"), {"scope": scope})
                db.execute(
                    text("""INSERT INTO tasteduel.provider_controls(scope_hash)
                    VALUES (:scope) ON CONFLICT DO NOTHING"""),
                    {"scope": scope},
                )
                row = (
                    db.execute(
                        text("""SELECT *, clock_timestamp() AS now
                    FROM tasteduel.provider_controls WHERE scope_hash=:scope FOR UPDATE"""),
                        {"scope": scope},
                    )
                    .mappings()
                    .one()
                )
                now = row["now"]
                if admit:
                    if row["auth_blocked"]:
                        denial = "QLOO_AUTHENTICATION_FAILED"
                    elif row["open_until"] and row["open_until"] > now:
                        denial = "QLOO_CIRCUIT_OPEN"
                    elif row["next_allowed_at"] and row["next_allowed_at"] > now:
                        wait_seconds = min(1, (row["next_allowed_at"] - now).total_seconds())
                    else:
                        reset = (now - row["window_start"]).total_seconds() >= 60
                        used = 0 if reset else row["used"]
                        # A lower configured limit always wins; scale-out cannot raise it.
                        limit = min(self.limit, row["limit_value"])
                        if used >= limit:
                            denial = "QLOO_SHARED_RATE_LIMIT"
                        else:
                            reserve(db, scope, "qloo-requests-day", limit=self.daily_limit, seconds=86400)
                            db.execute(
                                text("""UPDATE tasteduel.provider_controls SET used=:used,
                                limit_value=:limit, window_start=CASE WHEN :reset THEN :now ELSE window_start END,
                                next_allowed_at=:now + (:spacing * interval '1 second') WHERE scope_hash=:scope"""),
                                {
                                    "scope": scope,
                                    "used": used + 1,
                                    "limit": limit,
                                    "reset": reset,
                                    "now": now,
                                    "spacing": self.spacing,
                                },
                            )
                else:
                    failures = row["failures"] + 1 if failed else 0
                    db.execute(
                        text("""UPDATE tasteduel.provider_controls SET failures=:failures,
                        auth_blocked=auth_blocked OR :auth,
                        open_until=CASE WHEN :failed AND :failures >= 3
                          THEN :now + interval '30 seconds' WHEN NOT :failed THEN NULL ELSE open_until END
                        WHERE scope_hash=:scope"""),
                        {
                            "scope": scope,
                            "failures": min(failures, 1000),
                            "failed": failed,
                            "auth": auth,
                            "now": now,
                        },
                    )
        except UsageDenied:
            raise AdmissionDenied("QLOO_DAILY_BUDGET_EXCEEDED") from None
        except SQLAlchemyError:
            raise AdmissionDenied("QLOO_ADMISSION_UNAVAILABLE") from None
        if denial:
            raise AdmissionDenied(denial)
        return wait_seconds

    async def admit(self, scope):
        for _ in range(6):
            wait = await asyncio.to_thread(self._transaction, scope, admit=True)
            if not wait:
                return
            await asyncio.sleep(wait)
        raise AdmissionDenied("QLOO_SHARED_RATE_LIMIT")

    async def record(self, scope, *, failed, auth=False):
        await asyncio.to_thread(self._transaction, scope, failed=failed, auth=auth)


class GuardedQlooPort:
    RETRYABLE = frozenset(
        {
            "QLOO_RATE_LIMITED",
            "MCP_DEADLINE",
            "MCP_PROCESS_EXIT",
            "MCP_STARTUP_TIMEOUT",
            "QLOO_UPSTREAM_UNAVAILABLE",
            "QLOO_HTTP_DEADLINE",
        }
    )

    def __init__(self, inner: QlooPort, store: AdmissionStore, scope: str):
        self.inner, self.store, self.scope = inner, store, scope

    @asynccontextmanager
    async def request_budget(self, *, max_requests=6, deadline_seconds=20):
        if _budget.get() is not None:
            raise ValueError("Nested budgets cannot reset the request envelope")
        budget = RequestBudget(max_requests, deadline_seconds)
        token = _budget.set(budget)
        try:
            yield budget
        finally:
            _budget.reset(token)

    async def reserve_upstream(self, operation: str):
        budget = _budget.get()
        if budget is None:
            raise AdmissionDenied("REQUEST_BUDGET_REQUIRED")
        if operation not in {"/search", "/entities", "/v2/insights"}:
            budget.denied = "QLOO_ENDPOINT_BLOCKED"
        elif budget.remaining_seconds <= 0:
            budget.denied = "QLOO_REQUEST_DEADLINE"
        elif budget.used >= budget.max_requests:
            budget.denied = "QLOO_REQUEST_BUDGET_EXCEEDED"
        if budget.denied:
            raise AdmissionDenied(budget.denied)
        # Increment before admission/dispatch. Failed/denied reservations never replenish it.
        budget.used += 1
        try:
            await self.store.admit(self.scope)
        except AdmissionDenied as failure:
            budget.denied = failure.code
            raise

    def note_dispatch(self, operation: str):
        """Observed transport dispatch, separately from conservative reservations."""
        budget = _budget.get()
        if (
            budget is None
            or operation not in {"/search", "/entities", "/v2/insights"}
            or budget.dispatched >= budget.used
        ):
            raise AdmissionDenied("QLOO_UNRESERVED_DISPATCH")
        budget.dispatched += 1

    async def resolve_seed(self, request):
        return await self._run(self.inner.resolve_seed, request)

    async def ranked_candidates(self, request):
        return await self._run(self.inner.ranked_candidates, request)

    async def _run(self, function, request):
        budget = _budget.get()
        if budget is None:
            return QlooResult("error", error=ProviderFailure("REQUEST_BUDGET_REQUIRED"))
        try:
            async with asyncio.timeout(budget.remaining_seconds):
                return await self._attempts(function, request, budget)
        except TimeoutError:
            return QlooResult("error", error=ProviderFailure("QLOO_REQUEST_DEADLINE"))

    async def _attempts(self, function, request, budget):
        for attempt in range(2):
            if budget.remaining_seconds <= 0:
                return QlooResult("error", error=ProviderFailure("QLOO_REQUEST_DEADLINE"))
            try:
                result = await function(request)
            except AdmissionDenied as denied:
                budget.denied = denied.code
                return QlooResult("error", error=ProviderFailure(denied.code))
            if budget.denied:
                return QlooResult("error", error=ProviderFailure(budget.denied))
            failure = result.error
            eligible = bool(failure and failure.retryable and failure.code in self.RETRYABLE)
            try:
                await self.store.record(
                    self.scope,
                    failed=eligible,
                    auth=bool(failure and failure.code == "QLOO_AUTHENTICATION_FAILED"),
                )
            except AdmissionDenied as denied:
                return QlooResult("error", error=ProviderFailure(denied.code))
            delay = max(0.25, failure.retry_after_seconds or 0) if failure else 0.25
            if (
                not eligible
                or attempt
                or budget.used >= budget.max_requests
                or delay > 2
                or budget.remaining_seconds < delay + 0.05
            ):
                return result
            await asyncio.sleep(delay)  # Never outrun Retry-After or retry after auth/contract failure.
        raise AssertionError("unreachable")

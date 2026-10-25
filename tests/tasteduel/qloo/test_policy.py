"""Observed reservations, retries and deadlines, without any provider traffic."""

import asyncio

import pytest

from tasteduel.adapters.qloo_policy import AdmissionDenied, GuardedQlooPort
from tasteduel.ports.qloo import ProviderFailure, QlooResult, ResolveSeedRequest

SCOPE = "e" * 64
REQUEST = ResolveSeedRequest("Invented Seed", "artist")


class ObservedStore:
    def __init__(self):
        self.admitted = []
        self.recorded = []
        self.auth_blocked = False

    async def admit(self, scope):
        if self.auth_blocked:
            raise AdmissionDenied("QLOO_AUTHENTICATION_FAILED")
        self.admitted.append(scope)

    async def record(self, scope, *, failed, auth=False):
        self.recorded.append((scope, failed, auth))
        self.auth_blocked |= auth


class ObservedProvider:
    def __init__(self, *, paths=("/search", "/entities"), results=(), delay=0):
        self.paths, self.results, self.delay = paths, list(results), delay
        self.calls, self.dispatched = 0, []
        self.guard = None

    async def resolve_seed(self, request):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        for path in self.paths:
            try:
                await self.guard.reserve_upstream(path)
            except AdmissionDenied:
                # The real managed child converts a denied reverse RPC into a safe failure.
                return QlooResult("error", error=ProviderFailure("SYNTHETIC_RESERVATION_DENIED"))
            self.dispatched.append(path)
        return self.results.pop(0) if self.results else QlooResult("empty")

    async def ranked_candidates(self, request):
        return await self.resolve_seed(request)


def setup(**kwargs):
    inner, store = ObservedProvider(**kwargs), ObservedStore()
    guard = GuardedQlooPort(inner, store, SCOPE)
    inner.guard = guard
    return guard, inner, store


async def test_budget_counts_internal_http_across_multiple_workflows_and_denies_seventh():
    guard, inner, store = setup()
    async with guard.request_budget() as budget:
        assert (await guard.resolve_seed(REQUEST)).status == "empty"
        assert (await guard.ranked_candidates(REQUEST)).status == "empty"
        assert (await guard.ranked_candidates(REQUEST)).status == "empty"
        result = await guard.ranked_candidates(REQUEST)
        assert result.error.code == "QLOO_REQUEST_BUDGET_EXCEEDED"
        assert budget.used == 6
        assert len(inner.dispatched) == len(store.admitted) == 6
        assert inner.calls == 4


async def test_missing_or_nested_envelope_cannot_reset_quota():
    guard, inner, _ = setup()
    result = await guard.resolve_seed(REQUEST)
    assert result.error.code == "REQUEST_BUDGET_REQUIRED" and inner.calls == 0
    async with guard.request_budget(max_requests=2) as budget:
        await guard.resolve_seed(REQUEST)
        with pytest.raises(ValueError, match="Nested"):
            async with guard.request_budget():
                pass
        assert budget.used == 2
        assert (await guard.resolve_seed(REQUEST)).error.code == "QLOO_REQUEST_BUDGET_EXCEEDED"
    assert (await guard.resolve_seed(REQUEST)).error.code == "REQUEST_BUDGET_REQUIRED"


@pytest.mark.parametrize("code", ["QLOO_RATE_LIMITED", "MCP_DEADLINE", "MCP_PROCESS_EXIT"])
async def test_one_eligible_retry_counts_every_internal_request(code):
    transient = QlooResult("error", error=ProviderFailure(code, True))
    guard, inner, store = setup(results=[transient, QlooResult("empty")])
    async with guard.request_budget() as budget:
        result = await guard.resolve_seed(REQUEST)
        assert result.status == "empty"
        assert inner.calls == 2 and budget.used == 4
        assert len(inner.dispatched) == len(store.admitted) == 4
    assert store.recorded == [(SCOPE, True, False), (SCOPE, False, False)]


async def test_retry_is_bounded_even_if_every_attempt_is_transient():
    failure = QlooResult("error", error=ProviderFailure("QLOO_RATE_LIMITED", True))
    guard, inner, _ = setup(paths=("/entities",), results=[failure, failure, failure])
    async with guard.request_budget() as budget:
        result = await guard.resolve_seed(REQUEST)
        assert result.error.code == "QLOO_RATE_LIMITED"
        assert inner.calls == budget.used == len(inner.dispatched) == 2


@pytest.mark.parametrize(
    "code,retryable",
    [
        ("QLOO_AUTHENTICATION_FAILED", False),
        ("QLOO_AUTHENTICATION_FAILED", True),
        ("PROVIDER_CONTRACT_INVALID", True),
        ("UNRECOGNIZED_TRANSIENT", True),
    ],
)
async def test_auth_and_unallowlisted_failures_never_trigger_a_fallback_or_retry(code, retryable):
    failure = QlooResult("error", error=ProviderFailure(code, retryable))
    guard, inner, _ = setup(results=[failure])
    async with guard.request_budget():
        result = await guard.resolve_seed(REQUEST)
    assert result.error.code == code
    assert inner.calls == 1 and len(inner.dispatched) == 2


async def test_auth_failure_blocks_later_admission_across_request_budgets():
    failure = QlooResult("error", error=ProviderFailure("QLOO_AUTHENTICATION_FAILED"))
    guard, inner, store = setup(results=[failure])
    async with guard.request_budget():
        await guard.resolve_seed(REQUEST)
    assert store.auth_blocked
    async with guard.request_budget():
        result = await guard.resolve_seed(REQUEST)
        assert result.error.code == "QLOO_AUTHENTICATION_FAILED"
    assert len(inner.dispatched) == 2


async def test_expired_deadline_skips_work_and_active_deadline_cancels_work():
    guard, inner, _ = setup()
    async with guard.request_budget() as budget:
        budget.started_at -= 21
        assert (await guard.resolve_seed(REQUEST)).error.code == "QLOO_REQUEST_DEADLINE"
        assert inner.calls == budget.used == 0
    guard, inner, _ = setup(delay=0.1)
    async with guard.request_budget(deadline_seconds=0.02) as budget:
        result = await guard.resolve_seed(REQUEST)
        assert result.error.code == "QLOO_REQUEST_DEADLINE"
        assert budget.used == 0 and not inner.dispatched


async def test_endpoint_denial_is_sticky_and_never_dispatches():
    guard, inner, _ = setup(paths=("/not-allowlisted",))
    async with guard.request_budget() as budget:
        result = await guard.resolve_seed(REQUEST)
        assert result.error.code == "QLOO_ENDPOINT_BLOCKED"
        assert budget.used == 0 and not inner.dispatched


async def test_budget_exhaustion_prevents_retry_instead_of_replenishing_requests():
    transient = QlooResult("error", error=ProviderFailure("QLOO_RATE_LIMITED", True))
    guard, inner, _ = setup(results=[transient])
    async with guard.request_budget(max_requests=2) as budget:
        result = await guard.resolve_seed(REQUEST)
        assert result.error.code == "QLOO_RATE_LIMITED"
        assert inner.calls == 1 and budget.used == 2

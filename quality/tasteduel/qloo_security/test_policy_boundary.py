"""Independent deadline and admission-bound checks; no database or live requests."""

import asyncio
import time

import pytest

from tasteduel.adapters.qloo_policy import GuardedQlooPort, PostgresAdmissionStore, RequestBudget
from tasteduel.ports.qloo import QlooResult


class ImmediateProvider:
    async def resolve_seed(self, request):
        return QlooResult("ok")


class SlowRecordStore:
    async def admit(self, scope):
        pass

    async def record(self, scope, *, failed, auth=False):
        await asyncio.sleep(0.2)


async def test_audit_recording_is_inside_total_request_deadline():
    port = GuardedQlooPort(ImmediateProvider(), SlowRecordStore(), "0" * 64)
    started = time.monotonic()
    async with port.request_budget(deadline_seconds=0.02):
        result = await port.resolve_seed(None)
    assert result.status == "error", "Do not return provider success after the declared request deadline"
    assert result.error.code == "QLOO_REQUEST_DEADLINE"
    assert time.monotonic() - started < 0.15


@pytest.mark.parametrize("count", [True, 1.5, float("nan"), float("inf")])
def test_request_count_is_an_integer_ceiling_not_a_fraction(count):
    with pytest.raises(ValueError):
        RequestBudget(max_requests=count)


@pytest.mark.parametrize("count", [True, 1.5, float("nan"), float("inf")])
def test_shared_rate_limit_is_a_valid_integer(count):
    with pytest.raises(ValueError):
        PostgresAdmissionStore(None, requests_per_minute=count)

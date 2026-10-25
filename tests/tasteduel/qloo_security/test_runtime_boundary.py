"""Secret-startup failure is bounded and sanitized without contacting any SDK."""

import time

import pytest

from tasteduel.api import provider_runtime as qloo_runtime
from tasteduel.config import Settings


async def test_slow_adc_secret_resolution_never_starts_a_child_or_blocks_startup(monkeypatch, caplog, capsys):
    process_starts = []

    def slow_synthetic_secret(_):
        time.sleep(0.2)
        return "synthetic-sensitive-value"

    def forbidden_process(**kwargs):
        process_starts.append(True)
        raise AssertionError("A timed-out secret lookup must not launch the MCP process")

    monkeypatch.setattr(qloo_runtime, "_secret_payload", slow_synthetic_secret)
    monkeypatch.setattr(qloo_runtime, "ManagedMcpProcess", forbidden_process)
    started = time.monotonic()
    with pytest.raises(qloo_runtime.ProviderStartupFailure) as caught:
        await qloo_runtime.build_qloo_runtime(Settings(qloo_startup_timeout=0.02), None)
    assert str(caught.value) == "QLOO_STARTUP_UNAVAILABLE"
    assert time.monotonic() - started < 0.15
    assert not process_starts
    captured = capsys.readouterr()
    assert "synthetic-sensitive-value" not in captured.out + captured.err + caplog.text

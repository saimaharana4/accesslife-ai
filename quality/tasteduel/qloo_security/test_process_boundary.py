"""Independent offline process/security checks with an adversarial child.

These tests prove framing, lifecycle and isolation, not live Qloo authorization.
"""

import asyncio
import contextvars
from pathlib import Path
import sys

import pytest

from tasteduel.adapters.qloo.process import ManagedMcpProcess, McpFailure


FAKE = Path(__file__).with_name("fake_mcp.py")
CONTRACT = Path(__file__).resolve().parents[3] / "runtime/qloo/discovered-contract.json"


def child(mode="normal", **kwargs):
    return ManagedMcpProcess(
        runner=FAKE,
        command=(sys.executable, str(FAKE), mode),
        contract_snapshot=CONTRACT,
        startup_timeout=2,
        call_timeout=kwargs.pop("call_timeout", 1),
        **kwargs,
    )


async def call(process, entity="fixture"):
    return await process.call_tool("qloo_describe", {"entity": entity, "type": "movie"})


@pytest.mark.parametrize(
    "bounds",
    [
        {"startup_timeout": float("inf")},
        {"startup_timeout": float("nan")},
        {"call_timeout": float("inf")},
        {"call_timeout": float("nan")},
        {"max_restarts": 1.5},
        {"max_restarts": 4},
    ],
)
def test_nonfinite_or_nonintegral_bounds_are_rejected(bounds):
    with pytest.raises(ValueError):
        ManagedMcpProcess(runner=FAKE, **bounds)


async def test_readiness_discovery_reuse_close_and_no_inherited_credentials(monkeypatch):
    for key in (
        "OPENAI_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "NODE_OPTIONS",
        "QLOO_BASE_URL",
        "QLOO_TRUSTED_BASE_URL",
        "HOME",
        "USERPROFILE",
        "QLOO_API_KEY",
    ):
        monkeypatch.setenv(key, "synthetic-sensitive-value")
    process = child(api_key="synthetic-test-only-key")
    try:
        assert not process.ready
        first = (await call(process, "first"))["structuredContent"]
        assert process.ready
        assert set(process.tool_schemas) == {"qloo_capabilities", "qloo_describe", "qloo_recommend"}
        second = (await call(process, "second"))["structuredContent"]
        assert first["pid"] == second["pid"]
        keys = set(first["environment_keys"])
        assert "QLOO_API_KEY" in keys
        assert not keys.intersection(
            {
                "OPENAI_API_KEY",
                "GOOGLE_APPLICATION_CREDENTIALS",
                "NODE_OPTIONS",
                "QLOO_BASE_URL",
                "QLOO_TRUSTED_BASE_URL",
                "HOME",
                "USERPROFILE",
            }
        )
        owned = process._process
    finally:
        await process.close()
    assert not process.ready
    assert owned.returncode is not None
    with pytest.raises(McpFailure, match="MCP_CLOSED"):
        await call(process)


async def test_stdout_only_framing_and_stderr_never_copied_to_logs(caplog, capsys):
    process = child("stderr")
    try:
        assert (await call(process))["structuredContent"]["synthetic"] is True
        # Allow the independently drained pipe to complete without arbitrary sleeps.
        await process.close()
        assert process.stderr_lines_discarded > 0
    finally:
        await process.close()
    captured = capsys.readouterr()
    assert "synthetic-sensitive-value" not in captured.out + captured.err + caplog.text


@pytest.mark.parametrize("mode", ["malformed", "oversized", "exit"])
async def test_terminal_protocol_or_process_failure_is_sanitized_and_child_reaped(mode):
    process = child(mode)
    await process.start()
    owned = process._process
    try:
        with pytest.raises(McpFailure) as caught:
            await call(process)
        assert "synthetic-sensitive-value" not in str(caught.value)
        assert not process.ready
        assert owned.returncode is not None, "A broken protocol must not leave the child running"
    finally:
        await process.close()


async def test_startup_timeout_reaps_child_and_respects_restart_bound():
    process = child("startup_hang", max_restarts=0)
    process.startup_timeout = 0.15
    try:
        with pytest.raises(McpFailure, match="MCP_STARTUP_TIMEOUT"):
            await process.start()
        assert process._process is None
        with pytest.raises(McpFailure, match="MCP_RESTART_LIMIT"):
            await process.start()
    finally:
        await process.close()


async def test_contract_mismatch_fails_before_any_workflow():
    process = child("bad_contract", max_restarts=0)
    try:
        with pytest.raises(McpFailure, match="MCP_CONTRACT_MISMATCH"):
            await process.start()
        assert not process.ready
        assert process._process is None
    finally:
        await process.close()


async def test_missing_packaged_contract_is_not_masked_by_repository_fallback(tmp_path):
    process = ManagedMcpProcess(
        runner=FAKE,
        command=(sys.executable, str(FAKE), "normal"),
        contract_snapshot=tmp_path / "absent-contract.json",
    )
    try:
        with pytest.raises(McpFailure, match="MCP_SCHEMA_SNAPSHOT_MISSING"):
            await process.start()
        assert process._process is None
        assert not process.ready
    finally:
        await process.close()


async def test_call_deadline_cancels_actual_child_and_restart_is_bounded():
    process = child("hang", call_timeout=0.15, max_restarts=1)
    try:
        await process.start()
        first = process._process
        with pytest.raises(McpFailure, match="MCP_DEADLINE"):
            await call(process)
        assert first.returncode is not None
        await process.start()
        assert process._process.pid != first.pid
        with pytest.raises(McpFailure, match="MCP_DEADLINE"):
            await call(process)
        with pytest.raises(McpFailure, match="MCP_RESTART_LIMIT"):
            await process.start()
    finally:
        await process.close()


async def test_cancel_active_workflow_reaps_child_and_drops_pending_response():
    process = child("hang")
    try:
        await process.start()
        owned = process._process
        task = asyncio.create_task(call(process))
        while not process._pending:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert owned.returncode is not None
        assert not process._pending
    finally:
        await process.close()


async def test_cancel_queued_caller_does_not_kill_another_active_call():
    process = child("concurrent")
    try:
        await process.start()
        first = asyncio.create_task(call(process, "first"))
        while not process._pending:
            await asyncio.sleep(0)
        second = asyncio.create_task(call(process, "second"))
        await asyncio.sleep(0)
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second
        assert (await first)["structuredContent"]["entity"] == "first"
        assert process.ready
    finally:
        await process.close()


async def test_concurrent_callers_get_only_their_own_result():
    process = child("concurrent")
    try:
        results = await asyncio.gather(call(process, "first"), call(process, "second"))
        assert [item["structuredContent"]["entity"] for item in results] == ["first", "second"]
        assert len({item["structuredContent"]["pid"] for item in results}) == 1
        assert results[0]["_tasteduel_http_statuses"] == (200,)
        assert results[1]["_tasteduel_http_statuses"] == (429,)
    finally:
        await process.close()


async def test_queued_deadline_does_not_cancel_another_active_workflow():
    process = child("concurrent")
    try:
        await process.start()
        first = asyncio.create_task(call(process, "first"))
        while not process._pending:
            await asyncio.sleep(0)
        process.call_timeout = 0.01
        with pytest.raises(McpFailure, match="MCP_DEADLINE"):
            await call(process, "second")
        assert (await first)["structuredContent"]["entity"] == "first"
        assert process.ready
    finally:
        await process.close()


async def test_unapproved_reverse_reservation_path_never_calls_budget_callback():
    seen = []

    async def reserve(path):
        seen.append(path)

    process = child("reserve_invalid_path", reserve_upstream=reserve)
    try:
        assert (await call(process))["structuredContent"] == {"dispatched": False}
        assert seen == []
    finally:
        await process.close()


async def test_reservation_is_fail_closed_and_context_is_callers_context():
    active_budget = contextvars.ContextVar("synthetic-budget")
    seen = []

    async def reserve(path):
        seen.append((path, active_budget.get()))

    process = child("reserve")
    try:
        # Reader is created outside the caller's context on purpose.
        await process.start()
        denied = (await call(process))["structuredContent"]
        assert denied == {"dispatched": False}
        active_budget.set("request-one")
        allowed = await process.call_tool(
            "qloo_describe", {"entity": "fixture", "type": "movie"}, reserve_upstream=reserve
        )
        assert allowed["structuredContent"] == {"dispatched": True}
        assert seen == [("/search", "request-one")]

        async def exhausted(_):
            raise RuntimeError("synthetic-sensitive-value")

        denied = await process.call_tool("qloo_describe", {"entity": "fixture"}, reserve_upstream=exhausted)
        assert denied["structuredContent"] == {"dispatched": False}
    finally:
        await process.close()


async def test_non_allowlisted_workflow_never_starts_child():
    process = child()
    try:
        with pytest.raises(McpFailure, match="MCP_WORKFLOW_BLOCKED"):
            await process.call_tool("qloo_rank", {})
        assert process._process is None
    finally:
        await process.close()

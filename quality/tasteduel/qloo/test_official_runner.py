"""Exercise the pinned official MCP child against a synthetic fetch, never the network."""

import asyncio
import json
from pathlib import Path

import pytest

from tasteduel.adapters.qloo.process import ManagedMcpProcess, McpFailure
from tasteduel.adapters.qloo.adapter import QlooMcpAdapter
from tasteduel.ports.qloo import ResolveSeedRequest

from .samples import SEED_ID

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "runtime/qloo/runner.mjs"
PRELOAD = Path(__file__).with_name("synthetic_fetch.mjs")


def make_process(tmp_path, mode="ok", *, reservation_allowed=True, api_key="synthetic-offline-key"):
    trace = tmp_path / "synthetic-observations.jsonl"
    wrapper = tmp_path / "offline-runner.mjs"
    wrapper.write_text(
        f"import {{installSyntheticFetch}} from {json.dumps(PRELOAD.as_uri())};\n"
        f"installSyntheticFetch({json.dumps(str(trace))}, {json.dumps(mode)});\n"
        f"await import({json.dumps(RUNNER.as_uri())});\n",
        encoding="utf-8",
    )
    reservations = []

    async def reserve(path):
        reservations.append(path)
        if not reservation_allowed:
            raise RuntimeError("SYNTHETIC_BUDGET_DENIAL")

    process = ManagedMcpProcess(
        runner=wrapper,
        api_key=api_key,
        reserve_upstream=reserve,
        startup_timeout=12,
        call_timeout=8,
        contract_snapshot=RUNNER.parent / "discovered-contract.json",
    )
    return process, trace, reservations


def observations(trace):
    return [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []


async def test_discovery_is_offline_and_actual_tool_schemas_reject_raw_api_parameters(tmp_path):
    process, trace, reservations = make_process(tmp_path)
    try:
        await process.start()
        assert process.ready
        assert observations(trace) == reservations == []
        assert set(process.tool_schemas) == {"qloo_capabilities", "qloo_describe", "qloo_recommend"}
        schema = process.tool_schemas["qloo_recommend"]
        assert schema["additionalProperties"] is False
        assert schema["properties"]["limit"]["maximum"] == 20
        assert "sort_by" not in schema["properties"]
        assert "filter.exists" not in schema["properties"]
        with pytest.raises(McpFailure):
            await process.call_tool("qloo_rank", {"options": []})
        for forbidden in ({"sort_by": "affinity"}, {"filter.exists": "properties.image"}, {"limit": 21}):
            with pytest.raises(McpFailure, match="MCP_ARGUMENTS_INVALID"):
                await process.call_tool(
                    "qloo_recommend",
                    {
                        "target_type": "movie",
                        "signals": [SEED_ID],
                        "limit": 20,
                        **forbidden,
                    },
                )
        assert observations(trace) == reservations == []
    finally:
        await process.close()


async def test_actual_official_workflows_construct_counted_get_auth_and_separate_queries(tmp_path):
    process, trace, reservations = make_process(tmp_path)
    try:
        described = await process.call_tool("qloo_describe", {"entity": "Invented Artist", "type": "artist"})
        assert described["structuredContent"]["status"] == "ok"
        recommended = await process.call_tool(
            "qloo_recommend",
            {
                "target_type": "movie",
                "signals": [SEED_ID],
                "limit": 20,
                "explain": True,
            },
        )
        assert recommended["structuredContent"]["status"] == "ok"
        rows = observations(trace)
        assert len(rows) == len(reservations)
        assert [row["path"] for row in rows] == reservations
        assert [row["path"] for row in rows] == ["/search", "/entities", "/entities", "/v2/insights"]
        assert all(row["method"] == "GET" and row["hasSyntheticKey"] for row in rows)
        assert all(row["origin"] == "https://hackathon.api.qloo.com" for row in rows)
        assert all(row["redirect"] == "manual" and row["hasAbortSignal"] for row in rows)
        assert rows[0]["query"] == {"query": "Invented Artist", "types": "urn:entity:artist", "take": "5"}
        assert rows[-1]["query"] == {
            "filter.type": "urn:entity:movie",
            "signal.interests.entities": SEED_ID,
            "take": "20",
            "feature.explainability": "true",
        }
        assert "sort_by" not in rows[-1]["query"]
        assert [row["affinity"] for row in recommended["structuredContent"]["results"]] == [0.8, 0.3]
        assert process.http_statuses == [200, 200]
    finally:
        await process.close()


@pytest.mark.parametrize("mode,status", [("auth", 401), ("rate_limit", 429), ("malformed", 200)])
async def test_official_child_failure_has_one_attempt_and_no_alternate_host(tmp_path, mode, status):
    process, trace, reservations = make_process(tmp_path, mode)
    try:
        result = await process.call_tool("qloo_describe", {"entity": SEED_ID, "type": "artist"})
        assert result.get("isError") is True or result.get("structuredContent", {}).get("status") == "error"
        assert len(observations(trace)) == len(reservations) == 1
        assert process.http_statuses == [status]
        assert observations(trace)[0]["origin"] == "https://hackathon.api.qloo.com"
    finally:
        await process.close()


async def test_reservation_denial_prevents_even_synthetic_http_dispatch(tmp_path):
    process, trace, reservations = make_process(tmp_path, reservation_allowed=False)
    try:
        result = await process.call_tool("qloo_describe", {"entity": SEED_ID, "type": "artist"})
        assert result.get("isError") is True or result.get("structuredContent", {}).get("status") == "error"
        assert reservations == ["/entities"]
        assert observations(trace) == []
    finally:
        await process.close()


async def test_deadline_reaps_official_child_without_synthetic_retry(tmp_path):
    process, trace, reservations = make_process(tmp_path, "timeout")
    process.call_timeout = 0.3
    try:
        await process.start()
        with pytest.raises(McpFailure, match="MCP_DEADLINE"):
            await process.call_tool("qloo_describe", {"entity": SEED_ID, "type": "artist"})
        assert not process.ready
        assert len(observations(trace)) == len(reservations) == 1
    finally:
        await process.close()


async def test_real_harness_ambiguity_reaches_typed_selection_without_hydration_or_recommendation(tmp_path):
    process, trace, reservations = make_process(tmp_path, "ambiguous")
    try:
        result = await QlooMcpAdapter(process).resolve_seed(ResolveSeedRequest("Invented Artist", "artist"))
        assert result.status == "needs_input"
        assert not result.entities and not result.candidates
        assert len(result.issues) == 1 and len(result.issues[0].choices) == 2
        assert all(choice.domain == "artist" for choice in result.issues[0].choices)
        assert reservations == ["/search"]
        assert [row["path"] for row in observations(trace)] == ["/search"]
    finally:
        await process.close()


async def test_missing_key_allows_offline_discovery_but_never_dispatches_a_data_request(tmp_path):
    process, trace, reservations = make_process(tmp_path, api_key=None)
    try:
        await process.start()
        assert process.ready
        result = await QlooMcpAdapter(process).resolve_seed(ResolveSeedRequest("Invented Artist", "artist"))
        assert result.status == "error"
        assert not result.entities and not result.candidates
        assert observations(trace) == reservations == []
    finally:
        await process.close()


async def test_concurrent_calls_return_their_own_atomic_http_status_snapshot(tmp_path):
    process, trace, reservations = make_process(tmp_path, "auth_once")
    try:
        first, second = await asyncio.gather(
            process.call_tool("qloo_describe", {"entity": SEED_ID, "type": "artist"}),
            process.call_tool("qloo_describe", {"entity": SEED_ID, "type": "artist"}),
        )
        assert first["_tasteduel_http_statuses"] == (401,)
        assert second["_tasteduel_http_statuses"] == (200,)
        assert process.http_statuses == [200]
        assert len(observations(trace)) == len(reservations) == 2
        assert first["structuredContent"]["status"] == "error"
        assert second["structuredContent"]["status"] == "ok"
    finally:
        await process.close()

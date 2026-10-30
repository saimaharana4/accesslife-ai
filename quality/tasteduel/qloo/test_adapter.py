"""Observe typed-port requests and failure classification without a real credential."""

from uuid import UUID

import pytest

from tasteduel.adapters.qloo.adapter import QlooMcpAdapter
from tasteduel.adapters.qloo.process import McpFailure
from tasteduel.ports.qloo import RankedCandidatesRequest, ResolveSeedRequest

from .samples import SEED_ID, envelope


class RecordedChild:
    def __init__(self, result=None, *, http=(), failure=None):
        self.result = result if result is not None else {"structuredContent": envelope()}
        self.http_statuses = list(http)
        self.result["_tasteduel_http_statuses"] = tuple(http)
        self.failure = failure
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.failure:
            raise McpFailure(self.failure)
        return self.result


async def test_resolve_uses_only_typed_describe_and_preserves_ambiguity():
    child = RecordedChild({"structuredContent": envelope("needs_input", operation="describe")})
    result = await QlooMcpAdapter(child).resolve_seed(ResolveSeedRequest("  Invented Name  ", "movie"))
    assert child.calls == [("qloo_describe", {"entity": "Invented Name", "type": "movie"})]
    assert result.status == "needs_input" and not result.entities
    assert len(result.issues[0].choices) == 2


async def test_rank_uses_resolved_uuid_and_only_supported_workflow_parameters():
    child = RecordedChild()
    result = await QlooMcpAdapter(child).ranked_candidates(
        RankedCandidatesRequest(UUID(SEED_ID), "artist", "movie")
    )
    assert child.calls == [
        (
            "qloo_recommend",
            {
                "target_type": "movie",
                "signals": [SEED_ID],
                "limit": 20,
                "explain": True,
            },
        )
    ]
    assert result.evidence.harness_version == "0.1.26"
    assert result.evidence.ordering_verified is False
    assert not hasattr(result, "structuredContent")
    assert not hasattr(result, "provenance")


@pytest.mark.parametrize(
    "seed_request",
    [
        ResolveSeedRequest("", "movie"),
        ResolveSeedRequest(" " * 2, "artist"),
        ResolveSeedRequest("x" * 201, "movie"),
        ResolveSeedRequest("Invented", "book"),
    ],
)
async def test_unsupported_seed_does_not_reach_child(seed_request):
    child = RecordedChild()
    result = await QlooMcpAdapter(child).resolve_seed(seed_request)
    assert result.status == "error" and not child.calls


@pytest.mark.parametrize("limit", [0, 21, True, "20"])
async def test_unsupported_ranking_limit_does_not_reach_child(limit):
    child = RecordedChild()
    result = await QlooMcpAdapter(child).ranked_candidates(
        RankedCandidatesRequest(UUID(SEED_ID), "artist", "movie", limit)
    )
    assert result.status == "error" and not child.calls


@pytest.mark.parametrize(
    "http,code,retryable",
    [
        ([401], "QLOO_AUTHENTICATION_FAILED", False),
        ([403], "QLOO_AUTHENTICATION_FAILED", False),
        ([429], "QLOO_RATE_LIMITED", True),
        ([401, 429], "QLOO_AUTHENTICATION_FAILED", False),
        ([500], "QLOO_UPSTREAM_UNAVAILABLE", True),
        ([502], "QLOO_UPSTREAM_UNAVAILABLE", True),
        ([503], "QLOO_UPSTREAM_UNAVAILABLE", True),
        ([504], "QLOO_UPSTREAM_UNAVAILABLE", True),
    ],
)
async def test_http_auth_and_rate_failures_override_untrusted_success(http, code, retryable):
    child = RecordedChild(http=http)
    result = await QlooMcpAdapter(child).ranked_candidates(
        RankedCandidatesRequest(UUID(SEED_ID), "artist", "movie")
    )
    assert result.status == "error" and result.error.code == code
    assert result.error.retryable is retryable
    assert result.candidates == ()
    assert len(child.calls) == 1


@pytest.mark.parametrize(
    "code,retryable",
    [
        ("MCP_DEADLINE", True),
        ("MCP_PROCESS_EXIT", True),
        ("MCP_STARTUP_TIMEOUT", True),
        ("MCP_CONTRACT_MISMATCH", False),
    ],
)
async def test_process_errors_have_safe_failure_values_without_alternate_provider(code, retryable):
    child = RecordedChild(failure=code)
    result = await QlooMcpAdapter(child).ranked_candidates(
        RankedCandidatesRequest(UUID(SEED_ID), "artist", "movie")
    )
    assert result.status == "error" and result.error.code == code
    assert result.error.retryable is retryable
    assert not result.candidates and len(child.calls) == 1


async def test_query_fingerprint_is_stable_but_changes_with_request_context():
    child = RecordedChild()
    adapter = QlooMcpAdapter(child)
    first = await adapter.ranked_candidates(RankedCandidatesRequest(UUID(SEED_ID), "artist", "movie", 20))
    repeat = await adapter.ranked_candidates(RankedCandidatesRequest(UUID(SEED_ID), "artist", "movie", 20))
    changed = await adapter.ranked_candidates(RankedCandidatesRequest(UUID(SEED_ID), "artist", "movie", 19))
    assert first.evidence.context_hash == repeat.evidence.context_hash
    assert first.evidence.context_hash != changed.evidence.context_hash


async def test_classification_reads_per_call_metadata_not_mutable_process_status():
    child = RecordedChild(http=(200,))
    child.http_statuses = [401]
    result = await QlooMcpAdapter(child).ranked_candidates(
        RankedCandidatesRequest(UUID(SEED_ID), "artist", "movie")
    )
    assert result.status == "ok" and len(result.candidates) == 2


async def test_auth_metadata_is_not_masked_by_malformed_structured_content():
    child = RecordedChild({"content": []}, http=(401,))
    result = await QlooMcpAdapter(child).resolve_seed(ResolveSeedRequest("Invented", "artist"))
    assert result.status == "error" and result.error.code == "QLOO_AUTHENTICATION_FAILED"
    assert result.error.retryable is False

"""No live payloads or network: validate exact GET contracts with MockTransport."""

from copy import deepcopy
from dataclasses import replace
import json
from uuid import UUID

import httpx
import pytest

from tasteduel.adapters.qloo.ranked_http import QlooRankedHttpAdapter, normalize_ranked_http
from tasteduel.adapters.qloo_policy import AdmissionDenied, GuardedQlooPort
from tasteduel.ports.qloo import QlooResult, RankedCandidatesRequest, ResolveSeedRequest, ranked_context_hash

REQUEST = RankedCandidatesRequest(UUID(int=999), "artist", "movie", 20)


def row(index=0, **changes):
    value = {
        "entity_id": str(UUID(int=1000 + index)),
        "name": f"Synthetic invented movie {index}",
        "types": ["urn:entity", "urn:entity:movie"],
        "query": {"affinity": 20.0 - index},
    }
    value.update(changes)
    return value


def payload(*rows):
    return {"success": True, "results": {"entities": list(rows or (row(), row(1)))}}


class ResolutionOnly:
    def __init__(self):
        self.requests = []

    async def resolve_seed(self, request):
        self.requests.append(request)
        return QlooResult("needs_input")

    async def ranked_candidates(self, request):
        raise AssertionError("No silent fallback to MCP ranking is allowed")


class Store:
    def __init__(self, denial=None):
        self.admitted = 0
        self.denial = denial

    async def admit(self, scope):
        if self.denial:
            raise AdmissionDenied(self.denial)
        self.admitted += 1

    async def record(self, scope, *, failed, auth=False):
        if auth:
            self.denial = "QLOO_AUTHENTICATION_FAILED"


def setup(handler, *, key="synthetic-not-a-real-key", denial=None):
    resolution, store = ResolutionOnly(), Store(denial)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    # No call happens until every callback is bound to the real shared guard.
    adapter = QlooRankedHttpAdapter(
        resolution, api_key=key, reserve_upstream=None, note_dispatch=None, client=client
    )
    guard = GuardedQlooPort(adapter, store, "d" * 64)
    adapter._reserve, adapter._dispatch = guard.reserve_upstream, guard.note_dispatch
    return guard, adapter, client, resolution, store


async def test_exact_get_event_host_auth_and_parameter_construction():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payload(), request=request)

    guard, _, client, _, store = setup(handler)
    async with client:
        async with guard.request_budget() as budget:
            result = await guard.ranked_candidates(REQUEST)
    assert result.status == "ok"
    assert len(requests) == store.admitted == budget.dispatched == budget.used == 1
    request = requests[0]
    assert request.method == "GET"
    assert request.url.scheme == "https" and request.url.host == "hackathon.api.qloo.com"
    assert request.url.path == "/v2/insights"
    assert dict(request.url.params) == {
        "filter.type": "urn:entity:movie",
        "signal.interests.entities": str(REQUEST.seed_id),
        "take": "20",
        "feature.explainability": "true",
        "sort_by": "affinity",
    }
    assert request.headers["X-Api-Key"] == "synthetic-not-a-real-key"
    assert not request.content and "synthetic-not-a-real-key" not in str(request.url)
    assert result.evidence.transport == "http_ranked"
    assert result.evidence.context_hash == ranked_context_hash(REQUEST, transport="http_ranked")
    assert result.evidence.context_hash != ranked_context_hash(REQUEST)
    assert result.evidence.score_field == "query.affinity" and result.evidence.ordering_verified


async def test_redirect_never_sends_key_to_another_host_even_when_client_follows_by_default():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://synthetic-attacker.invalid/steal"})

    guard, _, client, _, _ = setup(handler)
    client.follow_redirects = True
    async with client, guard.request_budget():
        result = await guard.ranked_candidates(REQUEST)
    assert result.error.code == "QLOO_HTTP_REJECTED"
    assert len(requests) == 1 and requests[0].url.host == "hackathon.api.qloo.com"


async def test_no_reservation_or_missing_credential_means_no_http_request():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payload())

    guard, _, client, _, _ = setup(handler)
    async with client:
        result = await guard.ranked_candidates(REQUEST)
    assert result.error.code == "REQUEST_BUDGET_REQUIRED" and not requests
    guard, _, client, _, _ = setup(handler, key="")
    async with client, guard.request_budget() as budget:
        result = await guard.ranked_candidates(REQUEST)
    assert result.error.code == "QLOO_CREDENTIAL_UNAVAILABLE"
    assert budget.used == budget.dispatched == 0 and not requests


async def test_shared_denial_is_safe_and_sticky_and_does_not_send_http():
    def handler(request):
        raise AssertionError("Admission denied: no dispatch allowed")

    guard, _, client, _, _ = setup(handler, denial="QLOO_SHARED_RATE_LIMIT")
    async with client, guard.request_budget() as budget:
        result = await guard.ranked_candidates(REQUEST)
    assert result.error.code == "QLOO_SHARED_RATE_LIMIT"
    assert budget.used == 1 and budget.dispatched == 0


async def test_resolution_remains_official_mcp_and_is_not_replaced_by_raw_search():
    def handler(request):
        raise AssertionError("Seed resolution must remain the pinned MCP operation")

    _, adapter, client, resolution, _ = setup(handler)
    request = ResolveSeedRequest("Synthetic ambiguous title", "movie")
    async with client:
        result = await adapter.resolve_seed(request)
    assert result.status == "needs_input" and resolution.requests == [request]


@pytest.mark.parametrize(
    "changes",
    [
        {"seed_id": "not-a-uuid"},
        {"seed_domain": "book"},
        {"target_domain": "person"},
        {"limit": True},
        {"limit": 0},
        {"limit": 21},
        {"limit": 3.5},
    ],
)
async def test_invalid_requests_fail_before_reservation_or_http(changes):
    def handler(request):
        raise AssertionError("Invalid request was sent")

    guard, _, client, _, _ = setup(handler)
    async with client, guard.request_budget() as budget:
        result = await guard.ranked_candidates(replace(REQUEST, **changes))
    assert result.error.code == "INVALID_RANKING_REQUEST"
    assert budget.used == budget.dispatched == 0


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"success": 1, "results": {"entities": []}},
        {"success": True, "results": []},
        {"success": True, "results": {"entities": {}}},
        {"success": True, "results": {"entities": [None]}},
        payload(row(entity_id="invalid-uuid")),
        payload(row(name=None)),
        payload(row(name=" ")),
        payload(row(name="a" * 201)),
        payload(row(query=None)),
        payload(row(query={})),
        payload(row(query={"affinity": True})),
        payload(row(query={"affinity": "0.1"})),
        payload(row(query={"affinity": float("nan")})),
        payload(row(query={"affinity": float("inf")})),
        payload(row(query={"affinity": 10**1000})),
        payload(row(affinity=10.0)),
        payload(row(affinity="20")),
        payload(row(types=None)),
        payload(row(types=["urn:entity:artist"])),
        payload(row(types=["urn:entity:movie", "urn:entity:artist"])),
        payload(row(types=[42])),
        payload(row(types=[])),
        payload(row(type="urn:entity:artist")),
        payload(row(type=0)),
        payload(row(type=False)),
        payload(row(subtype=[])),
        payload(row(), row()),
        payload(row(query={"affinity": 1}), row(1, query={"affinity": 2})),
        payload(*[row(i) for i in range(21)]),
    ],
)
def test_malformed_conflicting_and_contradictory_response_is_never_promoted(value):
    result = normalize_ranked_http(value, REQUEST)
    assert result.status == "error" and result.error.code == "QLOO_CONTRACT_INVALID"
    assert result.evidence is None and not result.candidates


def test_equal_scores_are_preserved_for_deterministic_tie_rejection_not_arbitrary_winners():
    result = normalize_ranked_http(payload(row(), row(1, query={"affinity": 20.0})), REQUEST)
    assert result.status == "ok"
    assert result.candidates[0].affinity == result.candidates[1].affinity


def test_empty_is_honest_and_missing_image_explanation_uses_supported_fallback():
    assert normalize_ranked_http({"success": True, "results": {"entities": []}}, REQUEST).status == "empty"
    result = normalize_ranked_http(payload(row()), REQUEST)
    assert result.status == "ok"
    assert result.candidates[0].entity.image_url is None
    assert not result.candidates[0].entity.image_rights_verified
    assert result.candidates[0].explanation is None and not result.warnings


def test_explanation_presence_is_warned_but_unreviewed_causal_text_never_survives():
    marker = "SYNTHETIC_UNSUPPORTED_PSYCHOLOGICAL_REASON"
    result = normalize_ranked_http(
        payload(row(query={"affinity": 20.0, "explainability": {"story": marker}})), REQUEST
    )
    assert result.status == "ok" and result.warnings == ("UNREVIEWED_EXPLANATION_PRESENT",)
    assert result.candidates[0].explanation is None and marker not in repr(result)


@pytest.mark.parametrize(
    "url", ["https://images.synthetic.invalid/cover.jpg", "http://images.invalid/a", "https://127.0.0.1/a"]
)
def test_image_metadata_is_never_mistaken_for_rights_or_fetched(url):
    result = normalize_ranked_http(payload(row(properties={"image": {"url": url}})), REQUEST)
    assert result.status == "ok"
    assert result.candidates[0].entity.image_url == (url if url.startswith("https://images.") else None)
    assert not result.candidates[0].entity.image_rights_verified


@pytest.mark.parametrize("status", [401, 403, 404, 500, 503])
async def test_http_failure_classification_and_no_silent_transport_fallback(status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"private": "synthetic-raw-error-marker"})

    guard, _, client, _, _ = setup(handler)
    async with client, guard.request_budget() as budget:
        result = await guard.ranked_candidates(REQUEST)
    assert result.status == "error"
    expected = (
        "QLOO_AUTHENTICATION_FAILED"
        if status in (401, 403)
        else ("QLOO_UPSTREAM_UNAVAILABLE" if status >= 500 else "QLOO_HTTP_REJECTED")
    )
    assert result.error.code == expected
    assert len(requests) == budget.dispatched == (2 if status >= 500 else 1)
    assert "synthetic-raw-error-marker" not in repr(result)


@pytest.mark.parametrize(
    "retry,expected",
    [("3", 3.0), ("200", 60.0), ("-2", 0.0), ("invalid", None), ("NaN", None), ("Infinity", None)],
)
async def test_rate_limit_exposes_bounded_retry_after_without_retrying_long_delays(retry, expected):
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": retry})

    _, adapter, client, _, _ = setup(handler)
    # Direct adapter test isolates its exact response classification from the outer retry policy.
    adapter._reserve = lambda operation: no_op()
    adapter._dispatch = lambda operation: None
    async with client:
        result = await adapter.ranked_candidates(REQUEST)
    assert result.error.code == "QLOO_RATE_LIMITED" and result.error.retryable
    assert result.error.retry_after_seconds == expected


async def no_op():
    pass


@pytest.mark.parametrize(
    "exception", [httpx.ReadTimeout("synthetic-private-url"), httpx.ConnectError("synthetic-private-url")]
)
async def test_transport_failures_are_typed_redacted_and_bounded(exception):
    def handler(request):
        raise exception

    guard, _, client, _, _ = setup(handler)
    async with client, guard.request_budget() as budget:
        result = await guard.ranked_candidates(REQUEST)
    assert result.status == "error" and result.error.retryable
    assert result.error.code in {"QLOO_HTTP_DEADLINE", "QLOO_UPSTREAM_UNAVAILABLE"}
    assert 1 <= budget.dispatched <= 2 and "synthetic-private-url" not in repr(result)


@pytest.mark.parametrize(
    "body",
    [b"not-json", b"\xff", b"a" * 2_000_001, b"[" * 1500 + b"0" + b"]" * 1500],
    ids=["invalid-json", "invalid-utf8", "over-2mb", "too-deep-json"],
)
async def test_malformed_and_oversized_bodies_do_not_escape_as_provider_json(body):
    guard, _, client, _, _ = setup(lambda request: httpx.Response(200, content=body))
    async with client, guard.request_budget():
        result = await guard.ranked_candidates(REQUEST)
    assert result.status == "error"
    assert result.error.code == (
        "QLOO_RESPONSE_TOO_LARGE" if len(body) > 2_000_000 else "QLOO_CONTRACT_INVALID"
    )


def test_raw_score_units_and_unknown_external_metadata_are_not_reinterpreted():
    original = payload(row(query={"affinity": 1234.5}, arbitrary="synthetic-unused-private"))
    before = deepcopy(original)
    result = normalize_ranked_http(original, REQUEST)
    assert result.candidates[0].affinity == 1234.5
    assert result.evidence.ordering_verified and "synthetic-unused-private" not in repr(result)
    assert original == before
    assert not hasattr(result, "raw_payload")
    assert "percent" not in json.dumps(result.evidence.__dict__, default=str).lower()

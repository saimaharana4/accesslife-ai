"""Explicit harness-gap typed search, using invented provider metadata only."""

from copy import deepcopy

import httpx
import pytest

from tasteduel.adapters.qloo.ranked_http import normalize_typed_search
from tasteduel.ports.qloo import ResolveSeedRequest

from .test_http_contract import row, setup

REQUEST = ResolveSeedRequest("Synthetic invented movie 0", "movie")


def body(*rows):
    return {"success": True, "results": list(rows or (row(),))}


async def test_typed_search_exact_get_and_actual_type_evidence_no_ranking():
    captured = []

    def handle(request):
        captured.append(request)
        return httpx.Response(200, json=body(), request=request)

    guard, adapter, client, resolution, store = setup(handle)
    adapter.typed_search = True
    async with client, guard.request_budget() as budget:
        result = await guard.resolve_seed(REQUEST)
    assert result.status == "ok"
    assert result.entities[0].domain == "movie"
    assert result.evidence is None and result.candidates == ()
    assert resolution.requests == []
    assert budget.used == budget.dispatched == store.admitted == 1
    assert len(captured) == 1
    request = captured[0]
    assert request.method == "GET"
    assert str(request.url.copy_with(query=None)) == "https://hackathon.api.qloo.com/search"
    assert dict(request.url.params) == {"query": REQUEST.query, "types": "urn:entity:movie", "take": "5"}
    assert request.headers["x-api-key"] == "synthetic-not-a-real-key"


def test_ambiguity_never_selects_first_or_returns_ranking():
    result = normalize_typed_search(body(row(), row(1, name=REQUEST.query)), REQUEST)
    assert result.status == "needs_input"
    assert len(result.issues[0].choices) == 2
    assert result.entities == result.candidates == () and result.evidence is None


@pytest.mark.parametrize(
    "change",
    [
        {"types": []},
        {"types": ["urn:entity:artist"]},
        {"types": "movie"},
        {"type": "urn:entity:artist"},
        {"subtype": False},
        {"entity_id": "invalid"},
        {"name": ""},
        {"name": "x" * 201},
        {"types": ["urn:entity:movie", None]},
    ],
)
def test_missing_or_contradictory_evidence_cannot_be_inferred(change):
    result = normalize_typed_search(body(row(**change)), REQUEST)
    assert result.status == "error"
    assert result.entities == ()


def test_missing_success_empty_duplicate_and_partial_name():
    assert normalize_typed_search({"results": []}, REQUEST).status == "empty"
    assert normalize_typed_search({"success": False, "results": []}, REQUEST).status == "error"
    assert normalize_typed_search({"success": True, "results": []}, REQUEST).status == "empty"
    assert normalize_typed_search(body(row(), deepcopy(row())), REQUEST).status == "error"
    result = normalize_typed_search(body(row(name="Different title")), REQUEST)
    assert result.status == "needs_input" and len(result.issues[0].choices) == 1

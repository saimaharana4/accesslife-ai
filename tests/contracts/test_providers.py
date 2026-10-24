import httpx
import pytest
from accesslife.adapters.taste import QlooTaste, ProviderError, DevelopmentTaste
from accesslife.adapters.catalogue import PLACES
from accesslife.domain.models import Explanation


async def test_qloo_requests_use_hackathon_get_header_and_valid_params():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"results": [{"entity_id": "seed", "name": "Jazz"}]})

    provider = QlooTaste("synthetic-test-key", transport=httpx.MockTransport(handler))
    assert await provider.resolve_interests(["Jazz"]) == ["seed"]
    await provider.insights({"filter.type": "urn:entity:place", "signal.interests.entities": "seed"})
    assert [r.url.path for r in calls] == ["/search", "/v2/insights"]
    assert all(
        r.method == "GET"
        and r.url.host == "hackathon.api.qloo.com"
        and r.headers["X-Api-Key"] == "synthetic-test-key"
        and "authorization" not in r.headers
        for r in calls
    )
    with pytest.raises(ProviderError, match="unsupported_qloo_parameters"):
        await provider.insights({"filter.type": "urn:entity:place", "wheelchair": "yes"})


async def test_qloo_auth_does_not_retry_and_ambiguous_seeds_stay_unresolved():
    calls = []

    def denied(request):
        calls.append(request)
        return httpx.Response(401)

    with pytest.raises(ProviderError, match="authentication"):
        await QlooTaste("synthetic", transport=httpx.MockTransport(denied)).resolve_interests(["art"])
    assert len(calls) == 1
    transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={"results": [{"name": "Jazz", "entity_id": "one"}, {"name": "Jazz", "entity_id": "two"}]},
        )
    )
    assert await QlooTaste("synthetic", transport=transport).resolve_interests(["Jazz"]) == []


async def test_qloo_full_ranking_preserves_unmapped_candidates():
    place = PLACES[0]
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/v2/tags":
            return httpx.Response(200, json={"results": {"tags": []}})
        if request.url.path == "/v2/insights":
            assert request.url.params["filter.results.entities"] == "synthetic-place"
            return httpx.Response(
                200,
                json={
                    "results": {"entities": [{"entity_id": "synthetic-place", "query": {"affinity": 0.7}}]}
                },
            )
        if request.url.params["query"] == "Jazz":
            return httpx.Response(200, json={"results": [{"entity_id": "synthetic-seed", "name": "Jazz"}]})
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "entity_id": "synthetic-place",
                        "name": place.name,
                        "location": {"lat": place.latitude, "lon": place.longitude},
                    }
                ]
                if request.url.params["query"] == place.name
                else []
            },
        )

    result = await QlooTaste("synthetic", transport=httpx.MockTransport(handler)).rank_candidates(
        PLACES[:2], ["entity:Jazz"]
    )
    assert result["live"] and result["scores"] == {place.id: 0.7}
    assert result["unmapped"] == [PLACES[1].id]
    assert set(result["order"]) == {p.id for p in PLACES[:2]}


@pytest.mark.parametrize("payload", [{"results": {}}, {"results": ["bad"]}, [], {"success": False}])
async def test_qloo_malformed_search_is_safe(payload):
    provider = QlooTaste(
        "synthetic", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    )
    with pytest.raises(ProviderError, match="qloo_malformed"):
        await provider.resolve_interests(["Jazz"])


async def test_development_taste_uses_explicit_categories_without_qloo_scores():
    places = PLACES[:3]
    result = await DevelopmentTaste().rank_candidates(places, ["architecture"])
    assert result["provider"] == "development" and not result["live"] and result["scores"] == {}
    assert result["order"][0] == "tate-modern"
    assert set(result["order"]) == {p.id for p in places}


async def test_qloo_rate_limit_is_retryable_and_bounded():
    calls = []

    def limited(request):
        calls.append(request)
        return httpx.Response(429)

    with pytest.raises(ProviderError) as exc:
        await QlooTaste("synthetic", transport=httpx.MockTransport(limited)).resolve_interests(["Jazz"])
    assert exc.value.retryable and len(calls) == 2


async def test_generation_fallback_only_for_transient_failures(monkeypatch):
    from accesslife.adapters.generation import generate, ModelGeneration
    from accesslife.config import settings

    cfg = settings()
    monkeypatch.setattr(cfg, "generation_provider", "vertex_ai")
    monkeypatch.setattr(cfg, "groq_api_key", "synthetic")
    calls = []

    async def transient(self, prompt, schema):
        calls.append(self.provider)
        if self.provider == "vertex_ai":
            raise ProviderError("temporary", True)
        return Explanation(
            summary="This is a provisional cultural outing. Review the venue evidence and verify opening hours and every travel leg before relying on it."
        )

    monkeypatch.setattr(ModelGeneration, "generate", transient)
    result, provider = await generate("untrusted input", Explanation)
    assert provider == "groq" and calls == ["vertex_ai", "groq"]

    async def denied(self, prompt, schema):
        raise ProviderError("authentication", False)

    monkeypatch.setattr(ModelGeneration, "generate", denied)
    with pytest.raises(ProviderError, match="authentication"):
        await generate("untrusted input", Explanation)

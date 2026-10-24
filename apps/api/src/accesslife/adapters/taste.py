import math
import unicodedata
import re
import asyncio
import hashlib
import json
import httpx
from accesslife.domain.models import Place
from accesslife.ports.providers import ProviderError
from accesslife.application.limits import provider_call
from accesslife.adapters import provider_cache
from accesslife.config import settings


class DevelopmentTaste:
    async def rank_candidates(self, places: list[Place], interests: list[str]) -> dict:
        seeds = {s.lower().strip() for s in interests}
        matches = {p.id: sorted(seeds & set(p.interests)) for p in places}
        ordered = sorted(places, key=lambda p: (-len(matches[p.id]), p.id))
        return {
            "provider": "development",
            "label": "Development taste engine",
            "live": False,
            "order": [p.id for p in ordered],
            "matches": matches,
            "scores": {},
            "warning": "Category matching only. No Qloo cultural graph or affinity scores are being used.",
        }


class QlooTaste:
    PLACE_PARAMS = {
        "filter.type",
        "signal.interests.entities",
        "signal.interests.tags",
        "filter.results.entities",
        "filter.location",
        "filter.location.radius",
        "take",
    }

    def __init__(self, key: str, base_url: str = "https://hackathon.api.qloo.com", transport=None):
        self.key, self.base_url, self.transport = key, base_url, transport
        if base_url != "https://hackathon.api.qloo.com":
            raise ValueError("Hackathon keys require the hackathon API origin")

    @provider_call
    async def request(self, path: str, params: dict):
        if not self.key:
            raise ProviderError("qloo_unconfigured")
        cache_key = hashlib.sha256(json.dumps([self.key, path, params], sort_keys=True).encode()).hexdigest()
        use_cache = settings().qloo_cache_enabled and path in {"/search", "/v2/tags"}
        if use_cache:
            cached = await asyncio.to_thread(provider_cache.get, cache_key)
            if cached is not None:
                return cached
        async with httpx.AsyncClient(transport=self.transport, timeout=8) as client:
            for attempt in range(2):
                try:
                    response = await client.get(
                        self.base_url + path, headers={"X-Api-Key": self.key}, params=params
                    )
                except httpx.RequestError as exc:
                    if attempt == 0:
                        continue
                    raise ProviderError("qloo_timeout", True) from exc
                if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                    continue
                if response.status_code in (401, 403):
                    raise ProviderError("qloo_authentication")
                if response.status_code >= 400:
                    raise ProviderError(
                        "qloo_request_failed", response.status_code == 429 or response.status_code >= 500
                    )
                try:
                    data = response.json()
                    if not isinstance(data, dict) or data.get("success") is False:
                        raise ProviderError("qloo_malformed")
                    if use_cache:
                        if path == "/search":
                            self.entities(data, search=True)
                        elif not isinstance(data.get("results"), dict) or not isinstance(
                            data["results"].get("tags"), list
                        ):
                            raise ProviderError("qloo_malformed")
                        await asyncio.to_thread(provider_cache.put, cache_key, data)
                    return data
                except ValueError as exc:
                    raise ProviderError("qloo_malformed") from exc
        raise ProviderError("qloo_unavailable", True)

    @staticmethod
    def entities(data, *, search=False):
        results = data.get("results")
        entities = results if search else results.get("entities") if isinstance(results, dict) else None
        if not isinstance(entities, list) or not all(isinstance(e, dict) for e in entities):
            raise ProviderError("qloo_malformed")
        return entities

    async def resolve_interests(self, names: list[str]):
        resolved = []
        for name in names[:5]:
            data = await self.request("/search", {"query": name, "take": 5})
            entities = self.entities(data, search=True)
            exact = [
                e
                for e in entities
                if isinstance(e.get("name"), str) and e["name"].casefold() == name.casefold()
            ]
            if len(exact) == 1 and exact[0].get("entity_id"):
                resolved.append(exact[0]["entity_id"])
        return resolved

    async def insights(self, params):
        if set(params) - self.PLACE_PARAMS or params.get("filter.type") != "urn:entity:place":
            raise ProviderError("unsupported_qloo_parameters")
        return await self.request("/v2/insights", params)

    async def resolve_tags(self, names: list[str]):
        resolved, unresolved = [], []
        for name in names[:5]:
            data = await self.request(
                "/v2/tags",
                {
                    "filter.query": name,
                    "filter.tag.types": "urn:tag:category:place,urn:tag:genre:place,urn:tag:genre:media,urn:tag:ambience:qloo",
                    "take": 10,
                },
            )
            tags = data.get("results", {}).get("tags") if isinstance(data.get("results"), dict) else None
            if not isinstance(tags, list) or not all(isinstance(t, dict) for t in tags):
                raise ProviderError("qloo_malformed")
            matched = False
            # Explicit place categories take precedence over genres. Within a type,
            # multiple exact matches remain unresolved; never choose by popularity.
            for tag_type in (
                "urn:tag:category:place",
                "urn:tag:genre:place",
                "urn:tag:genre:media",
                "urn:tag:ambience:qloo",
            ):
                exact = [
                    t
                    for t in tags
                    if t.get("type") == tag_type
                    and t.get("name", "").casefold() == name.casefold()
                    and t.get("id")
                ]
                if len(exact) == 1:
                    resolved.append(exact[0]["id"])
                    matched = True
                    break
                if len(exact) > 1:
                    break
            if not matched:
                unresolved.append(name)
        return list(dict.fromkeys(resolved)), unresolved

    async def rank_candidates(self, places: list[Place], interests: list[str]):
        tags, unresolved = await self.resolve_tags(interests)
        entity_names = [
            name.removeprefix("entity:").strip() for name in unresolved if name.startswith("entity:")
        ]
        seeds = await self.resolve_interests(entity_names) if entity_names else []
        if not seeds and not tags:
            raise ProviderError("qloo_interests_unresolved")
        crosswalk = {}
        for place in places[:8]:
            data = await self.request(
                "/search", {"query": place.name, "types": "urn:entity:place", "take": 5}
            )
            entities = self.entities(data, search=True)
            matches = {}
            for entity in entities:
                loc = entity.get("location") or {}
                if not isinstance(loc, dict):
                    continue
                lat, lon = loc.get("lat"), loc.get("lon")
                if (
                    self.canonical_name(entity.get("name", "")) == self.canonical_name(place.name)
                    and isinstance(lat, (int, float))
                    and isinstance(lon, (int, float))
                    and entity.get("entity_id")
                ):
                    if abs(lat - place.latitude) < 0.005 and abs(lon - place.longitude) < 0.005:
                        matches[entity["entity_id"]] = entity
            if len(matches) == 1:
                crosswalk[next(iter(matches))] = place.id
        if not crosswalk:
            raise ProviderError("qloo_places_unmapped")
        params = {
            "filter.type": "urn:entity:place",
            "filter.results.entities": ",".join(crosswalk),
            "take": len(crosswalk),
        }
        if seeds:
            params["signal.interests.entities"] = ",".join(seeds)
        if tags:
            params["signal.interests.tags"] = ",".join(tags)
        data = await self.insights(params)
        entities = self.entities(data)
        scores = {}
        for entity in entities:
            pid = crosswalk.get(entity.get("entity_id"))
            query = entity.get("query") or {}
            score = query.get("affinity") if isinstance(query, dict) else None
            if pid and type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 1:
                scores[pid] = score
        if not scores:
            raise ProviderError("qloo_scores_unavailable")
        order = sorted(places, key=lambda p: (p.id not in scores, -scores.get(p.id, 0), p.id))
        return {
            "provider": "qloo",
            "label": "Qloo live",
            "live": True,
            "scores": scores,
            "score_semantics": "Qloo affinity, comparable only within this request; not an enjoyment probability",
            "order": [p.id for p in order],
            "resolved_entities": seeds,
            "resolved_tags": tags,
            "matches": {},
            "unmapped": [p.id for p in places if p.id not in scores],
        }

    @staticmethod
    def canonical_name(name):
        if not isinstance(name, str):
            return ""
        name = "".join(
            c for c in unicodedata.normalize("NFKD", name.casefold()) if not unicodedata.combining(c)
        )
        name = re.sub(r"[^a-z0-9 ]", "", name)
        return re.sub(r"^the\s+", "", name).strip()

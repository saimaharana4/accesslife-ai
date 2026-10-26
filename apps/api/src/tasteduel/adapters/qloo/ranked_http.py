"""Explicit escape hatch for the pinned harness's documented ranking-contract gap.

No silent transport switch. Resolution still uses the official MCP port; only
ranking uses independently validated GET Insights with an explicit affinity sort.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
import json
import math
import unicodedata
from uuid import UUID

import httpx

from tasteduel.adapters.qloo.normalization import _image
from tasteduel.ports.qloo import (
    EntityMetadata,
    ProviderFailure,
    QlooPort,
    QlooResult,
    RankedCandidate,
    RankedCandidatesRequest,
    RankingEvidence,
    ResolutionIssue,
    ranked_context_hash,
    ranked_http_parameters,
)


class QlooRankedHttpAdapter:
    def __init__(
        self,
        resolution: QlooPort,
        *,
        api_key: str,
        reserve_upstream: Callable[[str], Awaitable[None]],
        note_dispatch: Callable[[str], None],
        client: httpx.AsyncClient | None = None,
        typed_search: bool = False,
    ):
        self.resolution = resolution
        self.typed_search = typed_search
        self._key = api_key
        self._reserve = reserve_upstream
        self._dispatch = note_dispatch
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=3),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )

    async def close(self):
        if self._owns_client:
            await self._client.aclose()

    async def resolve_seed(self, request):
        if self.typed_search:
            if (
                request.domain not in ("artist", "movie")
                or not isinstance(request.query, str)
                or not 1 <= len(request.query.strip()) <= 200
            ):
                return self._failure("INVALID_SEED_REQUEST")
            payload = await self._get(
                "/search",
                {"query": request.query.strip(), "types": "urn:entity:" + request.domain, "take": 5},
            )
            return payload if isinstance(payload, QlooResult) else normalize_typed_search(payload, request)
        return await self.resolution.resolve_seed(request)

    async def ranked_candidates(self, request: RankedCandidatesRequest):
        if (
            not isinstance(request.seed_id, UUID)
            or request.seed_domain not in ("artist", "movie")
            or request.target_domain not in ("artist", "movie")
            or type(request.limit) is not int
            or not 1 <= request.limit <= 20
        ):
            return self._failure("INVALID_RANKING_REQUEST")
        payload = await self._get("/v2/insights", ranked_http_parameters(request))
        return payload if isinstance(payload, QlooResult) else normalize_ranked_http(payload, request)

    async def _get(self, path, parameters):
        if path not in ("/search", "/v2/insights"):
            return self._failure("QLOO_ENDPOINT_BLOCKED")
        if not self._key:
            return self._failure("QLOO_CREDENTIAL_UNAVAILABLE")
        await self._reserve(path)
        # This is the transport's actual send attempt, not the earlier reservation.
        self._dispatch(path)
        try:
            async with self._client.stream(
                "GET",
                "https://hackathon.api.qloo.com" + path,
                params=parameters,
                headers={"X-Api-Key": self._key},
                follow_redirects=False,
            ) as response:
                status = response.status_code
                if status in (401, 403):
                    return self._failure("QLOO_AUTHENTICATION_FAILED")
                if status == 429:
                    retry = response.headers.get("retry-after", "")
                    try:
                        number = float(retry)
                        retry = min(60.0, max(0.0, number)) if math.isfinite(number) else None
                    except ValueError:
                        retry = None
                    return QlooResult("error", error=ProviderFailure("QLOO_RATE_LIMITED", True, retry))
                if 500 <= status <= 599:
                    return self._failure("QLOO_UPSTREAM_UNAVAILABLE", True)
                if status != 200:
                    return self._failure("QLOO_HTTP_REJECTED")
                body = bytearray()
                async for part in response.aiter_bytes():
                    body.extend(part)
                    if len(body) > 2_000_000:
                        return self._failure("QLOO_RESPONSE_TOO_LARGE")
                payload = json.loads(body)
        except (httpx.TimeoutException, TimeoutError):
            return self._failure("QLOO_HTTP_DEADLINE", True)
        except httpx.TransportError:
            return self._failure("QLOO_UPSTREAM_UNAVAILABLE", True)
        except (ValueError, UnicodeDecodeError):
            return self._failure("QLOO_CONTRACT_INVALID")
        return payload

    @staticmethod
    def _failure(code, retryable=False):
        return QlooResult("error", error=ProviderFailure(code, retryable))


def normalize_typed_search(payload, request) -> QlooResult:
    """Actual returned types only. Ambiguity requires a user choice, never a guess."""
    # Search's documented envelope is {results: [...]}; unlike Insights it does
    # not require a success member. An explicit failure is still rejected.
    if not isinstance(payload, dict) or ("success" in payload and payload["success"] is not True):
        return QlooRankedHttpAdapter._failure("QLOO_CONTRACT_INVALID")
    rows = payload.get("results")
    rows = rows.get("entities") if isinstance(rows, dict) else rows
    if not isinstance(rows, list) or len(rows) > 5:
        return QlooRankedHttpAdapter._failure("QLOO_CONTRACT_INVALID")
    if not rows:
        return QlooResult("empty")
    entities = tuple(_search_entity(row, request.domain) for row in rows)
    if any(entity is None for entity in entities) or len({entity.id for entity in entities}) != len(entities):
        return QlooRankedHttpAdapter._failure("QLOO_CONTRACT_INVALID")

    def normalized(value):
        return unicodedata.normalize("NFKC", value).strip().casefold()

    matches = tuple(entity for entity in entities if normalized(entity.name) == normalized(request.query))
    if len(matches) == 1:
        return QlooResult("ok", entities=matches)
    return QlooResult("needs_input", issues=(ResolutionIssue("ambiguous", matches or entities),))


def _search_entity(row, domain):
    if not isinstance(row, dict):
        return None
    try:
        identifier = UUID(row.get("entity_id", ""))
    except (ValueError, TypeError, AttributeError):
        return None
    name = row.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        return None
    types = row.get("types", [])
    if not isinstance(types, list) or any(not isinstance(value, str) for value in types):
        return None
    observed = []
    for value in [row.get("type"), row.get("subtype"), *types]:
        if value is None or value == "urn:entity":
            continue
        if not isinstance(value, str) or not value:
            return None
        observed.append(value.removeprefix("urn:entity:"))
    if not observed or any(value != domain for value in observed):
        return None
    properties = row.get("properties", {})
    image = _image(properties.get("image")) if isinstance(properties, dict) else None
    return EntityMetadata(identifier, name.strip(), domain, image)


def normalize_ranked_http(payload, request: RankedCandidatesRequest) -> QlooResult:
    def invalid():
        return QlooResult("error", error=ProviderFailure("QLOO_CONTRACT_INVALID"))

    if not isinstance(payload, dict) or payload.get("success") is not True:
        return invalid()
    results = payload.get("results")
    rows = results.get("entities") if isinstance(results, dict) else None
    if not isinstance(rows, list) or len(rows) > request.limit:
        return invalid()
    if not rows:
        return QlooResult("empty")
    candidates = []
    seen = set()
    previous = math.inf
    explanation_present = False
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            return invalid()
        try:
            identifier = UUID(row.get("entity_id", ""))
        except (ValueError, TypeError, AttributeError):
            return invalid()
        name, query = row.get("name"), row.get("query")
        if (
            identifier in seen
            or not isinstance(name, str)
            or not name.strip()
            or len(name) > 200
            or not isinstance(query, dict)
        ):
            return invalid()
        seen.add(identifier)
        score = query.get("affinity")
        try:
            finite_score = type(score) in (int, float) and math.isfinite(score)
        except (OverflowError, TypeError, ValueError):
            finite_score = False
        if not finite_score or score > previous:
            return invalid()
        if "affinity" in row and (type(row["affinity"]) not in (int, float) or row["affinity"] != score):
            return invalid()
        observed = []
        for key in ("type", "subtype"):
            value = row.get(key)
            if value is not None and value != "urn:entity":
                if not isinstance(value, str) or not value:
                    return invalid()
                observed.append(value.removeprefix("urn:entity:"))
        types = row.get("types", [])
        if not isinstance(types, list):
            return invalid()
        for value in types:
            if not isinstance(value, str):
                return invalid()
            if value != "urn:entity":
                observed.append(value.removeprefix("urn:entity:"))
        if not observed or any(value != request.target_domain for value in observed):
            return invalid()
        properties = row.get("properties", {})
        image = _image(properties.get("image")) if isinstance(properties, dict) else None
        explanation_present |= bool(query.get("explainability"))
        candidates.append(
            RankedCandidate(
                EntityMetadata(identifier, name.strip(), request.target_domain, image), float(score), position
            )
        )
        previous = score
    warnings = ("UNREVIEWED_EXPLANATION_PRESENT",) if explanation_present else ()
    evidence = RankingEvidence(
        ranked_context_hash(request, transport="http_ranked"),
        datetime.now(UTC),
        score_field="query.affinity",
        ordering_verified=True,
        source_label="Qloo Insights API; explicit affinity sort",
        transport="http_ranked",
    )
    return QlooResult("ok", candidates=tuple(candidates), warnings=warnings, evidence=evidence)

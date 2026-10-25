"""Strict, bounded projection of canonical MCP envelopes into private typed values."""

from datetime import datetime, timezone
import ipaddress
import math
import re
from urllib.parse import urlsplit
from uuid import UUID

from tasteduel.ports.qloo import (
    EntityMetadata,
    ProviderFailure,
    QlooResult,
    RankedCandidate,
    RankingEvidence,
    ResolutionIssue,
)

STATUSES = {"ok", "empty", "needs_input", "partial", "degraded", "error"}


def _domain(value):
    return value.removeprefix("urn:entity:") if isinstance(value, str) else None


def _image(value):
    if not isinstance(value, dict) or not isinstance(value.get("url"), str):
        return None
    value = value["url"]
    if len(value) > 2048:
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            return None
        if parts.hostname.lower() in {"localhost", "localhost.localdomain"}:
            return None
        try:
            if not ipaddress.ip_address(parts.hostname).is_global:
                return None
        except ValueError:
            pass
        return value  # Metadata only: never fetched, licensed, or publicly projected here.
    except ValueError:
        return None


def _entity(row, domain, matching_identity=None):
    if not isinstance(row, dict):
        return None
    try:
        identifier = UUID(row.get("entity_id", row.get("id", "")))
    except (ValueError, TypeError, AttributeError):
        return None
    observed = [_domain(row.get(key)) for key in ("type", "subtype")]
    observed = [value for value in observed if value and value != "urn:entity"]
    if not observed and matching_identity:
        if matching_identity.get("entityId") == str(identifier):
            observed = [_domain(matching_identity.get("type"))]
    if not observed or any(value != domain for value in observed):
        return None
    name = row.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 500:
        return None
    properties = row.get("properties")
    image = _image(properties.get("image")) if isinstance(properties, dict) else None
    return EntityMetadata(identifier, name.strip(), domain, image)


def _failure(code="PROVIDER_CONTRACT_INVALID"):
    return QlooResult("error", error=ProviderFailure(code))


def normalize_result(payload, *, operation, domain, context_hash):
    if not isinstance(payload, dict) or not isinstance(domain, str) or domain not in {"artist", "movie"}:
        return _failure()
    if payload.get("schema_version") != "1.0-preview.1" or payload.get("operation") != operation:
        return _failure()
    status, rows = payload.get("status"), payload.get("results")
    if not isinstance(status, str) or status not in STATUSES or not isinstance(rows, list) or len(rows) > 20:
        return _failure()
    if "result_count" in payload and (
        type(payload["result_count"]) is not int or payload["result_count"] != len(rows)
    ):
        return _failure()
    if (
        not isinstance(operation, str)
        or operation not in {"describe", "recommend"}
        or not isinstance(context_hash, str)
        or not re.fullmatch(r"[a-f0-9]{64}", context_hash)
    ):
        return _failure()
    warning_codes = []
    # Arbitrary provider warning/explanation text is untrusted. Preserve presence as a factual code.
    if payload.get("warnings"):
        warning_codes.append("PROVIDER_WARNINGS_PRESENT")
    if payload.get("explainability"):
        warning_codes.append("UNREVIEWED_EXPLANATION_PRESENT")
    error = None
    if status == "error":
        value = payload.get("error")
        if not isinstance(value, dict):
            return _failure()
        code = value.get("code")
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code):
            code = "PROVIDER_ERROR"
        error = ProviderFailure(code, value.get("retryable") is True)
    issues = []
    resolution = payload.get("resolution")
    if isinstance(resolution, dict):
        raw_issues = resolution.get("issues", [])
        if isinstance(raw_issues, list):
            for issue in raw_issues[:10]:
                if not isinstance(issue, dict):
                    continue
                choices = issue.get("candidates", [])
                normalized = (
                    tuple(entity for row in choices[:10] if (entity := _entity(row, domain)))
                    if isinstance(choices, list)
                    else ()
                )
                kind = issue.get("kind")
                issues.append(
                    ResolutionIssue(
                        kind
                        if isinstance(kind, str) and kind in {"ambiguous", "not_found", "unresolved"}
                        else "unresolved",
                        normalized,
                    )
                )
    entities, candidates = [], []
    rejected = 0
    interpretation = payload.get("interpretation", {})
    identity = interpretation.get("entity") if isinstance(interpretation, dict) else None
    seen = set()
    if status in {"ok", "partial", "degraded"}:
        for position, row in enumerate(rows):
            entity = _entity(row, domain, identity if isinstance(identity, dict) else None)
            if not entity or entity.id in seen:
                rejected += 1
                continue
            seen.add(entity.id)
            if operation == "describe":
                entities.append(entity)
            else:
                score = row.get("affinity")
                if type(score) not in {int, float} or not math.isfinite(score):
                    rejected += 1
                    continue
                if row.get("explainability"):
                    warning_codes.append("UNREVIEWED_EXPLANATION_PRESENT")
                candidates.append(RankedCandidate(entity, float(score), position))
    if rejected:
        warning_codes.append("CANDIDATES_REJECTED")
        if status == "ok":
            status = "partial" if candidates or entities else "degraded"
    if status == "ok" and not candidates and not entities:
        status = "empty"
    evidence = RankingEvidence(context_hash, datetime.now(timezone.utc)) if candidates else None
    return QlooResult(
        status,
        tuple(entities),
        tuple(candidates),
        tuple(issues),
        tuple(dict.fromkeys(warning_codes)),
        evidence,
        error,
    )

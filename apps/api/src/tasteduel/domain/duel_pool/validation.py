"""Fail-closed validation of a single already-normalized frozen context."""

from collections import Counter
from dataclasses import dataclass
from math import isfinite
from unicodedata import normalize
from urllib.parse import urlsplit
from uuid import UUID

from .types import Candidate, Category, PairQualityPolicy, RankingSnapshot


@dataclass(frozen=True)
class ValidationResult:
    accepted: tuple[Candidate, ...]
    rejections: tuple[tuple[str, int], ...]
    snapshot_reasons: tuple[str, ...]


def canonical_name(value: str) -> str:
    return " ".join(normalize("NFKC", value).casefold().split())


def category_labels(candidate: Candidate) -> frozenset[str]:
    return frozenset(
        canonical_name(category.label)
        for category in candidate.categories
        if isinstance(category, Category)
        and isinstance(category.label, str)
        and category.label.strip()
        and len(category.label) <= 120
        and isinstance(category.source, str)
        and category.source.strip()
        and len(category.source) <= 300
    )


def approved_image(candidate: Candidate) -> str | None:
    if candidate.image_rights_verified is not True or not isinstance(candidate.image_url, str):
        return None
    try:
        parsed = urlsplit(candidate.image_url)
        if (
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and len(candidate.image_url) <= 2048
        ):
            # URL is metadata only. Any later image fetch needs its own allowlist/SSRF policy.
            return candidate.image_url
    except ValueError:
        pass
    return None


def validate_snapshot(snapshot: RankingSnapshot, policy: PairQualityPolicy) -> ValidationResult:
    fatal: list[str] = []
    if snapshot.ordering_verified is not True:
        fatal.append("ordering_unverified")
    if snapshot.domain not in ("artist", "movie") or snapshot.seed_domain not in ("artist", "movie"):
        fatal.append("unsupported_domain")
    if not isinstance(snapshot.seed_id, UUID):
        fatal.append("invalid_seed_identity")
    if (
        not isinstance(snapshot.context_hash, str)
        or not snapshot.context_hash.strip()
        or len(snapshot.context_hash) > 128
    ):
        fatal.append("missing_context")
    if not all(
        isinstance(value, str) and value.strip() and len(value) <= 128
        for value in (snapshot.provider, snapshot.harness_version, snapshot.score_field)
    ):
        fatal.append("missing_provenance")
    if len(snapshot.candidates) > policy.max_candidates:
        fatal.append("candidate_limit_exceeded")
        return ValidationResult(
            (), (("candidate_limit_exceeded", len(snapshot.candidates)),), tuple(sorted(set(fatal)))
        )

    id_counts = Counter(c.id for c in snapshot.candidates if isinstance(c.id, UUID))
    names = Counter(
        canonical_name(c.name) for c in snapshot.candidates if isinstance(c.name, str) and c.name.strip()
    )
    positions = Counter(c.position for c in snapshot.candidates if type(c.position) is int and c.position > 0)
    accepted: list[Candidate] = []
    rejected: Counter[str] = Counter()
    for candidate in snapshot.candidates:
        reasons: list[str] = []
        if not isinstance(candidate.id, UUID):
            reasons.append("invalid_identity")
        elif id_counts[candidate.id] > 1:
            reasons.append("duplicate_identity")
        elif candidate.id == snapshot.seed_id:
            reasons.append("seed_self_match")
        if not isinstance(candidate.name, str) or not candidate.name.strip() or len(candidate.name) > 200:
            reasons.append("missing_metadata")
        elif names[canonical_name(candidate.name)] > 1:
            reasons.append("ambiguous_name")
        if candidate.ambiguous is not False:
            reasons.append("ambiguous_identity")
        if candidate.domain != snapshot.domain:
            reasons.append("domain_mismatch")
        if candidate.context_hash != snapshot.context_hash:
            reasons.append("context_mismatch")
        if (
            not isinstance(candidate.categories, tuple)
            or len(candidate.categories) > 3
            or any(
                not isinstance(category, Category)
                or not isinstance(category.label, str)
                or not category.label.strip()
                or len(category.label) > 120
                or not isinstance(category.source, str)
                or not category.source.strip()
                or len(category.source) > 300
                for category in candidate.categories
            )
        ):
            reasons.append("invalid_category_metadata")
        try:
            finite_score = type(candidate.affinity) in (float, int) and isfinite(candidate.affinity)
        except (OverflowError, TypeError, ValueError):
            finite_score = False
        if not finite_score:
            reasons.append("missing_or_nonfinite_score")
        if type(candidate.position) is not int or candidate.position <= 0:
            reasons.append("invalid_position")
        elif positions[candidate.position] > 1:
            reasons.append("duplicate_position")
        if reasons:
            # An entity is counted once; reason counters may count multiple independently useful facts.
            rejected.update(set(reasons))
        else:
            accepted.append(candidate)
    accepted.sort(key=lambda c: (c.position, str(c.id)))
    if any(a.affinity < b.affinity for a, b in zip(accepted, accepted[1:])):
        fatal.append("contradictory_order")
    return ValidationResult(tuple(accepted), tuple(sorted(rejected.items())), tuple(sorted(set(fatal))))

"""Explicit public projections. Never call model_dump on a private row/receipt."""

from tasteduel.api import schemas as s
from tasteduel.domain.types import RankingSource
from tasteduel.ports.reads import DiscoveryRead, EntityRead, GameRead, RoundRead


def entity(value: EntityRead) -> s.EntityPublic:
    art = s.ArtworkPublic(kind="owned_fallback", asset_id=value.asset_id) if value.asset_id else None
    return s.EntityPublic(
        id=value.id, name=value.name, type=value.entity_type, source=value.source, artwork=art
    )


def round_public(game: GameRead, round_: RoundRead | None = None):
    round_ = round_ or game.current
    if round_ is None:
        return None
    choices = tuple(s.ChoicePublic(id=choice.id, entity=entity(choice.entity)) for choice in round_.choices)
    common = dict(
        game_id=game.id,
        round_id=round_.id,
        ordinal=round_.ordinal,
        revision=game.revision,
        seed=entity(game.seed),
        target_type=round_.target_type,
        choices=choices,
        source=game.seed.source,
    )
    if round_.accepted is None:
        return s.PlayableRoundPublic(
            **common,
            question=f"Which {round_.target_type} ranks higher for this seed in {'this synthetic fixture' if game.seed.source == 'fixture' else 'Qloo’s taste graph'}?",
        )
    accepted, receipt = round_.accepted, game.receipt
    # Global pool diagnostics can reveal future answer-dependent information.
    # Accepted earlier rounds do not authorize disclosure about unplayed pairs.
    summary = (
        s.CurationSummaryPublic(
            curator_mode=receipt.curator_mode,
            source=game.seed.source,
            target_domains=receipt.target_domains_selected,
            candidate_count_received=receipt.candidate_count_received,
            rejection_counts=receipt.rejection_counts,
            bounded_correction_count=receipt.bounded_correction_count,
            five_round_path_verified=receipt.five_round_path_verified,
        )
        if game.phase == "completed" and game.answered_count == 5
        else None
    )
    # Optional richer wording remains absent until returned semantics/rights are verified.
    evidence = s.RevealedEvidencePublic(
        source=game.seed.source,
        context=s.RankingContextPublic(
            seed=entity(game.seed), target_type=round_.target_type, retrieved_at=round_.retrieved_at
        ),
    )
    return s.RevealedRoundPublic(
        **common,
        selected_choice_id=accepted.selected_choice_id,
        winning_choice_id=accepted.winning_choice_id,
        correct=accepted.correct,
        cumulative_score=accepted.cumulative_score,
        accepted_at=accepted.accepted_at,
        evidence=evidence,
        curation_summary=summary,
    )


def game_public(game: GameRead) -> s.GamePublic:
    return s.GamePublic(
        game_id=game.id,
        phase=game.phase,
        mode=game.mode,
        revision=game.revision,
        seed=entity(game.seed),
        curator_mode=game.receipt.curator_mode,
        source=RankingSource(game.seed.source),
        current_ordinal=game.current_ordinal,
        answered_count=game.answered_count,
        score=game.score,
        expires_at=game.expires_at,
        current_round=round_public(game),
    )


def discovery_public(value: DiscoveryRead) -> s.DiscoveryPublic:
    return s.DiscoveryPublic(
        entity=entity(value.entity), saved_at=value.saved_at, expires_at=value.expires_at
    )

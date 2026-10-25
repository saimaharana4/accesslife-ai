"""PostgreSQL read adapter. Builds bounded values, never generic ORM responses."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from tasteduel.application.errors import AppError
from tasteduel.domain.curation import CurationReceipt as ReceiptValue
from tasteduel.persistence import models as m
from tasteduel.ports.reads import AcceptedRead, ChoiceRead, DiscoveryRead, EntityRead, GameRead, RoundRead


def unavailable():
    return AppError(503, "STORED_STATE_UNAVAILABLE", "The saved game is temporarily unavailable.")


class SqlReadRepository:
    def __init__(self, db: Session, session_id: UUID):
        self.db, self.session_id = db, session_id

    def owned(self, model, *conditions):
        return select(model).where(model.session_id == self.session_id, *conditions)

    def entity(self, entity_id: UUID, source: str) -> EntityRead:
        entity = self.db.scalar(self.owned(m.Entity, m.Entity.id == entity_id))
        if entity is None or entity.expires_at <= datetime.now(UTC):
            raise unavailable()
        # Only known local owned fallback IDs are enabled in this foundation.
        asset = entity.artwork_asset_id if entity.rights_policy == "project_owned" else None
        if asset not in {"afterlight", "blue-hour", "slow-burn", "velvet-static"}:
            asset = None
        return EntityRead(entity.id, entity.name, entity.entity_type, source, asset)

    def receipt(self, game_id: UUID) -> ReceiptValue:
        receipt = self.db.scalar(self.owned(m.CurationReceipt, m.CurationReceipt.game_id == game_id))
        if receipt is None or receipt.status != "succeeded":
            raise AppError(
                409, "GENERATION_IN_PROGRESS", "A validated game has not been published yet.", retryable=True
            )
        return ReceiptValue(
            game_id=receipt.game_id,
            curator_mode=receipt.curator_mode,
            seed_entity_id=receipt.seed_entity_id,
            seed_type=receipt.seed_type,
            target_domains_considered=tuple(receipt.target_domains_considered),
            target_domains_selected=tuple(receipt.target_domains_selected),
            qloo_request_count=receipt.qloo_request_count,
            tool_request_count=receipt.tool_request_count,
            model_request_count=receipt.model_request_count,
            candidate_count_received=receipt.candidate_count_received,
            rejection_counts=receipt.rejection_counts,
            valid_pair_count=receipt.valid_pair_count,
            bounded_correction_count=receipt.bounded_correction_count,
            five_round_path_verified=receipt.five_round_path_verified,
            provider_version=receipt.provider_version,
            harness_version=receipt.harness_version,
            model_version=receipt.model_version,
            validator_version=receipt.validator_version,
            elapsed_ms=receipt.elapsed_ms,
            status=receipt.status,
            created_at=receipt.created_at,
        )

    def round(self, game_id: UUID, delivered, source: str) -> RoundRead:
        pair = self.db.scalar(
            self.owned(m.PrivatePair, m.PrivatePair.id == delivered.pair_id, m.PrivatePair.game_id == game_id)
        )
        if pair is None:
            raise unavailable()
        snapshot = self.db.scalar(
            self.owned(
                m.RankingSnapshot,
                m.RankingSnapshot.id == pair.snapshot_id,
                m.RankingSnapshot.game_id == game_id,
            )
        )
        if snapshot is None or snapshot.expires_at <= datetime.now(UTC):
            raise AppError(410, "GAME_EXPIRED", "The evidence supporting this game has expired.")
        rows = list(
            self.db.scalars(
                self.owned(
                    m.RoundContestant,
                    m.RoundContestant.round_id == delivered.id,
                    m.RoundContestant.game_id == game_id,
                ).order_by(m.RoundContestant.side)
            )
        )
        if len(rows) != 2 or [row.side for row in rows] != ["left", "right"]:
            raise unavailable()
        choices = tuple(ChoiceRead(row.id, self.entity(row.entity_id, source)) for row in rows)
        answer = self.db.scalar(
            self.owned(m.Answer, m.Answer.round_id == delivered.id, m.Answer.game_id == game_id)
        )
        accepted = None
        if answer is not None:
            # Only after accepted-answer/owner checks may a private winner leave this adapter.
            winner = next((row.id for row in rows if row.entity_id == pair.winner_entity_id), None)
            if winner is None or answer.choice_id not in {row.id for row in rows}:
                raise unavailable()
            earlier_ids = select(m.DeliveredRound.id).where(
                m.DeliveredRound.game_id == game_id,
                m.DeliveredRound.session_id == self.session_id,
                m.DeliveredRound.ordinal <= delivered.ordinal,
            )
            accepted_answers = list(self.db.scalars(self.owned(m.Answer, m.Answer.round_id.in_(earlier_ids))))
            accepted = AcceptedRead(
                answer.choice_id,
                winner,
                answer.correct,
                answer.created_at,
                sum(answer_.correct for answer_ in accepted_answers),
            )
        return RoundRead(
            delivered.id, delivered.ordinal, snapshot.target_type, snapshot.created_at, choices, accepted
        )

    def game(self, game_id: UUID) -> GameRead | None:
        game = self.db.scalar(self.owned(m.Game, m.Game.id == game_id))
        if game is None:
            return None
        receipt = self.receipt(game_id)
        source = "fixture" if receipt.curator_mode == "fixture" else "qloo"
        answers = list(self.db.scalars(self.owned(m.Answer, m.Answer.game_id == game_id)))
        delivered = self.db.scalar(
            self.owned(
                m.DeliveredRound,
                m.DeliveredRound.game_id == game_id,
                m.DeliveredRound.ordinal == game.current_ordinal,
            )
        )
        current = self.round(game_id, delivered, source) if delivered is not None else None
        return GameRead(
            game.id,
            game.session_id,
            game.status,
            game.mode,
            game.revision,
            game.current_ordinal,
            len(answers),
            sum(answer.correct for answer in answers),
            game.expires_at,
            self.entity(game.seed_entity_id, source),
            receipt,
            current,
        )

    def answered_rounds(self, game_id: UUID) -> tuple[RoundRead, ...]:
        receipt = self.receipt(game_id)
        source = "fixture" if receipt.curator_mode == "fixture" else "qloo"
        rounds = self.db.scalars(
            self.owned(m.DeliveredRound, m.DeliveredRound.game_id == game_id).order_by(
                m.DeliveredRound.ordinal
            )
        )
        return tuple(self.round(game_id, round_, source) for round_ in rounds)

    def discoveries(self) -> tuple[DiscoveryRead, ...]:
        rows = list(
            self.db.scalars(self.owned(m.Discovery).order_by(m.Discovery.created_at.desc()).limit(100))
        )
        result = []
        for row in rows:
            entity = self.db.scalar(self.owned(m.Entity, m.Entity.id == row.entity_id))
            if entity is not None and entity.expires_at > datetime.now(UTC):
                source = "fixture" if entity.provider == "fixture" else "qloo"
                result.append(
                    DiscoveryRead(self.entity(entity.id, source), row.created_at, entity.expires_at)
                )
        return tuple(result)

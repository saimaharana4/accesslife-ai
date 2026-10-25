"""Owned read use cases; authoritative mutation/curation is deliberately later."""

from datetime import UTC, datetime
from uuid import UUID

from tasteduel.application.errors import AppError, not_found
from tasteduel.ports.reads import ReadRepository


class ReadService:
    def __init__(self, repository: ReadRepository, session_id: UUID):
        self.repository = repository
        self.session_id = session_id

    def game(self, game_id: UUID):
        game = self.repository.game(game_id)
        if game is None or game.session_id != self.session_id:
            raise not_found()
        if game.expires_at <= datetime.now(UTC) or game.phase == "expired":
            raise AppError(410, "GAME_EXPIRED", "This game has expired. Start a new game.")
        if game.phase == "cancelled":
            raise AppError(409, "GAME_CANCELLED", "This game is no longer active.")
        return game

    def playable(self, game_id: UUID):
        game = self.game(game_id)
        if game.current is None:
            raise AppError(409, "NO_CURRENT_ROUND", "This game has no unanswered current round.")
        if game.current.accepted is not None:
            raise AppError(409, "ROUND_AWAITING_ADVANCE", "Read the accepted reveal and select Next.")
        return game

    def results(self, game_id: UUID):
        game = self.game(game_id)
        if game.phase != "completed" or game.answered_count != 5:
            raise AppError(409, "GAME_INCOMPLETE", "Complete all five rounds before opening results.")
        rounds = self.repository.answered_rounds(game_id)
        if len(rounds) != 5 or any(round_.accepted is None for round_ in rounds):
            raise AppError(503, "STORED_STATE_UNAVAILABLE", "This result is temporarily unavailable.")
        return game, rounds

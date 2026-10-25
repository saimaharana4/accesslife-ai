"""Stable application failures, containing safe copy rather than provider/SQL errors."""


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable


def not_found() -> AppError:
    return AppError(404, "NOT_FOUND", "The requested resource is unavailable.")

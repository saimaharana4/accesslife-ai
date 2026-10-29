"""Allowlisted preparation failures; never serialize provider diagnostics or pool facts."""

from tasteduel.application.errors import AppError


def preparation_failure(outcome) -> AppError:
    code = outcome.failure_code
    feedback = outcome.receipt.final_pool_status
    if code == "CURATION_DEADLINE":
        return AppError(503, "GENERATION_DEADLINE_EXCEEDED",
            "Preparing this duel took too long. Retry the same saved request.", retryable=True)
    if code == "QLOO_AUTHENTICATION_FAILED":
        return AppError(503, "GENERATION_CONFIGURATION_UNAVAILABLE",
            "Game preparation is unavailable. Please try again later.")
    if feedback in {"insufficient_coverage", "needs_input"} and code in {
        None, "INSUFFICIENT_COVERAGE", "MODEL_REQUEST_BUDGET", "CORRECTION_BUDGET",
    }:
        return AppError(422, "GENERATION_INSUFFICIENT_COVERAGE",
            "There are not enough verified comparisons for this favourite. Choose another artist or film.")
    if feedback == "provider_unavailable" or code == "PROVIDER_UNAVAILABLE":
        return AppError(503, "GENERATION_PROVIDER_UNAVAILABLE",
            "The cultural ranking service is temporarily unavailable. Retry the same saved request.", retryable=True)
    return AppError(503, "GENERATION_UNAVAILABLE",
        "This duel could not be prepared. Retry the same saved request.", retryable=True)

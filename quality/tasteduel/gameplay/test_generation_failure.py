"""Failure contracts contain no entity, rank or provider diagnostics."""
from types import SimpleNamespace

import pytest

from tasteduel.application.generation_failure import preparation_failure


@pytest.mark.parametrize("reason,status,expected,retryable", [
    ("CURATION_DEADLINE", None, "GENERATION_DEADLINE_EXCEEDED", True),
    ("QLOO_AUTHENTICATION_FAILED", "provider_unavailable", "GENERATION_CONFIGURATION_UNAVAILABLE", False),
    ("INSUFFICIENT_COVERAGE", "insufficient_coverage", "GENERATION_INSUFFICIENT_COVERAGE", False),
    ("PROVIDER_UNAVAILABLE", "provider_unavailable", "GENERATION_PROVIDER_UNAVAILABLE", True),
    ("PRIVATE_PROVIDER_DIAGNOSTICS", None, "GENERATION_UNAVAILABLE", True),
    ("MALFORMED_TOOL_ARGUMENTS", "insufficient_coverage", "GENERATION_UNAVAILABLE", True),
])
def test_failure_classification_is_explicit_allowlisted_and_sanitized(reason,status,expected,retryable):
    outcome = SimpleNamespace(failure_code=reason, receipt=SimpleNamespace(final_pool_status=status))
    error = preparation_failure(outcome)
    assert error.code == expected and error.retryable is retryable
    assert error.status == (422 if expected == "GENERATION_INSUFFICIENT_COVERAGE" else 503)
    assert "PRIVATE_PROVIDER_DIAGNOSTICS" not in error.message

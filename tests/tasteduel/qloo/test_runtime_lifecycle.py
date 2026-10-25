"""No secret access/network: exercise the API lifecycle with injected private runtimes."""

from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from tasteduel.api.main import create_app
from tasteduel.api.provider_runtime import ProviderStartupFailure
from tasteduel.config import Settings


def test_disabled_lifecycle_never_invokes_provider_factory():
    async def forbidden(*args):
        pytest.fail("Default API must not read Secret Manager or start a provider")

    app = create_app(Settings(), qloo_factory=forbidden)
    with TestClient(app) as client:
        assert client.get("/v1/health/live").status_code == 200
        assert app.state.qloo is None
        assert app.state.qloo_status == "disabled"


def test_one_runtime_per_lifespan_and_shutdown(db_engine):
    calls = []
    port = object()

    async def close():
        calls.append("close")

    async def factory(settings, engine):
        assert engine is db_engine
        calls.append("start")
        return SimpleNamespace(port=port, close=close)

    app = create_app(Settings(qloo_enabled=True), engine=db_engine, qloo_factory=factory)
    with TestClient(app) as client:
        assert app.state.qloo is port
        for _ in range(3):
            assert client.get("/v1/health/live").status_code == 200
        assert calls == ["start"]
    assert calls == ["start", "close"]
    assert app.state.qloo is None


def test_provider_startup_failure_is_safe_no_fallback(db_engine):
    async def factory(*args):
        raise ProviderStartupFailure("QLOO_AUTHENTICATION_FAILED")

    app = create_app(Settings(qloo_enabled=True), engine=db_engine, qloo_factory=factory)
    with TestClient(app) as client:
        assert app.state.qloo is None
        assert app.state.qloo_status == "QLOO_AUTHENTICATION_FAILED"
        response = client.get("/v1/health/live")
        assert response.status_code == 200
        assert "AUTHENTICATION" not in response.text


def test_reference_configuration_cannot_redirect_credentials():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(qloo_secret_version="https://docs.qloo.com/mcp")

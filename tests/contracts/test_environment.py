import httpx
import pytest
from accesslife.adapters import environment
from accesslife.config import settings


@pytest.mark.parametrize(
    "payload,expected",
    [
        (
            {
                "daily": {
                    "time": ["2026-10-29"],
                    "temperature_2m_max": [18],
                    "precipitation_probability_max": [20],
                }
            },
            "live",
        ),
        ({"daily": {"time": []}}, "outside_forecast_horizon"),
        ({"daily": None}, "unavailable"),
        ({}, "unavailable"),
    ],
)
async def test_forecast_valid_missing_and_malformed_do_not_fabricate(monkeypatch, payload, expected):
    monkeypatch.setattr(settings(), "live_providers", True)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        environment.httpx,
        "AsyncClient",
        lambda **kw: original(
            **kw, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
        ),
    )
    result = await environment.weather("london", "2026-10-29")
    assert result["status"] == expected
    if expected != "live":
        assert "temperature_max_c" not in result


async def test_forecast_timeout_and_transit_capabilities_are_explicit(monkeypatch):
    monkeypatch.setattr(settings(), "live_providers", True)
    original = httpx.AsyncClient

    def timeout(request):
        raise httpx.ReadTimeout("synthetic deadline", request=request)

    monkeypatch.setattr(
        environment.httpx, "AsyncClient", lambda **kw: original(**kw, transport=httpx.MockTransport(timeout))
    )
    assert (await environment.weather("london", "2026-10-29"))["status"] == "unavailable"
    for city in ("london", "new-york", "paris", "berlin", "chicago"):
        assert (await environment.transit(city))["status"] == "routing_unverified"

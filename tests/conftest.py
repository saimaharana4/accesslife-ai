import os

os.environ["GENERATION_PROVIDER"] = "template"
os.environ["LIVE_PROVIDERS"] = "false"
os.environ["TASTE_PROVIDER"] = "development"
os.environ["QLOO_CACHE_ENABLED"] = "false"
# Repeated deterministic suites share an isolated DB, never the public demo quota.
os.environ["MAX_DAILY_PLANNING_RUNS"] = "1000000"
os.environ["PROVIDER_LIMITS_ENABLED"] = "false"
os.environ["DATABASE_URL"] = os.environ.get(
    "ACCESSLIFE_TEST_DATABASE_URL",
    "postgresql+psycopg://accesslife:accesslife_local@127.0.0.1:5432/accesslife_test",
)

import pytest
from fastapi.testclient import TestClient
from accesslife.api.main import app
from accesslife.persistence.db import Session, SessionRow


@pytest.fixture
def client():
    import hashlib

    with TestClient(app) as client:
        response = client.post("/v1/sessions")
        assert response.status_code == 200
        token = client.cookies.get("accesslife_session")
        yield client
        with Session.begin() as db:
            row = db.get(SessionRow, hashlib.sha256(token.encode()).hexdigest())
            if row:
                db.delete(row)


@pytest.fixture
def inputs():
    return {
        "city_id": "london",
        "window": {
            "starts_at": "2026-10-29T10:00:00+00:00",
            "ends_at": "2026-10-29T15:00:00+00:00",
            "time_zone": "Europe/London",
        },
        "mobility": {"required_features": [], "max_leg_distance_m": 5000, "max_total_distance_m": 10000},
        "interests": [{"name": "art"}],
    }

"""Exercise durable execution over an actual worker restart, using a disposable session."""

import json
import subprocess
import time
from uuid import uuid4
import httpx

with httpx.Client(base_url="http://localhost:8000", timeout=10) as client:
    client.post("/v1/sessions").raise_for_status()
    body = {
        "city_id": "london",
        "window": {
            "starts_at": "2026-10-29T10:00:00+00:00",
            "ends_at": "2026-10-29T15:00:00+00:00",
            "time_zone": "Europe/London",
        },
        "mobility": {"required_features": []},
        "interests": [{"name": "history"}],
    }
    response = client.post("/v1/plans", json=body, headers={"Idempotency-Key": str(uuid4())})
    response.raise_for_status()
    plan_id = response.json()["plan_id"]
    time.sleep(0.7)
    subprocess.run(["docker", "compose", "restart", "worker"], check=True, capture_output=True)
    for _ in range(85):
        result = client.get(f"/v1/plans/{plan_id}")
        result.raise_for_status()
        if result.json()["version"]:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Worker did not resume the durable run within the recovery budget")
    assert result.json()["version"] == 1
    print(
        json.dumps(
            {
                "worker_restart": "passed",
                "published_versions": 1,
                "provisional": not result.json()["confirmed"],
            }
        )
    )
    client.delete("/v1/sessions/current").raise_for_status()

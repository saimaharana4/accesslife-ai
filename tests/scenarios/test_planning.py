from datetime import timedelta
from uuid import uuid4
import pytest
from pydantic import ValidationError
from accesslife.domain.models import Fact, Mobility, Window, eligibility
from accesslife.adapters.catalogue import PLACES, CITIES
from accesslife.application.runs import claim_run
from accesslife.agents.planner import execute
from accesslife.persistence.db import Session, RunRow, now


@pytest.mark.parametrize(
    "status,conflict,stale,refs",
    [
        ("unknown", False, False, []),
        ("limited", False, False, ["x"]),
        ("inaccessible", False, False, ["x"]),
        ("confirmed", True, False, ["x"]),
        ("confirmed", False, True, ["x"]),
        ("confirmed", False, False, []),
    ],
)
def test_mandatory_access_never_passes_missing_conflicting_or_stale(status, conflict, stale, refs):
    place = PLACES[0].model_copy(deep=True)
    place.facts = [
        Fact(feature="step_free_entrance", status=status, conflict=conflict, stale=stale, evidence_ids=refs)
    ]
    assert not eligibility(place, Mobility(), {"x"})[0]


def test_fabricated_evidence_reference_cannot_establish_eligibility():
    place = PLACES[0].model_copy(deep=True)
    place.facts = [Fact(feature="step_free_entrance", status="confirmed", evidence_ids=["missing-source"])]
    assert not eligibility(place, Mobility(), set())[0]


def test_zero_limits_are_preserved_and_dst_nonexistent_time_rejected():
    assert Mobility(max_leg_distance_m=0).max_leg_distance_m == 0
    with pytest.raises(ValidationError):
        Window(
            starts_at="2026-03-29T01:30:00+00:00",
            ends_at="2026-03-29T04:00:00+01:00",
            time_zone="Europe/London",
        )


async def test_idempotency_duplicate_delivery_versions_and_session_isolation(client, inputs):
    key = str(uuid4())
    first = client.post("/v1/plans", json=inputs, headers={"Idempotency-Key": key})
    assert first.status_code == 202, first.text
    result = first.json()
    assert client.get("/v1/sessions/current").json()["active_run"] == {
        "run_id": result["run_id"],
        "plan_id": result["plan_id"],
    }
    assert client.post("/v1/plans", json=inputs, headers={"Idempotency-Key": key}).json() == result
    changed = {**inputs, "interests": [{"name": "history"}]}
    assert client.post("/v1/plans", json=changed, headers={"Idempotency-Key": key}).status_code == 409
    claimed = claim_run(result["run_id"])
    assert claimed and claim_run(result["run_id"]) is None
    await execute(*claimed)
    assert claim_run(result["run_id"]) is None
    plan = client.get(f"/v1/plans/{result['plan_id']}").json()
    assert plan["version"] == 1 and not plan["confirmed"]
    assert set(plan["baseline_order"]) == set(plan["taste"]["order"])
    response = client.get(f"/v1/runs/{result['run_id']}/events", headers={"Last-Event-ID": "2"})
    ids = [int(line[4:]) for line in response.text.splitlines() if line.startswith("id: ")]
    assert ids and min(ids) > 2 and ids == sorted(set(ids))
    replan = client.post(
        f"/v1/plans/{result['plan_id']}/replan",
        json={"expected_version": 1, "inputs": changed},
        headers={"Idempotency-Key": str(uuid4())},
    )
    await execute(*claim_run(replan.json()["run_id"]))
    assert client.get(f"/v1/plans/{result['plan_id']}").json()["version"] == 2
    assert client.get(f"/v1/plans/{result['plan_id']}?version=1").json()["version"] == 1
    assert (
        client.post(
            f"/v1/plans/{result['plan_id']}/replan",
            json={"expected_version": 1, "inputs": inputs},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 409
    )
    original = client.cookies.get("accesslife_session")
    client.post("/v1/sessions")
    assert client.get(f"/v1/plans/{result['plan_id']}").status_code == 404
    client.delete("/v1/sessions/current")
    client.cookies.set("accesslife_session", original)


async def test_expired_lease_fencing_and_cancellation(client, inputs):
    result = client.post("/v1/plans", json=inputs, headers={"Idempotency-Key": str(uuid4())}).json()
    old = claim_run(result["run_id"])
    with Session.begin() as db:
        db.get(RunRow, result["run_id"]).lease_until = now() - timedelta(seconds=1)
    new = claim_run(result["run_id"])
    assert new and new[1] != old[1]
    await execute(*old)
    assert client.get(f"/v1/plans/{result['plan_id']}").json()["version"] == 0

    client.post(f"/v1/runs/{result['run_id']}/cancel")
    await execute(*new)
    assert client.get(f"/v1/plans/{result['plan_id']}").json()["version"] == 0


async def test_session_clear_between_claim_and_execution_deletes_private_work(client, inputs):
    result = client.post("/v1/plans", json=inputs, headers={"Idempotency-Key": str(uuid4())}).json()
    claimed = claim_run(result["run_id"])
    assert claimed
    client.delete("/v1/sessions/current").raise_for_status()
    await execute(*claimed)
    with Session() as db:
        assert db.get(RunRow, result["run_id"]) is None


@pytest.mark.parametrize("city", CITIES, ids=lambda c: c.id)
async def test_five_cities_have_working_honest_drafts(client, inputs, city):
    values = {
        **inputs,
        "city_id": city.id,
        "window": {
            "starts_at": "2026-10-29T10:00:00"
            + (
                "-04:00"
                if city.id == "new-york"
                else "-05:00"
                if city.id == "chicago"
                else "+01:00"
                if city.id in ["paris", "berlin"]
                else "+00:00"
            ),
            "ends_at": "2026-10-29T15:00:00"
            + (
                "-04:00"
                if city.id == "new-york"
                else "-05:00"
                if city.id == "chicago"
                else "+01:00"
                if city.id in ["paris", "berlin"]
                else "+00:00"
            ),
            "time_zone": city.time_zone,
        },
    }
    result = client.post("/v1/plans", json=values, headers={"Idempotency-Key": str(uuid4())})
    assert result.status_code == 202, result.text
    await execute(*claim_run(result.json()["run_id"]))
    plan = client.get(f"/v1/plans/{result.json()['plan_id']}").json()
    assert plan["stops"] and not plan["confirmed"]
    assert all(s["status"] == "provisional" for s in plan["stops"])


def test_trips_have_unverified_transfers_revision_checks_and_origin_protection(client):
    body = {
        "title": "Across cultures",
        "segments": [
            {"id": "a", "city_id": "london", "date": "2026-10-29"},
            {"id": "b", "city_id": "paris", "date": "2026-10-30"},
        ],
    }
    trip = client.post("/v1/trips", json=body).json()
    assert trip["transfers"][0]["status"] == "user_arranged_unverified"
    assert client.patch(f"/v1/trips/{trip['id']}", json={**body, "expected_revision": 0}).status_code == 409
    assert (
        client.patch(f"/v1/trips/{trip['id']}", json={**body, "expected_revision": 1}).json()["revision"] == 2
    )
    assert (
        client.post("/v1/trips", json=body, headers={"Origin": "https://untrusted.example"}).status_code
        == 403
    )

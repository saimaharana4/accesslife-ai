from datetime import timedelta
from uuid import uuid4
from google.cloud import tasks_v2
from accesslife.application.runs import CloudTasksDispatcher, claim_run
from accesslife.config import settings
from accesslife.persistence.db import Session, RunRow, now


def test_dispatch_reuses_reservations_and_recovers_expired_task_names(client, inputs, monkeypatch):
    cfg = settings()
    for key, value in {
        "cloud_tasks_queue": "projects/synthetic/locations/test/queues/planning",
        "worker_internal_url": "https://worker.invalid",
        "internal_worker_token": "synthetic-only",
        "cloud_tasks_invoker_service_account": "task@synthetic.invalid",
    }.items():
        monkeypatch.setattr(cfg, key, value)
    calls = []

    class Tasks:
        def create_task(self, **kwargs):
            calls.append(kwargs["task"])

    monkeypatch.setattr(tasks_v2, "CloudTasksClient", Tasks)
    response = client.post("/v1/plans", json=inputs, headers={"Idempotency-Key": str(uuid4())})
    rid = response.json()["run_id"]
    dispatcher = CloudTasksDispatcher()
    dispatcher.enqueue(rid)
    dispatcher.enqueue(rid)
    assert calls[0]["name"] == calls[1]["name"]
    assert calls[0]["http_request"]["oidc_token"]["audience"] == "https://worker.invalid"
    assert claim_run(rid)
    dispatcher.enqueue(rid)
    assert len(calls) == 2  # An active execution is never dispatched again.
    with Session.begin() as db:
        row = db.get(RunRow, rid)
        row.lease_until = now() - timedelta(seconds=1)
        row.checkpoint = {"_dispatch": {"revision": 1, "at": (now() - timedelta(minutes=2)).isoformat()}}
    dispatcher.enqueue(rid, rotate=True)
    assert calls[2]["name"] != calls[0]["name"]
    with Session.begin() as db:
        row = db.get(RunRow, rid)
        row.checkpoint = {"_dispatch": {"revision": 3, "at": (now() - timedelta(minutes=2)).isoformat()}}
    dispatcher.enqueue(rid, rotate=True)
    with Session() as db:
        assert db.get(RunRow, rid).status == "failed"
    assert len(calls) == 3

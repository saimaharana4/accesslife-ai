import hashlib
import json
from datetime import timedelta, datetime
from uuid import uuid4
from sqlalchemy import select, func, text
from accesslife.persistence.db import Session, RunRow, EventRow, PlanRow, now
from accesslife.config import settings

TERMINAL = {"completed", "failed", "cancelled", "superseded"}


def append_event(db, run, stage, status, summary, evidence_count=0):
    # Callers hold the run lock; sequence allocation and state changes commit together.
    sequence = (db.scalar(select(func.max(EventRow.sequence)).where(EventRow.run_id == run.id)) or 0) + 1
    data = {
        "run_id": run.id,
        "sequence": sequence,
        "agent": stage,
        "stage": stage,
        "status": status,
        "summary": summary,
        "evidence_count": evidence_count,
        "elapsed_ms": max(0, int((now() - run.created_at).total_seconds() * 1000)),
    }
    db.add(EventRow(run_id=run.id, sequence=sequence, data=data))
    return data


def fingerprint(inputs):
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def claim_run(run_id=None):
    with Session.begin() as db:
        # Cross-process concurrency guard, not a Python in-memory semaphore.
        db.execute(text("SELECT pg_advisory_xact_lock(741802)"))
        active = db.scalar(
            select(func.count())
            .select_from(RunRow)
            .where(RunRow.status == "running", RunRow.lease_until > now())
        )
        if active >= settings().max_active_planning_runs:
            return None
        query = (
            select(RunRow)
            .where(
                (RunRow.status == "queued") | ((RunRow.status == "running") & (RunRow.lease_until < now()))
            )
            .order_by(RunRow.created_at)
            .with_for_update(skip_locked=True)
        )
        if run_id:
            query = query.where(RunRow.id == run_id)
        run = db.scalar(query.limit(1))
        if not run:
            return None
        if run.attempts >= 3:
            run.status = "failed"
            append_event(
                db, run, "supervisor", "failed", "Planning attempts exhausted. Retry with a new request."
            )
            return None
        run.status = "running"
        run.attempts += 1
        run.lease_token = str(uuid4())
        run.lease_until = now() + timedelta(seconds=60)
        append_event(db, run, "supervisor", "running", "Checking city requirements and available evidence")
        return run.id, run.lease_token


def ensure_current(db, run_id, token):
    run = db.scalar(select(RunRow).where(RunRow.id == run_id).with_for_update())
    if not run or run.status != "running" or run.lease_token != token or run.lease_until < now():
        raise RuntimeError("run_obsolete")
    plan = db.get(PlanRow, run.plan_id)
    if not plan or plan.generation != run.generation:
        raise RuntimeError("run_obsolete")
    return run


class PostgresDispatcher:
    def enqueue(self, run_id):
        # The committed queued row is the durable local queue.
        return None


class CloudTasksDispatcher:
    def enqueue(self, run_id, rotate=False):
        from google.cloud import tasks_v2

        # The outbox reservation is committed before the network call. Client
        # retries reuse it; reconciliation rotates a stale task name to avoid
        # Cloud Tasks' tombstone deduplication stranding an unclaimed run.
        with Session.begin() as db:
            run = db.scalar(select(RunRow).where(RunRow.id == run_id).with_for_update())
            if not run or run.status in TERMINAL:
                return
            if run.status == "running" and run.lease_until and run.lease_until > now():
                return
            prior = run.checkpoint.get("_dispatch")
            revision = prior["revision"] if prior else 1
            if rotate and prior:
                if datetime.fromisoformat(prior["at"]) > now() - timedelta(seconds=60):
                    return
                if revision >= 3 or run.attempts >= 3:
                    run.status = "failed"
                    run.lease_until = None
                    append_event(
                        db,
                        run,
                        "supervisor",
                        "failed",
                        "Planning delivery attempts exhausted. Submit a new request.",
                    )
                    return
                revision += 1
            if not prior or rotate:
                run.checkpoint = {
                    **run.checkpoint,
                    "_dispatch": {"revision": revision, "at": now().isoformat()},
                }
        cfg = settings()
        client = tasks_v2.CloudTasksClient()
        task = {
            "name": f"{cfg.cloud_tasks_queue}/tasks/run-{run_id}-dispatch-{revision}",
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": cfg.worker_internal_url + f"/internal/runs/{run_id}:execute",
                "headers": {"Content-Type": "application/json", "X-Worker-Token": cfg.internal_worker_token},
                "body": b"{}",
                "oidc_token": {
                    "service_account_email": cfg.cloud_tasks_invoker_service_account,
                    "audience": cfg.worker_internal_url,
                },
            },
        }
        from google.api_core.exceptions import AlreadyExists

        try:
            client.create_task(parent=cfg.cloud_tasks_queue, task=task)
        except AlreadyExists:
            pass


def dispatcher():
    return CloudTasksDispatcher() if settings().task_backend == "cloud_tasks" else PostgresDispatcher()

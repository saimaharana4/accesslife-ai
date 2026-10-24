import asyncio
import secrets
from fastapi import FastAPI, Request, HTTPException
from sqlalchemy import select, delete
from accesslife.config import settings
from accesslife.persistence.db import (
    Session,
    SessionRow,
    RunRow,
    ProviderCacheRow,
    ProviderPermitRow,
    QuotaRow,
    now,
)
from accesslife.application.runs import claim_run, CloudTasksDispatcher
from accesslife.agents.planner import execute

app = FastAPI(title="AccessLife internal worker")


@app.post("/internal/runs/{run_id}:execute")
async def task(run_id: str, request: Request):
    token = settings().internal_worker_token
    if not token or not secrets.compare_digest(request.headers.get("x-worker-token", ""), token):
        raise HTTPException(403)
    claimed = claim_run(run_id)
    if claimed:
        await execute(*claimed)
    else:
        with Session() as db:
            run = db.get(RunRow, run_id)
            if run and run.status in {"queued", "running"}:
                raise HTTPException(503, "run_busy_retry")
    return {"status": "acknowledged"}


async def loop():
    active = set()
    ticks = 0
    while True:
        active = {task for task in active if not task.done()}
        if len(active) < settings().max_active_planning_runs:
            claimed = await asyncio.to_thread(claim_run)
            if claimed:
                active.add(asyncio.create_task(execute(*claimed)))
        ticks += 1
        if ticks % 120 == 0:
            with Session.begin() as db:
                for model in (SessionRow, ProviderCacheRow, ProviderPermitRow, QuotaRow):
                    db.execute(delete(model).where(model.expires_at < now()))
        await asyncio.sleep(0.5)


def reconcile():
    with Session.begin() as db:
        for model in (SessionRow, ProviderCacheRow, ProviderPermitRow, QuotaRow):
            db.execute(delete(model).where(model.expires_at < now()))
    with Session() as db:
        ids = list(
            db.scalars(
                select(RunRow.id).where(
                    (RunRow.status == "queued")
                    | ((RunRow.status == "running") & (RunRow.lease_until < now()))
                )
            )
        )
    for rid in ids:
        CloudTasksDispatcher().enqueue(rid, rotate=True)


if __name__ == "__main__":
    import sys

    reconcile() if "--reconcile" in sys.argv else asyncio.run(loop())

import asyncio
from contextvars import ContextVar
from datetime import timedelta
from functools import wraps
from uuid import uuid4
from sqlalchemy import select, func, delete, text
from accesslife.persistence.db import Session, ProviderPermitRow, QuotaRow, now
from accesslife.ports.providers import ProviderError

RUN_CONTEXT: ContextVar[str] = ContextVar("run_context", default="")


def quota(key: str, limit: int, seconds: int):
    with Session.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(741805)"))
        row = db.get(QuotaRow, key)
        if not row:
            row = QuotaRow(id=key, count=0, expires_at=now() + timedelta(seconds=seconds))
            db.add(row)
        if row.expires_at < now():
            row.count, row.expires_at = 0, now() + timedelta(seconds=seconds)
        if row.count >= limit:
            raise ProviderError("request_limit_reached")
        row.count += 1


def reserve(run_id):
    with Session.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(741804)"))
        db.execute(delete(ProviderPermitRow).where(ProviderPermitRow.expires_at < now()))
        total = db.scalar(select(func.count()).select_from(ProviderPermitRow))
        per_run = db.scalar(
            select(func.count()).select_from(ProviderPermitRow).where(ProviderPermitRow.run_id == run_id)
        )
        if total >= 12 or per_run >= 5:
            return None
        token = str(uuid4())
        db.add(ProviderPermitRow(id=token, run_id=run_id, expires_at=now() + timedelta(seconds=45)))
        return token


def provider_call(function):
    @wraps(function)
    async def limited(*args, **kwargs):
        from accesslife.config import settings

        if not settings().provider_limits_enabled:
            return await function(*args, **kwargs)
        run_id = RUN_CONTEXT.get() or str(uuid4())
        token = None
        for _ in range(15):
            token = await asyncio.to_thread(reserve, run_id)
            if token:
                break
            await asyncio.sleep(0.1)
        if not token:
            raise ProviderError("provider_busy", True)
        try:
            return await function(*args, **kwargs)
        finally:
            with Session.begin() as db:
                db.execute(delete(ProviderPermitRow).where(ProviderPermitRow.id == token))

    return limited

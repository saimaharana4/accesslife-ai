# Taste Duel database lineage

This lineage is separate from the historical AccessLife migrations. Prompt 5 targets only `127.0.0.1:55435/tasteduel_prompt5`, using the pre-created `tasteduel` schema. The environment refuses other hosts, ports, database names, migration principals and drivers. Cloud migration configuration is a later reviewed change.

Run from the repository root:

```powershell
uv run --no-sync python scripts/tasteduel_local.py start
uv run --no-sync python scripts/tasteduel_local.py migrate
uv run --no-sync python scripts/tasteduel_local.py test tests/tasteduel/integration -q
```

The helper bootstraps a dedicated local container and keeps generated local-only credentials in process memory and dedicated Docker configuration, never repository files or command arguments. Docker retains its own metadata locally. It supplies `TASTEDUEL_MIGRATION_DATABASE_URL` to Alembic and separate runtime/test variables; this lineage never reads the historical `DATABASE_URL` or real provider credentials.

The migration role owns the schema and immutable migration stamp. The runtime role has schema usage, explicitly granted table DML and read access to the nonsecret revision stamp. Neither role is a superuser or can bypass RLS. Runtime cannot create tables, schemas, temporary objects or roles. Public database/schema privileges are revoked by the bootstrap. Runtime gets no delete/update privileges on immutable evidence, answers or frozen challenges; limited session/challenge revocation updates have database guards.

Every owned table uses forced RLS. A trusted API transaction authenticates the session cookie, then calls `set_config('app.session_id', session_uuid, true)`. The custom GUC is a trusted application context, not a cryptographic SQL identity: a database client holding the runtime password can set it. Session authentication, parameterized queries and the private database boundary remain necessary. An unscoped transaction sees no owned rows; revoked/expired sessions cannot see their game graph. Sessions remain visible within their own context so the API can validate expiry/revocation.

`td0001` is the frozen initial SQL schema. `td0002` adds irreversible session revocation, insertion freeze after first delivery, seed exclusion and runtime revision-stamp access. `td0003` adds private mutation receipts containing a canonical signature and checked typed owned references; no raw request or response payload is stored. `td0004` requires an accepted answer for a completed answer receipt and captures the exact authoritative game revision at completion under a row lock. Later advancement leaves the saved completion revision unchanged. Forward migrations carry changes after application; automatic destructive downgrades are disabled. Deployment rollback must preserve a compatible database or use an explicitly reviewed forward repair.

The 19 tables provide the storage foundation. Generation claim/reclaim/concurrency orchestration, authenticated cross-session challenge copying, provider retention policy enforcement and a bounded maintenance purge are later prompts. Session-scoped usage counters do not establish a provider-key-wide quota. Expiry caps and private storage do not establish permission to retain Qloo data; retention still requires verified provider policy. Do not grant a public runtime service migration credentials to perform maintenance.

Mutation receipt subjects are owned games for answer/advance/create-challenge/play-challenge operations and owned entities for discovery saves. A play receipt refers to the newly allocated local replay game. A completed receipt refers only to the matching owned round, discovery, challenge or game; immutable signatures support later request handlers distinguishing a retry from a changed-body conflict. The schema does not implement those handlers or compare incoming HTTP bodies.

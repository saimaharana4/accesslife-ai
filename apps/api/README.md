# Taste Duel API

FastAPI implements authoritative guest gameplay under `src/tasteduel`. Python/Pydantic owns the public contract; OpenAPI generates frontend types. PostgreSQL 16 persists games, evidence, private pools, accepted answers, discoveries and fixed challenges. The current schema head is `td0011`.

Use the [container guide](CONTAINERS.md) for the maintained local runtime. The web app forwards same-origin `/api/v1` requests to private FastAPI `/v1` routes. Production API invocation requires IAM; public browser credentials and direct provider payloads are never exposed.

## Implemented interfaces

| Interface | Behavior |
|---|---|
| `POST /v1/sessions` | Create or reuse an anonymous guest |
| `GET /v1/sessions/current` | Return safe current-session state |
| `DELETE /v1/sessions/current` | Revoke guest access and dependent live shares |
| `GET /v1/entities/search` | Typed, bounded seed lookup with explicit selection |
| `POST /v1/games` | Await bounded generation under a transactional idempotent claim |
| `GET /v1/games/{id}` | Restore authorized state, including a saved accepted reveal |
| `GET /v1/games/{id}/round` | Deliver only the current unanswered public round |
| `POST /v1/games/{id}/answer` | Accept once; identical retry returns saved reveal |
| `POST /v1/games/{id}/advance` | Explicit idempotent advancement/completion |
| `GET /v1/games/{id}/results` | Server-scored completed result |
| `GET/POST /v1/discoveries` | List or explicitly save permitted discoveries |
| `DELETE /v1/discoveries/{entity_id}` | Remove an owned discovery |
| `POST /v1/challenges` | Freeze exactly five delivered comparisons |
| `GET/DELETE /v1/challenges/{slug}` | Read a safe invitation or revoke an owned link |
| `POST /v1/challenges/{slug}/plays` | Create a separate guest-owned fixed replay |
| `GET /v1/health/live` | Process liveness |
| `GET /v1/health/ready` | Database/schema and honest admission readiness |

Exact request/response schemas and declared status codes are in the [exported contract](../../packages/contracts/openapi.json). Error envelopes contain a stable code, useful message and retry metadata rather than stack traces. State/signature conflicts return 409, expired evidence 410, validation failures 422, admission limits 429 and unavailable dependencies 503 as applicable. A running generation reservation can return 202 with an expiry/recovery path; no background queue is implied.

## Authority and isolation

Generation stores the ready pool and full private curation receipt atomically. Expiring fenced execution claims prevent duplicate publication after restart. Reusing an idempotency key with changed input is a conflict, not a new game.

Only an authenticated owner can answer or advance. The playable DTO omits answers, ranks, affinities and future contestants. The reveal DTO exposes only an accepted current round. Reload can restore that reveal without delivering a future answer. Score is derived from stored accepted answers, never client totals.

Solo adaptation uses the validated unused pool without new provider calls. Challenge replay freezes order/sides/context/rules and does not adapt or re-query Qloo. Prediction correctness is never stored as a preference; explicit discovery saves are a separate action.

Runtime and migration roles are separate; forced RLS protects owned records. The runtime cannot perform schema DDL or modify immutable evidence. Private provider controls coordinate key-wide budgets across instances. [Security model](../../docs/security.md) · [Migration lineage](tasteduel_migrations/README.md).

## Contracts and tests

From the repository root:

```powershell
uv sync --project runtime/python --frozen --group dev
corepack pnpm contracts
uv run --project runtime/python --frozen python scripts/export_contracts.py --check
.\scripts\tasteduel-compose.ps1 test
```

Database tests require the isolated local stack described in the container guide. CI uses synthetic provider contracts and a clean PostgreSQL database, not production event keys. Dated component audits preserve their original implementation checkpoints; [current verification](../../docs/verification.md) and [release identities](../../infra/migration/production-release-execution-2026-10-28.md) supersede old stage-status claims.

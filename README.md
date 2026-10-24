# AccessLife AI

Evidence-led cultural outings for London, New York, Paris, Berlin and Chicago.

A working local Next.js/FastAPI application with sourced venue cards, feature evidence, mobility constraints, provisional itineraries, immutable replanning, progress replay and multi-city collections. Actual Qloo and Vertex integrations have passed live smoke checks. **[Open the live GCP application](https://accesslife-web-dfthmgvvaa-el.a.run.app).** Verified deployment results are recorded in [project memory](ai/memory.md).

**All current outings are provisional.** Door-to-door routes, opening windows, travel durations, last-mile access and rest seating remain unverified. Venue facts cannot establish a safe entire journey. Inter-city transfers are user-arranged and unverified.

## Run locally

Docker Desktop must be running. The Windows preflight checks it, validates Compose, mounts existing ADC read-only when present, migrates the database and starts services:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
# Application: http://localhost:3000
# API documentation: http://localhost:8000/docs
```

Or use Compose directly:

```powershell
Copy-Item .env.example .env  # Once; keep your existing local configuration.
docker compose up --build
```

The default clone runs with a clearly labelled development taste provider. Language-service failure preserves deterministic facts and a factual explanation template. No provider key is needed for that provisional flow. Images contain a pinned CPU MiniLM model; build needs access to its public model repository.

To index the 12 original guidance summaries:

```powershell
docker compose --profile tools run --rm ingest
```

Stop services without erasing the database volume:

```powershell
docker compose down
```

Do not add `-v` unless you intend to delete local application data. Anonymous sessions expire after 24 hours; clearing a session deletes its active records. Cloud backups follow their separate retention policy.

## Real providers and credentials

Vertex uses Google Gen AI with ADC, global `gemini-3.8-flash` and LOW thinking. Project/model access was verified by an actual structured-output request. New developers can authenticate using `gcloud.cmd auth application-default login`; `scripts/dev.ps1` mounts that original credential directory read-only. Do not copy ADC into the repository or images.

All real application credentials belong in Secret Manager. `.env` should contain **resource references**, not payloads. For the authorized project, local Qloo configuration is:

```dotenv
TASTE_PROVIDER=qloo
QLOO_API_KEY_SECRET=projects/project-bb13ecd8-9d67-408d-9a7/secrets/accesslife-qloo-api-key
```

The operator needs access to that secret; the browser never receives the key. Runtime cloud identities receive access only to their required secrets. Vertex and GitHub Actions use IAM rather than static API/service-account keys. Database and worker credentials are also in Secret Manager. Optional Groq/OpenAI/Ollama credentials remain unconfigured; use rotated values before enabling them through their `*_API_KEY_SECRET` references.

Qloo resolves place tags and explicit named seeds (`entity:Radiohead`), matches eligible venues, then calls Insights. Real results enable the Qloo Impact Lab. A failed/unmapped integration remains visibly a development fallback. Scores are comparable only within the same request and are not enjoyment probabilities. Raw responses remain in a private expiring server cache, never in Git or a public dataset.

## Coverage and limitations

| City | Curated venues | Live Qloo-scored venues in art/history smoke |
|---|---:|---:|
| London | 3 | 2 |
| New York | 3 | 1 |
| Paris | 3 | 2 |
| Berlin | 3 | 2 |
| Chicago | 3 | 3 |

Twelve narrow feature summaries link to official venue sources and record retrieval/rights information. Unverified or conflicting mandatory facts cannot pass eligibility. Some lift statements are limited, not blanket confirmation. No city is coverage-complete. Additional OSM results are discovery previews outside the curated planning pool. Weather is optional; transport adapters expose capabilities/available line status, not verified accessible routing.

Distance values are explicitly straight-line lower bounds. The planner rejects outlines that already exceed those bounds; a draft within the bounds still needs actual route verification. Visit durations and rest suggestions are planning placeholders. The small retrieval smoke is not a held-out recall benchmark or multilingual corpus.

## Architecture and verification

Server-rendered Next.js shell and an accessible interactive workspace; FastAPI/Pydantic contracts; replaceable provider ports; a bounded LangGraph planning graph; PostgreSQL 16 with PostGIS/pgvector, durable execution leases/checkpoints/events and immutable plan versions. Local dispatch uses committed database rows and a separate worker. Cloud Tasks dispatch uses persisted reservations, IAM, idempotency and bounded reconciliation.

Install Node 24, Python 3.12 and uv for development checks. Dependency lockfiles are committed:

```powershell
uv sync --frozen --extra retrieval --group dev
npx.cmd --yes pnpm@10.28.2 install --frozen-lockfile
$env:PYTHONPATH='apps/api/src'
# One-time isolated test database, after the local DB is running:
docker compose exec -T db createdb -U accesslife accesslife_test
$env:DATABASE_URL='postgresql+psycopg://accesslife:accesslife_local@127.0.0.1:5432/accesslife_test'
uv run alembic -c apps/api/alembic.ini upgrade head
Remove-Item Env:DATABASE_URL
uv run pytest -q
uv run python scripts/export_contracts.py
npx.cmd --yes pnpm@10.28.2 contracts
npx.cmd --yes pnpm@10.28.2 typecheck
npx.cmd --yes pnpm@10.28.2 exec playwright install chromium
npx.cmd --yes pnpm@10.28.2 test:e2e
```

Use the existing test database on later runs; do not recreate or drop application data. Override `ACCESSLIFE_TEST_DATABASE_URL` if required. Tests default to deterministic providers and never use the live key. Live checks are explicit:

```powershell
uv run python scripts/qloo_smoke.py
uv run python scripts/provider_smoke.py
uv run python scripts/retrieval_smoke.py
uv run python scripts/runtime_smoke.py  # Restarts the actual local worker.
uv run python scripts/restore_smoke.py  # Restores a snapshot into a disposable local DB.
```

35 backend contracts/scenarios, desktop/mobile browser journeys locally and on GCP, axe scans, keyboard/reflow/reduced-motion checks, worker restart and a real local backup/restore have passed. Check [memory](ai/memory.md) for final counts and cloud-specific outcomes. Screen-reader user testing, complete city coverage, deeper retrieval evaluation and broader load testing remain release work.

## GCP operations

The agreed project is `project-bb13ecd8-9d67-408d-9a7`, region `asia-south1`. AccessLife has its own Cloud SQL instance and runtime identities, independent of existing workloads. Terraform prepares public web, private API/worker, Cloud Tasks, maintenance jobs, private buckets, Secret Manager integration, registry, WIF and monitoring.

The dated [cost review](infra/COST_REVIEW.md) forecasts US$78.48 including an 18% tax reserve through 5 November against the US$80 envelope. It assumes bounded demo use and requires daily review. Alerts and instance limits are not spending caps. Extending the window or load requires another estimate. [Operations instructions](infra/README.md) distinguish local validation, actual rollout, rollback and teardown.

## Implementation documents

| Document | Purpose |
|---|---|
| [prd.md](ai/prd.md) | Product requirements, current limits and future features |
| [Architecture.md](ai/Architecture.md) | Modules, contracts, planning flow and deployment |
| [rules.md](ai/rules.md) | Stack, evidence, security and error handling |
| [phases.md](ai/phases.md) | Build sequence and honest completion gates |
| [design.md](ai/design.md) | Visual system, components and interaction states |
| [memory.md](ai/memory.md) | Short dated outcomes and outstanding gates |

Only the six maintained documents in `/ai` are published. The three original local references remain unchanged and ignored; runtime never depends on them.

## Hackathon and license

Target feature freeze: 30 October. Submission deadline: **31 October 2026, 9:15 AM IST**. Preserve judging access through 5 November and required follow-up. A live Qloo adapter alone does not establish release qualification: external app access, validated coverage and submission evidence still need their gates. See the [official guide](https://docs.qloo.com/reference/qloo-llm-hackathon-developer-guide), [overview](https://qloo.devpost.com/) and [rules](https://qloo.devpost.com/rules).

Source and documentation: [MIT](LICENSE). Model, map, venue and provider rights remain separate; see [third-party notices](third_party/README.md). Never publish real Qloo payloads, personal plans or credentials as test data.

# Taste Duel

**Production readiness ? 27 October 2026.** The production-mode application, isolated local runtime, and CI checks are verified. Taste Duel is **not deployed to GCP and is not yet a public production service**. The latest successful [production verification run](https://github.com/saimaharana4/accesslife-ai/actions/runs/40489370908) passed on commit `afb41e1`, including database migrations, provider contracts, container smoke, Playwright, full axe scans, secret scanning, and Terraform validation.

Taste Duel is a five-round cultural prediction game. A player chooses a familiar artist or film, then predicts which of two Qloo-ranked entities appears higher for that specific seed and query. Qloo supplies the cultural ranking; deterministic code controls eligibility, winners, scoring, and replay. A correct guess measures game performance only. It is never recorded as a preference.

## Product experience

- Search and select an exact supported Qloo entity as the seed.
- Play five rounds with clear loading, source, reveal, and result states.
- Read factual post-answer context about Qloo's ranking; unsupported explanations are omitted.
- Adapt challenge level from the player's game performance and the already validated pool. This is not taste learning.
- Save discoveries only through an explicit user action.
- Create an invitation that freezes the creator's five delivered comparisons. A friend gets a separate score and the same comparisons; shared play is casual, not a cheat-proof competition.
- Use the complete keyboard-accessible, map-free flow. Original title-card artwork is the fallback when licensed imagery is unavailable.

Taste Duel distinguishes genuine Qloo-backed play, deterministic Qloo curation, and synthetic fixture mode. Fixture results are visibly labelled and cannot enter production builds.

## Run locally

Requires Docker Desktop. From the repository root in PowerShell:

```powershell
.\scripts\tasteduel-compose.ps1 preflight
.\scripts\tasteduel-compose.ps1 up
.\scripts\tasteduel-compose.ps1 health
.\scripts\tasteduel-compose.ps1 test
.\scripts\tasteduel-compose.ps1 down
```

The web app is at `http://127.0.0.1:13001`; API documentation is at `http://127.0.0.1:18005/docs`. PostgreSQL data remains in the separate `taste-duel-data` volume after stopping the stack. Do not remove that volume as part of routine shutdown.

The default local stack disables external providers. Optional live mode requires ADC and server-side Secret Manager access; the preflight checks only for an ADC file and never reads or copies its contents. See the [container and operations guide](apps/api/CONTAINERS.md) before enabling providers.

## Architecture

The web application uses Next.js App Router and strict TypeScript. The API uses FastAPI, Pydantic, SQLAlchemy, Alembic, and PostgreSQL 16. Python owns the API schemas; TypeScript client types are generated from OpenAPI.

The private Qloo adapter resolves seeds and ranked candidates. A bounded Vertex curator can choose among supported sources and refine an inadequate candidate strategy. Deterministic validators and transactions retain authority over every answer. Qloo and Vertex credentials remain server-side; browser DTOs omit future answers and private pools. Challenges store immutable delivered rounds rather than querying providers again.

The local Compose runtime uses separate web, API, migration, and database roles, pinned dependencies, non-root application containers, and a persistent database volume. GCP deployment is a separate release operation and has not been performed.

## Verification and release status

Local verification recorded 666 backend tests, 61 Node checks, 36 full browser/a11y audit cases, and 21 fixture-browser cases. A persisted synthetic game and challenge replay survived an API restart with zero provider calls. The search control's corrected SVG chevron was verified in production rendering and keyboard interaction.

The latest CI run covers the same source and additionally checks a clean database migration, generated-contract drift, production container build/smoke, tracked-source secret scanning, and backend-free Terraform validation. No cloud resource was provisioned or deployed by that run.

Before a public GCP launch, complete the reviewed cloud cost/IAM/Secret Manager setup, deploy and exercise the genuine provider path in the target environment, and finish willing-user playtesting plus manual screen-reader and native browser-zoom review. CI success is evidence of repeatable checks; it is not a production deployment or proof of real-user impact.

## Project documentation

- [Product requirements](ai/prd.md)
- [Architecture](ai/Architecture.md)
- [Engineering and security rules](ai/rules.md)
- [Implementation phases](ai/phases.md)
- [Visual and interaction design](ai/design.md)
- [Dated project memory](ai/memory.md)
- [Qloo source, capability, and rights record](ai/qloo-capability-matrix.md)
- [API operations](apps/api/CONTAINERS.md)
- [API security and performance audit](apps/api/AUDIT.md)
- [Source and third-party licence notes](third_party/README.md)

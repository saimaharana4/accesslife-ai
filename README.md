# Taste Duel

**Production readiness — 27 October 2026.** The production-mode application, isolated local runtime, and baseline CI checks are verified. Taste Duel is **not deployed to GCP and is not yet a public production service**. The recorded [production verification run](https://github.com/saimaharana4/taste-duel/actions/runs/40491218493) passed on commit `ef5c27c`, including database migrations, provider contracts, container smoke, Playwright, full axe scans, secret scanning, and Terraform validation. The new product-validation changes require their own CI run.

Taste Duel is a five-round cultural prediction game. A player chooses a familiar artist or film, then predicts which of two Qloo-ranked entities appears higher for that specific seed and query. Qloo supplies the cultural ranking; deterministic code controls eligibility, winners, scoring, and replay. A correct guess measures game performance only. It is never recorded as a preference.

Cloud foundation is verified: the saved plan applied, restricted keyless access
and new database privileges passed, and shared rollback assets remain preserved.
The conservative forecast is US$82.84 under the approved US$90 ceiling.
[Taste Duel application deployment remains pending](infra/migration/foundation-execution-2026-10-27.md).

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

The [foundation cost review](infra/migration/cost-approval-2026-10-27.md) passes at
**US$82.84 under the user-approved US$90 ceiling**, preserving seven backups.
It conservatively includes all unallocated gross usage and assumes no future
credits. The independently reviewed saved foundation plan applied successfully;
keyless [authentication passed](https://github.com/saimaharana4/taste-duel/actions/runs/40559171936).
The repository is now `saimaharana4/taste-duel`. Live database privilege checks passed; Taste Duel services and public traffic have not been deployed.

A bounded live quality audit checked Radiohead and Beyoncé → films, and Inception and Spirited Away → artists. All four produced valid five-round paths with ten distinct contestants, using exactly eight Qloo requests and no model calls. Original title cards remain the approved artwork; image metadata alone does not grant reuse rights. Difficulty remains a versioned engineering heuristic, not human calibration. See the [round-quality results](ai/round-quality-validation.md).

Private server-side [event accounting](ai/product-event-accounting.md) records committed gameplay, explicit saves and fixed challenge activity without search text, ranking payloads or tracking fingerprints. Tests/fixtures are excluded by default, and operational activity is never presented as verified human participation. There are **zero observed human participants**; the [willing-user protocol](ai/playtest-protocol.md) is ready and human discovery value remains unproven.

Current local verification passed 681 backend tests (one Compose-only restart check skipped), the production build, strict typecheck, unchanged OpenAPI contracts, fixture exclusion and a reviewed-source secret scan. Six affected full keyboard solo/replay journeys passed across desktop, 390px and 320px with 33 full axe scans and 33 captures. The earlier CI baseline separately recorded 61 Node checks, 36 complete audit cases, 21 fixture-browser cases and restart-safe synthetic game/challenge persistence; those unchanged checks were not all rerun for this update.

The recorded CI baseline additionally checked a clean database migration, generated-contract drift, production container build/smoke, tracked-source secret scanning, and backend-free Terraform validation. No cloud resource was provisioned or deployed by that run.

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

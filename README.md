# Taste Duel

**Live web app:** [Play Taste Duel](https://tasteduel-web-902056825143.asia-south1.run.app). The production configuration passed genuine Qloo/Vertex five-round play, discovery saving, exact friend replay, response-loss recovery, keyboard/mobile checks and full axe scans. The API remains IAM-private. Readiness monitoring and a compatible rollback/return rehearsal passed. [Verified release evidence and limitations](infra/migration/production-release-execution-2026-10-28.md).

Taste Duel is a five-round cultural prediction game. A player chooses a familiar artist or film, then predicts which of two Qloo-ranked entities appears higher for that specific seed and query. Qloo supplies the cultural ranking; deterministic code controls eligibility, winners, scoring, and replay. A correct guess measures game performance only. It is never recorded as a preference.

The application runs on GCP with managed SQL, server-side Secret Manager references
and keyless identities. Existing AccessLife recovery data remains separate and
preserved. [Deployment and recovery evidence](infra/migration/production-release-execution-2026-10-28.md).

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

The local Compose runtime uses separate web, API, migration, and database roles, pinned dependencies, non-root application containers, and a persistent database volume. GCP serves the public web app through a private API with managed SQL connectivity. No worker, ingestion service or embedding model is required.

## Verification and release status

The [carried-forward 28 October production forecast](infra/migration/production-cost-review-2026-10-28.md) passes at
**US$88.15 under the user-approved US$90 ceiling**, preserving seven backups.
It conservatively includes all unallocated gross usage and assumes no future
credits; no 29 October billing refresh is claimed. The independently reviewed saved foundation plan applied successfully;
keyless [authentication passed](https://github.com/saimaharana4/taste-duel/actions/runs/40559171936).
The repository is `saimaharana4/taste-duel`. Live database privilege checks passed. The reviewed web-only public grant applied after the exact sealed configuration passed acceptance; unauthenticated direct API requests still return 403.

A bounded live quality audit checked Radiohead and Beyoncé → films, and Inception and Spirited Away → artists. All four produced valid five-round paths with ten distinct contestants, using exactly eight Qloo requests and no model calls. Original title cards remain the approved artwork; image metadata alone does not grant reuse rights. Difficulty remains a versioned engineering heuristic, not human calibration. See the [round-quality results](ai/round-quality-validation.md).

Private server-side [event accounting](ai/product-event-accounting.md) records committed gameplay, explicit saves and fixed challenge activity without search text, ranking payloads or tracking fingerprints. Tests/fixtures are excluded by default, and operational activity is never presented as verified human participation. There are **zero observed human participants**; the [willing-user protocol](ai/playtest-protocol.md) is ready and human discovery value remains unproven.

The deployed application source is `e49564c6c4c36840fbc7b4a101793863bd8c330c`, with immutable API/web image digests in the [release manifest](infra/releases/production-2026-10-28.json). Its [full remote CI](https://github.com/saimaharana4/taste-duel/actions/runs/40696917534) passed contracts, real PostgreSQL integration, strict typecheck, production/container builds, OpenAPI drift, secret scanning, Terraform validation and complete desktop/mobile axe journeys. Later release-tooling and documentation changes do not change the deployed application files.

The recorded CI baseline additionally checked a clean database migration, generated-contract drift, production container build/smoke, tracked-source secret scanning, and backend-free Terraform validation. No cloud resource was provisioned or deployed by that run.

The [release record](infra/migration/production-release-execution-2026-10-28.md) distinguishes the genuine solo game created on the sealed production configuration from the subsequent unauthenticated public fixed replay and typed search. Twelve sealed and eight public full axe scans passed. Verification games retain their normal expiry; they are never extended to repeat a test. After an overnight pause, rollback and return checks proved health/expiry behavior, unchanged hashes across 14 history tables and unchanged provider counters; they did not replay an expired game. Cleanup has been exercised but remains a bounded manual operation. Willing-user discovery value, native screen-reader and native zoom testing remain unmeasured. The recovery rehearsal proved a scoped in-memory logical restore, not a managed Cloud SQL backup restore or a durable full export. CI and automated cloud play do not establish real-user impact.

Challenge canonical URLs, share links and original-art social images use the actual Cloud Run origin. No custom domain is claimed. The landing page is intentionally `noindex` and currently has no canonical/OG SEO tags.

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

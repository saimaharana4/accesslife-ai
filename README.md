# Taste Duel

One favourite. Five duels. Predict Qloo's ranking, discover something surprising, then challenge a friend to the same five rounds.

**Status - 26 October 2026: Prompt 7 implements the private deterministic duel-pool engine offline.** It proves complete five-round no-repeat paths, enforces versioned quality/diversity and returns bounded curator feedback. The real-normalized-sample gate is blocked: Prompt 2 retained aggregates only and canonical MCP ordering remains unverified. The browser still uses synthetic fixtures; live gameplay, agent and public release are pending. No provider/model/credential/cloud calls or database changes occurred in Prompt 7.

## What the new product will do

1. Play as a guest and select an unambiguous movie or music-artist seed.
2. Predict which of two same-type entities ranks higher for that seed in one frozen Qloo request context.
3. Complete five solo rounds, with deterministic difficulty adaptation and one point per correct prediction.
4. See a result ticket and save discoveries within the guest session.
5. Share the **actual five rounds played**, with their order, sides, answer key and scoring version frozen. A friend's replay does not adapt or refresh Qloo rankings.

Qloo supplies the ranking for a request; it does not decide whether someone's personal taste is correct. No enjoyment probabilities, invented global percentiles, speed-based scores or unverified claims about individual fans. Book/person support is a later capability gate, not a current promise. The AccessLife five-city requirement does not apply to this new product.

The target interface is a mobile-first cultural game: oversized artwork, distinctive typography, a central DUEL seam and a shareable result ticket. Prototype screenshots and actual accessibility checks precede backend polish. The [design specification](ai/design.md) makes that direction concrete.

## Planned versus implemented

| Item | Actual status |
|---|---|
| Taste Duel requirements, architecture, rules, design and sequence | Rewritten for the pivot in Prompt 1 |
| Existing AccessLife source | Recoverable at the checkpoint below; unused old planner/map web modules removed after replacement checks. Legacy backend/cloud unchanged |
| Taste Duel fixture frontend | Server shell, reusable tokens/primitives, React Aria confirmation, discriminated state machine and in-memory adapter; five invented rounds, accepted-answer score, save/unsave and local invitation |
| Prompt 4 verification | 10 state/adapter/disclosure tests and TypeScript passed; 13 affected Playwright checks passed, including full keyboard games at all three widths. 39 full axe scans found zero violations; 39 captures include accepted evidence, long titles, missing art and ranking semantics. Six unaffected cancellation/state-story checks retain their earlier passes |
| Taste Duel API/database foundation | Separate `tasteduel` domain, sessions, owned reads, private snapshots/pools/receipts, PostgreSQL constraints/RLS and separate migration/runtime roles; actual application OpenAPI generates frontend declarations |
| Prompt 6 provider transport | Official harness `0.1.26` / Node `24.18.1`, exact discovered schemas, typed six-state normalization, ambiguity choices, bounded stdio lifecycle and shared PostgreSQL admission; no raw-HTTP fallback |
| Prompt 6 verification boundary | Synthetic contracts, real local SQL controls and packaged offline checks; **zero live Qloo calls**, no Secret Manager payload access. Compact score precedence/default ordering remain unverified and `ordering_verified=false` |
| Prompt 6 actual checks | 283 isolated backend tests passed, including 126 new provider/lifecycle/policy/security checks; Ruff/OpenAPI drift passed. New image built; network-none/read-only UID10001 harness discovery, API liveness/OpenAPI/unconfigured readiness and bounded SIGTERM smoke passed |
| Prompt 7 offline pool | Validated frozen-context candidates, exact five-round/continuation feasibility, bounded category/band objective, stable sides/IDs and private feedback; no new endpoint or game mutation |
| Prompt 7 real-data gate | Blocked: no retained normalized candidate samples and no verified canonical MCP ordering. No new provider/model/Secret Manager calls or cloud/DB changes |
| Prompt 7 actual checks | 159 targeted tests passed: 99 new engine/bridge/fairness checks plus 60 existing provider contracts; Ruff and application OpenAPI drift passed. No new visual/runtime/cloud acceptance claim |
| Prompt 5 verification | Clean PostgreSQL 16 migration chain `td0001`–`td0004`; 157 checks passed, including real database constraints and HTTP secrecy/isolation; Ruff, TypeScript and OpenAPI drift passed. Final evidence is under `.data/tasteduel-prompt5/` |
| Live search, generation, authoritative answer/Next/save mutations, public replay and RoundCuratorAgent | Contracts declared; unconnected operations return honest `501 FOUNDATION_NOT_IMPLEMENTED`. No full game engine, durable browser gameplay or live integration claim |
| Qloo feasibility and rights | Pinned harness `0.1.26`; offline discovery and two raw cross-domain samples passed within **12/12** requests. Canonical MCP Insights, same-domain cells, nested explanation semantics and broad coverage remain unverified; [full matrix](ai/qloo-capability-matrix.md) |
| Prompt 2 synthetic verification | 22 tests passed; Ruff passed. No production game, accessibility, restart or cloud readiness claim |
| Prompt 3 local production-build verification | 12 Playwright tests passed across 1440×1000, 390×844 and 320×844; 27 full axe scans found zero violations; 30 screenshots captured, with core states and layout edge cases visually reviewed |
| Taste Duel images and fonts | Four original SVGs; locally hosted Barlow Condensed/Manrope with OFL notices and immutable provenance. [Asset manifest](third_party/taste-duel-assets.md) |
| Taste Duel live URL, repository rename and GCP cutover | Not performed; reserved for later migration prompts |
| Historical AccessLife verification | Recorded in [memory](ai/memory.md); not rerun or relabelled as Taste Duel verification |

There is no Taste Duel production URL yet. Local preview: **http://127.0.0.1:3001**. The previously recorded [AccessLife endpoint](https://accesslife-web-dfthmgvvaa-el.a.run.app) remains a legacy deployment reference; its health was not rechecked in this frontend iteration.

## Run the isolated API/database foundation

Use Python 3.12, uv and running Docker Desktop. This workflow targets only a
new loopback-bound PostgreSQL 16 container at `127.0.0.1:55435/tasteduel_prompt5`.
It refuses the legacy database, remote hosts and the wrong database role. The
existing Compose stack is not used. No provider credentials or ADC are needed.

```powershell
uv sync --locked
uv run --no-sync python scripts/tasteduel_local.py start
uv run --no-sync python scripts/tasteduel_local.py migrate
uv run --no-sync python scripts/tasteduel_local.py test -q
corepack pnpm contracts
uv run --no-sync python scripts/export_contracts.py --check
corepack pnpm typecheck
uv run --no-sync python scripts/tasteduel_local.py api
# API documentation: http://127.0.0.1:8002/docs ; Ctrl+C stops the API.
# Then stop the dedicated database without deleting its data:
uv run --no-sync python scripts/tasteduel_local.py stop
```

The helper generates local-only credentials in process memory and dedicated
Docker container configuration, never repository credential files or command
arguments. Docker stores its own metadata locally. It neither reads nor copies
real provider keys. Runtime has DML/RLS privileges; the separate migration owner
owns schema changes. See the [migration guide](apps/api/tasteduel_migrations/README.md).

Actual private routes use `/v1`; the declared browser base `/api` gives
`/api/v1`. The web forwarding boundary remains disabled until integration.
Sessions, health and owned game/current-round/result/discovery reads are
implemented. Tests seed synthetic private database graphs directly; this is
not an implemented generation or answer service. Asking for an already answered
playable round returns 409; an owned game read restores that accepted reveal.
Other guests receive uniform 404s. Receipts, future pools, ranks, affinities and
raw cache payloads never become public response models.

Python/Pydantic is the single wire-contract source. `contracts` exports the
actual application OpenAPI and regenerates `apps/web/src/lib/api/schema.d.ts`;
the rejected upstream Qloo meta-schema is not involved. Fixture/presentation
types remain UI-only. [API foundation details](apps/api/README.md) distinguish
declared success contracts from handlers still returning 501.

Prompt 5 evidence belongs in ignored `.data/tasteduel-prompt5/`. Its checks do
not validate live Qloo/Vertex, cloud connectivity, public replay or restart-safe
mutation execution. Prompt 6's provider controls are described below.

## Private Qloo runtime - Prompt 6

Prompt 7 adds a pure deterministic engine behind this boundary; it does not
enable provider mode or connect the browser. See the [pool guide](apps/api/DUEL_POOL.md).

```powershell
npm.cmd ci --prefix runtime/qloo --ignore-scripts --no-audit --no-fund
uv run --no-sync python scripts/tasteduel_qloo_offline.py
docker build -f infra/containers/tasteduel-api.Dockerfile -t tasteduel-api:prompt6 .
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges tasteduel-api:prompt6 python scripts/tasteduel_qloo_offline.py
```

These checks need no credentials and make no upstream calls. The new image
contains only the Taste Duel Python modules plus separately locked minimal
Python/Node runtimes; it does not replace the legacy Compose/CI image. It runs
as UID 10001. Default provider configuration is disabled and health does not
claim game generation is available.

When explicitly enabled server-side with `TASTEDUEL_QLOO_ENABLED=true`, API
startup resolves the existing Secret Manager **reference**, through server ADC,
into memory and forwards only the Qloo key to one managed child. No key value
belongs in source, browser configuration, command arguments or an image layer.
This credential lookup was not exercised in Prompt 6. See the
[runtime guide](runtime/qloo/README.md) for the exact reference, lifecycle and
remaining live gate.

Callers must wrap an entire generation in `port.request_budget(...)`: at most
six actual upstream requests and twenty seconds across resolution, hydration,
ranking and one eligible retry. Missing budgets fail closed. PostgreSQL stores
only key fingerprints/counters/circuit flags for admission: default thirty
requests/minute, 200 ms minimum spacing, three transient failures opening the
circuit for thirty seconds, and sticky authentication failure until key rotation
or a reviewed operator repair. These are engineering limits, **not** Qloo's
advertised quota. All Taste Duel instances must share this database. An old
AccessLife runtime bypasses this control and must be stopped or coordinated
before a shared-key live rollout; this stage makes no cloud changes.

Raw provider payloads remain process-local; no live data/cache was retained.
The port returns private typed values, never generic JSON to React. It withholds
unreviewed explanations and image rights claims. Live canonical Insights,
same-domain coverage and compact-versus-raw score semantics remain the precise
[Prompt 2 gaps](ai/qloo-capability-matrix.md). Its budget remains **12/12**;
Prompt 6 consumes **0** additional calls. Prompt 7 now supplies the offline
deterministic engine; genuine pool readiness stays gated on those live checks.

## Check the deterministic engine - Prompt 7

```powershell
uv run --no-sync python scripts/tasteduel_pool_check.py --synthetic
uv run --no-sync python -m pytest -c pytest.tasteduel.ini --confcutdir=tests/tasteduel tests/tasteduel/duel_pool tests/tasteduel/duel_pool_review -q
```

No database, credentials, model or network is needed. The demonstration clearly
labels invented data and prints aggregate validation facts. Local artifacts are
`.data/tasteduel-prompt7/{synthetic-report.json,tests.xml,verification.json}`.
The [engine guide](apps/api/DUEL_POOL.md) specifies policy, rejection accounting,
safe feedback and the blocked real-sample gate. No frontend/screenshots changed.
Next numbered step is Prompt 8; live capability/sample proof is still required
before dependent genuine-agent integration.

## Run the development fixture game

Node 24 with Corepack is sufficient; no Docker, database, ADC or API key is needed.

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm dev:fixtures
# Open http://127.0.0.1:3001 ; Ctrl+C stops the preview.
```

The launcher explicitly enables `TASTEDUEL_FIXTURES=1` for Next's development
server. `dev:prototype` is a compatibility alias. Confirm a seed on `/`, then
complete `/g/demo` to unlock `/results/demo` and `/c/demo` in the same app
session. Ten unique invented contestants fill five rounds; the result is
computed from accepted answers. All-first-card choices currently produce 3/5,
but choosing other cards changes that score. Refresh clears progress and saves;
opening a result directly never invents a completed game.

Development stories: `/prototype/empty`, `/prototype/partial`,
`/prototype/retry`, `/prototype/expired`, `/prototype/interrupted`,
`/prototype/long-title`, `/prototype/missing-image`, `/prototype/preparing`,
`/prototype/pending`, `/prototype/selected`, `/prototype/submitting` and
`/prototype/disabled`. `/g/demo?story=retry` exercises an accepted answer whose
response is lost; Retry reuses the same answer request without another point.
Short pools explain why five rounds cannot start. Static selected/pending
stories explicitly disclose that no task is running. `/how-it-works` explains
aggregate ranking versus personal preference. Sound is absent and unnecessary.

After an accepted answer, open **Why this duel?** for the explicitly synthetic
ranking context, optional save actions and a compact fixture curation summary.
No Qloo or agent was called. This reusable evidence component has a source,
factual context and optional supported-explanation slot; no cultural cause is
invented. The summary projects only safe aggregate preparation facts. Neither
surface appears before acceptance or reveals future contestants/answers.
Correct/incorrect predictions are game performance, not personal taste.

```powershell
corepack pnpm typecheck
corepack pnpm test:fixture-state
corepack pnpm test:fixtures
# Browser tests require the explicit dev fixture server on port 3001.
# Stop dev before the production checks below:
corepack pnpm build
corepack pnpm check:fixture-production
corepack pnpm start:prototype
```

**Production builds exclude the fixture implementation.** The Next configuration
selects it only during `PHASE_DEVELOPMENT_SERVER` with the explicit flag. All
other phases resolve the entry to a separate unavailable module, including a
production build with `TASTEDUEL_FIXTURES=1` set. Production displays an honest
unavailable landing page; game/result/challenge/story routes return 404 and no
fixture controls are rendered. The emitted-output check rejects known fixture
data/control markers. `start:prototype` serves this production boundary, not the
fixture game. Use `dev:fixtures` to play locally.

Tests reject browser requests to external hosts or `/api/`. The existing API
stub returns `503 PROTOTYPE_ONLY` and cannot contact AccessLife/Qloo/GCP.
Idempotent retries, cancellation tokens and duplicate guards belong to the
local fixture adapter; they do not prove database concurrency, server ownership
or restart recovery. The synthetic answer key is client code only in explicit
development mode. Genuine backend integration remains later work.

Current journey screenshots/axe/geometry evidence: `test-results/tasteduel-fixtures-final/`;
HTML report: `playwright-report/tasteduel-fixtures/index.html`. How-it-works and
motion-equivalence checks have separate `tasteduel-fixtures-how` and
`tasteduel-fixtures-motion` artifact/report folders. Earlier unchanged
cancellation and state-story coverage remains in `test-results/tasteduel-fixtures/`.
Review and production-boundary evidence: ignored `.data/tasteduel-prompt4/`.
Prompt 3 captures remain under `.data/tasteduel-prompt3/`; its old isolated
suite is historical and does not describe the full fixture journey.

Prompt 3's standalone build passed. Its checks covered keyboard seed selection/reveal,
focus transfer, local font loading, reduced motion, 48px interactive targets,
320px overflow, 200% root-font text scaling and an actual aborted SVG request
before hydration. Visual review corrected desktop action placement, mobile
headline sizing, clipped fallback content and the seam between unequal stacked
cards. Computed enabled-action contrast is 16.70:1. Human screen-reader testing,
actual browser zoom, other browser engines and real-user playtesting remain
unverified. The Compose stack/CI are legacy and were not validated as Taste
Duel delivery infrastructure.

## Execute one iteration at a time

The source of execution instructions is [ai/prompts.md](ai/prompts.md), containing 21 bounded prompts with agent ownership and completion gates. **Next numbered step: Prompt 8 - bounded curator**, with the real-sample/canonical-order gate still blocked before dependent live integration. Prompt 7's offline deterministic checks do not close it. Prompt 2 used exactly twelve Qloo requests; Prompts 3-7 add zero live calls or Secret Manager payload access. Do not reset the exhausted budget on resume or in a clean clone.

Read its shared requirements, then paste the complete numbered prompt. Do not run all prompts as a single implementation request. Independent synthetic visual work can proceed during a provider outage, but it cannot pass the genuine integration gate.

| Document | Purpose |
|---|---|
| [prd.md](ai/prd.md) | Audience, game journeys, MVP requirements, acceptance and later scope |
| [Architecture.md](ai/Architecture.md) | Fresh modules, contracts, agent/data boundaries and GCP migration target |
| [rules.md](ai/rules.md) | Stack, winner authority, secrecy, source rights, failures and testing |
| [phases.md](ai/phases.md) | All 21 iterations, dependencies, gates and legacy-removal schedule |
| [design.md](ai/design.md) | Visual tokens, screen hierarchy, interactions and accessibility |
| [memory.md](ai/memory.md) | Historical AccessLife outcomes and dated Taste Duel progress |
| [prompts.md](ai/prompts.md) | Copy/paste execution instructions from scratch through production |
| [qloo-capability-matrix.md](ai/qloo-capability-matrix.md) | Dated provider/source pins, bounded capability evidence and rights/retention policy |

Only these eight `/ai` Markdown files are eligible for publication. Original references, environment values, private provider responses, state, datasets and artifacts remain ignored. Keep dependency lockfiles. Do not force-add ignored credential or capture files.

## Target implementation

Next.js App Router, strict TypeScript, Tailwind, React Aria and planned Motion; FastAPI/Pydantic, SQLAlchemy/Alembic and ordinary PostgreSQL 16. One bounded Vertex-powered `RoundCuratorAgent` will use the implemented private Qloo port. Deterministic validators, the game engine and database transactions will own eligibility, winners and score. Motion is not installed. Harness `0.1.26` is now pinned in `runtime/qloo` and packaged with Node24.18.1 in the isolated backend image; its live ordering gate remains open. Vertex model access is deferred to Prompt 8.

The target GCP deployment is public Cloud Run web -> same-origin forwarding -> private Cloud Run API -> Cloud SQL, Qloo and Vertex. Qloo/database secrets stay in Secret Manager; Vertex and GitHub Actions use IAM/WIF. A bounded game-generation request completes before returning a ready game; retries use durable reservations/leases. No post-response in-memory worker assumption.

Pre-answer DTOs contain only playable choices. After a server-accepted answer, a separate reveal DTO can disclose that answered round only. Neither public invitations nor HTML/RSC/JavaScript/social previews expose future winners, rankings or private pools. Answer/Next/replay use stored evidence and make no new Qloo/LLM calls.

The new game needs no RAG, ingestion/chunking, embeddings, vector database, maps, transport or separate planning worker. Prompt 3 removes six unused legacy web modules and seven obsolete direct web dependencies, after the new shell's checks. Legacy Python/runtime/container files remain until their later replacement gates; the [removal plan](ai/phases.md) records this boundary.

## Data and artwork boundaries

Qloo is the sole ranking authority. Its entity images and optional explanations are used only when available and permitted. An image URL alone does not license redistribution, mirroring or social-card reuse. Original SVG/CSS/typographic covers are the baseline fallback; TMDB, Wikidata or selected Commons assets are optional after permission and attribution checks. No arbitrary image scraping or fake posters representing named films.

Retention and challenge expiry must follow applicable source/event terms. Store only needed private evidence with expiry; do not rebuild Qloo's catalogue or publish real responses. Expired evidence expires the challenge rather than silently changing its answer key. See [rules](ai/rules.md) and the source matrix in [architecture](ai/Architecture.md).

## AccessLife checkpoint and source recovery

| Baseline | Value |
|---|---|
| Branch / origin | `main` / `https://github.com/saimaharana4/accesslife-ai.git` |
| Preserved HEAD | `86d4ef677ae7dba93bf0211e4348d7c29284a948` |
| Local annotated tag | `accesslife-before-taste-duel-2026-10-24` |
| Last application-code commit | `f6236dbc12d75e4c549ec65059ebcb8e8a014c30` |
| Prior application CI evidence | [Run 40071609074](https://github.com/saimaharana4/accesslife-ai/actions/runs/40071609074), historical result; not rerun here |
| Initial tracked working tree | Clean, 90 tracked files; existing `ai/prompts.md` was ignored and is now allowlisted |

The checkpoint tag is local and has not been pushed in Prompt 1. Git history contains the old implementation; no parallel active copy or extra application build context was created. Inspect its original README without changing the checkout:

```powershell
git show accesslife-before-taste-duel-2026-10-24:README.md
git rev-parse 'accesslife-before-taste-duel-2026-10-24^{commit}'
```

The existing `scripts/dev.ps1`, Compose stack, application E2E suite and cloud workflows still describe legacy backend integration and are **not** the new fixture frontend's startup/verification path. Use the commands above and isolated `test:fixtures` suite. Legacy CI has not been migrated or run as Taste Duel CI; no push was made to trigger it. Container/CI replacement remains Prompt 14.

For source rollback, inspect the tag or use an explicitly isolated worktree outside the new build context; do not hard-reset user work or roll back a live database automatically. [Legacy operations](infra/README.md) and [legacy cost review](infra/COST_REVIEW.md) remain AccessLife baseline documents until their migration stages.

Original local reference preservation manifest (SHA-256):

| Ignored reference under `ai/` | SHA-256 |
|---|---|
| `AccessLife_AI_Design_Document_v4.docx` | `e61c32f86982a7ba9c6e435c2bf79c2aaac1d302153c2e5fdb5cde0222698a2a` |
| `deep-research-report.md` | `5f930e822f27902129f797e69155a40196ba956428895f5cc023f5562105b52b` |
| `qloo_rules.md` | `335c8f41138f01dca034376855fec08ece3d603b4d295018beeba7dbd95b5a33` |

They remain local and byte-for-byte preserved. Runtime must not depend on these ignored files.

## GCP migration boundaries

The recorded project is `project-bb13ecd8-9d67-408d-9a7`, region `asia-south1`. Prompt 1 does not query or change cloud resources, secret values, traffic, repository identity or IAM.

Later prompts inventory the dedicated AccessLife resources and plan new `tasteduel-web`/`tasteduel-api` services plus a new logical database on the existing dedicated SQL instance. Retain immutable-name exceptions and Terraform ownership explicitly. A SQL instance, bucket or secret ID cannot be renamed by changing a display label. Do not create another continuously billed SQL instance for cosmetic naming, destroy the old database during a resource rename, or touch unrelated PharmaGuard workloads.

The historical US$78.48 estimate through 5 November is **not** a current estimate or a fresh pivot allowance. The US$80 incremental envelope includes prior incurred AccessLife spend, remaining shared infrastructure, overlap and Taste Duel. Refresh it through at least **6 November 2026, 10:15 IST**, plus required follow-up. Stop provisioning if that total does not fit; budget alerts are notifications, not caps.

Repository rename/WIF and cloud foundation are Prompt 17; candidate release is Prompt 18; public cutover is Prompt 19; legacy retirement follows its preservation gate in Prompt 20. No new GCP migration is complete today.

## Licence and release

Project source/docs use [MIT](LICENSE). Provider output, artwork, fonts and existing [third-party notices](third_party/README.md) have separate terms. A source licence does not grant rights to external media or Qloo data.

Hackathon dates and submission requirements are rechecked before release. The plan targets 31 October 2026, 09:15 IST submission and judging access through 6 November 2026, 10:15 IST, subject to the official rules and required follow-up. Functional public Taste Duel, real Qloo integration, licensed source and factual release evidence remain future gates.

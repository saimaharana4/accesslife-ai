# Taste Duel

One favourite. Five duels. Predict Qloo's ranking, discover something surprising, then challenge a friend to the same five rounds.

**Status - 25 October 2026: Taste Duel has a local visual prototype (Prompt 3), using explicitly fictional content.** It includes seed selection, one sample duel/reveal, a result-ticket specimen, a challenge invitation and loading/error designs. It is not a complete five-round game or live Qloo integration. Prompt 2 remains partial: raw cross-domain samples passed, while canonical MCP Insights and same-domain cells remain unverified. Backend, containers and GCP deployment remain legacy AccessLife; no cloud provisioning, deployment or repository rename occurred.

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
| Taste Duel UI | New server shell, local fonts, original SVG art, React Aria synthetic seed chooser and one interactive sample reveal; result/invitation are labelled specimens |
| Taste Duel API, five-round engine, persistence, real sharing and RoundCuratorAgent | Planned; not implemented or tested |
| Qloo feasibility and rights | Pinned harness `0.1.26`; offline discovery and two raw cross-domain samples passed within **12/12** requests. Canonical MCP Insights, same-domain cells, nested explanation semantics and broad coverage remain unverified; [full matrix](ai/qloo-capability-matrix.md) |
| Prompt 2 synthetic verification | 22 tests passed; Ruff passed. No production game, accessibility, restart or cloud readiness claim |
| Prompt 3 local production-build verification | 12 Playwright tests passed across 1440×1000, 390×844 and 320×844; 27 full axe scans found zero violations; 30 screenshots captured, with core states and layout edge cases visually reviewed |
| Taste Duel images and fonts | Four original SVGs; locally hosted Barlow Condensed/Manrope with OFL notices and immutable provenance. [Asset manifest](third_party/taste-duel-assets.md) |
| Taste Duel live URL, repository rename and GCP cutover | Not performed; reserved for later migration prompts |
| Historical AccessLife verification | Recorded in [memory](ai/memory.md); not rerun or relabelled as Taste Duel verification |

There is no Taste Duel production URL yet. Local preview: **http://127.0.0.1:3001**. The previously recorded [AccessLife endpoint](https://accesslife-web-dfthmgvvaa-el.a.run.app) remains a legacy deployment reference; its health was not rechecked in this frontend iteration.

## Run the visual prototype

Node 24 with Corepack is sufficient; no Docker, database, ADC or API key is needed.

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm dev:prototype
# Open http://127.0.0.1:3001 ; Ctrl+C stops the preview.
```

Preview routes: `/`, `/g/demo`, `/results/demo`, `/c/demo`, `/how-it-works`,
`/prototype/loading` and `/prototype/error`. Use
`/g/demo?variant=long-title-missing-image` for the long-title/fallback specimen.
Selecting another fictional seed updates the arena context. The result's 3/5 is
an illustrative specimen, not a score calculated from the sample round.

```powershell
corepack pnpm typecheck
corepack pnpm build
corepack pnpm test:prototype
# Tests require the preview already running on port 3001.
# For a local production-build preview, stop dev first, then:
corepack pnpm start:prototype
```

Prototype tests use only local assets and reject browser requests to external
hosts or `/api/`. The old forwarding route now returns `503 PROTOTYPE_ONLY` and
cannot contact AccessLife/Qloo/GCP. Answer and reveal state are disposable local
UI state; refresh resets the specimen. There is no saved game, real score,
challenge link or production answer-secrecy claim. The full fixture journey is
Prompt 4; genuine backend integration comes later.

Screenshots/axe/geometry/font evidence: `test-results/tasteduel-prototype/`;
HTML report: `playwright-report/tasteduel-prototype/index.html`.
First/second visual passes and final review notes are under ignored
`.data/tasteduel-prompt3/`. Verification outcomes below distinguish automated
text scaling from actual browser zoom and screen-reader user testing.

The final standalone build passes. Checks cover keyboard seed selection/reveal,
focus transfer, local font loading, reduced motion, 48px interactive targets,
320px overflow, 200% root-font text scaling and an actual aborted SVG request
before hydration. Visual review corrected desktop action placement, mobile
headline sizing, clipped fallback content and the seam between unequal stacked
cards. Computed enabled-action contrast is 16.70:1. Human screen-reader testing,
actual browser zoom, other browser engines and real-user playtesting remain
unverified. The current CI/containers are legacy and were not validated as Taste
Duel delivery infrastructure.

## Execute one iteration at a time

The source of execution instructions is [ai/prompts.md](ai/prompts.md), containing 21 bounded prompts with agent ownership and completion gates. **Next: Prompt 4 - complete five-round fixture frontend.** Resolve the recorded Prompt 2 MCP/coverage gaps under a separate small budget before dependent provider/game integration. Prompt 2 used exactly twelve Qloo requests; Prompt 3 makes zero Qloo/Vertex/Secret Manager calls. Do not restart Prompt 2's exhausted budget on resume or in a clean clone.

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

Next.js App Router, strict TypeScript, Tailwind, React Aria and Motion; FastAPI/Pydantic, SQLAlchemy/Alembic and ordinary PostgreSQL 16. One bounded Vertex-powered `RoundCuratorAgent` will use the official Qloo harness through a normalized provider port. Deterministic validators, the game engine and database transactions own eligibility, winners and score. Motion is not installed; harness `0.1.26` was inspected only in an ignored isolated spike directory, not added to the application runtime. Vertex model access is deferred to Prompt 8.

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

The existing `scripts/dev.ps1`, Compose stack, application E2E suite and cloud workflows still describe legacy backend integration and are **not** the new prototype's startup/verification path. Use the commands above. Legacy CI has not been migrated or run as Taste Duel CI; use the isolated `test:prototype` suite. Container/CI replacement remains Prompt 14.

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

# Taste Duel

One favourite. Five duels. Predict Qloo's ranking, discover something surprising, then challenge a friend to the same five rounds.

**Status - 24 October 2026: Prompt 1 preservation is complete; Prompt 2 has a partial capability gate. Taste Duel application development has not started.** Two genuine cross-domain samples prove a five-round numeric pool is feasible for tested artist/movie seeds, using an explicit raw diagnostic. Canonical MCP Insights and same-domain rankings remain unverified. Application code, containers, deployment configuration and the existing deployment still belong to AccessLife AI; the new isolated probe/tests do not replace them. No cloud provisioning, deployment or repository rename occurred.

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
| Existing AccessLife source | Preserved unchanged at the checkpoint below; no new active copy added |
| Taste Duel UI, API, game engine, database and RoundCuratorAgent | Planned; not implemented or tested |
| Qloo feasibility and rights | Pinned harness `0.1.26`; offline discovery and two raw cross-domain samples passed within **12/12** requests. Canonical MCP Insights, same-domain cells, nested explanation semantics and broad coverage remain unverified; [full matrix](ai/qloo-capability-matrix.md) |
| Prompt 2 synthetic verification | 22 tests passed; Ruff passed. No production game, accessibility, restart or cloud readiness claim |
| Taste Duel images and fonts | Proposed sources; usage/licence and rendered checks remain pending |
| Taste Duel live URL, repository rename and GCP cutover | Not performed; reserved for later migration prompts |
| Historical AccessLife verification | Recorded in [memory](ai/memory.md); not rerun or relabelled as Taste Duel verification |

There is no Taste Duel production URL yet. The previously recorded [AccessLife endpoint](https://accesslife-web-dfthmgvvaa-el.a.run.app) is a legacy deployment reference, not the new game; its current health was not rechecked in this documentation-only iteration.

## Execute one iteration at a time

The source of execution instructions is [ai/prompts.md](ai/prompts.md), containing 21 bounded prompts with agent ownership and completion gates. **Next independent step: Prompt 3 - original visual prototype with labelled synthetic data.** Resolve the recorded Prompt 2 MCP/coverage gaps under a separate small budget before dependent provider/game integration. The current iteration used exactly twelve Qloo requests and zero Vertex calls; do not restart its exhausted budget on resume or in a clean clone.

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

The new game needs no RAG, ingestion/chunking, embeddings, vector database, maps, transport or separate planning worker. Existing dependencies and runtime files remain until their replacement gates pass; the exact [removal plan](ai/phases.md) prevents breaking the preserved app halfway through the pivot.

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

The existing startup script still launches **AccessLife**, not Taste Duel:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
# Existing AccessLife web: http://localhost:3000
# Existing AccessLife API docs: http://localhost:8000/docs
docker compose down
# Preserve the database volume; do not add -v.
```

These commands were inspected, not executed as Taste Duel verification. For a later source rollback, inspect the tag or use an explicitly isolated worktree outside the new build context; do not hard-reset user work or roll back a live database automatically. [Legacy operations](infra/README.md) and [legacy cost review](infra/COST_REVIEW.md) remain AccessLife baseline documents until their migration stages.

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

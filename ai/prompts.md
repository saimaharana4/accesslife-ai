# Taste Duel: build from scratch, one prompt at a time

Prepared: 24 October 2026. Delivery type: execution prompts, not an implemented pivot.

This file supersedes the AccessLife product direction **for future Taste Duel work**. It does not claim the existing app or GCP resources have changed. Execute one numbered prompt per iteration, in order. Do not paste the entire sequence as one build request. Each prompt instructs Codex to read this file, so its shared requirements continue to apply when a prompt is pasted separately.

The source brief is the user's attached Taste Duel architecture note. Its useful principles are retained; unsupported percentile claims, universal affinity thresholds, automatic image rights, excessive infrastructure and ambiguous challenge behavior are corrected below.

## How each iteration must run

- You are the lead Codex engineer. Use every available Codex agent slot for useful independent work. In a four-slot environment, use the lead plus three subagents; rotate specialist roles in subsequent waves. Do not exceed available concurrency or invent a swarm of deployed application services.
- Assign explicit owners, paths, prerequisites and acceptance checks before agents edit. Parallelize independent tasks, keep shared contracts and migrations coordinated, and have an agent who did not author a change review it. The lead integrates, runs the actual checks and resolves disagreements.
- Specialist roles across the sequence: product/visual design, frontend interaction, Qloo/data research, game/agent logic, API/database, GCP/release, and independent accessibility/security review. A role is a responsibility, not necessarily another running agent or deployed service.
- Start with the current repository state and previous gate results. Do not reset Git, overwrite unrelated changes or assume a previous test is still valid after changing its implementation.
- Complete only the selected prompt. Do not provision cloud resources during local prompts, skip ahead to production, or keep implementing later stages without a separate instruction.
- Make routine reversible implementation decisions autonomously. Do not request repeated permission already supplied by the chosen prompt. Stop only the dependent work when a real requirement is missing, a cost gate fails, or an action would destroy data outside the authorized migration; explain the exact blocker and continue independent work.
- A failed gate is not completion. Fix it within that iteration or record the concrete blocker. Do not silently reduce five rounds, replace genuine Qloo with fixtures, weaken accessibility checks or call untested cloud deployment successful.
- Finish with: changed files; runnable commands and URL where applicable; checks actually run with results; screenshot/artifact locations; unresolved limitations; and the next prompt number. Update the maintained specs and append one or two factual lines to `ai/memory.md` during implementation iterations.
- Screenshots and test artifacts containing private data belong in ignored local artifacts. Synthetic fixtures must be recognizably synthetic. Never commit live Qloo response captures.
- No messages, outreach, Devpost submission or purchases are authorized merely by these prompts. Prepare reviewable materials; sending/submitting them requires the user's instruction.

## Product contract: the experience we are building

**Taste Duel is a web game: choose one favourite, predict five Qloo comparisons, discover something surprising, then challenge a friend to the same five rounds.**

The question is: **"Which ranks higher for this seed in Qloo's taste graph?"** A player's preferences are not right or wrong. Qloo supplies a ranking for a specific request, not universal cultural truth, a psychological diagnosis or a probability of individual enjoyment.

MVP launch scope:

1. Guest play without accounts, an actual typed entity search and unambiguous seed selection.
2. Music-artist and movie seed support; movie and music-artist target rounds, subject to the live coverage gate. Book/person seeds and book rounds are additions only after their own coverage and metadata checks. Do not assume a director's name is a movie entity.
3. Five solo rounds selected adaptively from a small validated pool. No entity repeats in a played game; difficulty labels are versioned game heuristics, not Qloo confidence levels.
4. Server-authoritative answers, one point per correct prediction, a maximum score of five and an optional streak display. No speed-based scoring or fake global percentiles.
5. Immediate selection feedback, clear answer reveal, an explicit Next action and a result ticket showing the real score and discoveries.
6. A share link that freezes the creator's **actual five played rounds**, order, sides, question context, answer key and scoring version. A friend's replay is fixed, not independently adaptive. Compare scores only for that challenge/version, not different solo runs.
7. A lightweight discovery save/unsave list within the guest session. It is not a second social network or account system.
8. Honest no-coverage, provider-unavailable, interrupted-game, expired-challenge and artwork-failure experiences.
9. Mobile and desktop browser use only. No native app, bookings, maps, transport, accessibility routing or multi-city planner.

A cross-domain round must actually cross domains. A musician seed leading only to other musicians is not evidence of the cross-domain feature. Both contestants in a duel must be the same target type and come from the same frozen ranking context. The five rounds may use multiple independently snapshotted target domains; never compare a movie score against an artist score.

### Corrections that every implementation prompt must preserve

- Do not use the attachment's invented "better than 84%" or sample audience percentages. Achievement names, if present, are clearly game rewards derived from the player's score.
- Determine actual wire score units and ordering from the tested Qloo/harness response. Do not assume all values are 0–1, multiply them into percentages, or claim 0.83 means an 83% enjoyment chance. Prefer rank wording in the main UI and explain raw values only when their semantics are established.
- Reject ties, near-ties, missing/nonfinite scores when required by the verified contract, ambiguous identity, self-pairs, duplicate entities and contradictory ranking metadata. Do not manufacture winners from arbitrary list order if it is not verified affinity ordering.
- Calibrate pair difficulty from actual returned distributions and player observations. Fixed deltas such as 0.20/0.08/0.02 are examples, not accepted universal thresholds or calibrated probabilities.
- Before a guess is accepted, never expose the winner, ranks, affinities, revealing explanation, remaining round pool or correct-answer-dependent URL through JSON, HTML, RSC payloads, JavaScript bundles, prefetch, logs exposed to users, social cards or analytics. The browser receives only the current playable round's public fields. Public choice order must be independent of upstream rank; use opaque round IDs and preserve the chosen side order in the snapshot.
- Answer submission and Next must not call Qloo or an LLM. Generate the pool before gameplay and score against stored evidence.
- The agent may curate and request data. Deterministic validators and persisted Qloo ordering determine the answer. An LLM must never create affinities, winners or unsupported causal explanations.
- If Qloo cannot produce enough valid rounds, explain that and offer another seed. A labelled synthetic UI demo is useful during development but is not the live product or submitted integration.

## Visual contract: design is a first-class deliverable

Direction: **cultural fight-night editorial**. Use a confident typographic wordmark, oversized artwork, a central DUEL seam, a compact five-round progress indicator and a result ticket worth sharing. The game itself is the hero.

Initial tokens, verified in rendered use before freezing:

| Role | Starting choice |
|---|---|
| Canvas | Ink `#101014` |
| Reading/card surface | `#1B1B23`, opaque where text needs it |
| Main text | Warm paper `#F4F1EA` |
| Primary action | Electric chartreuse `#DBFF5E`, ink text |
| Secondary accent | Muted lavender `#B9A9FF` |
| Error/incorrect | Soft coral `#FF9A9A`, plus text/icon |
| Display type | Locally hosted licensed Barlow Condensed or a verified equivalent |
| Reading type | Locally hosted licensed Manrope or a verified equivalent |
| Type scale | Fluid display approximately 48–112 px; body 18 px; useful metadata 14–16 px |
| Controls | Minimum 48 px primary hit area; visible focus and readable labels |
| Motion | Selection 120–180 ms; reveal at most 450 ms; opacity/transform preferred |

These are starting specifications, not a claim that arbitrary colour combinations pass contrast. Use at most two font families and three necessary weights, ship their licence notices, and inspect screenshots with fonts actually loaded. Keep titles readable outside images; do not crop away identifying text or rely on poster lettering.

Build these routes and shared components:

```text
Server AppShell
  Wordmark / HowItWorks / optional SoundOff (default off)
  /                    LandingSeedStage
                         SeedCombobox / SeedResults / ExampleSeeds / StartDuel
  /g/[gameId]          DuelArena
                         SeedChip / RoundPips / Question
                         ChoicePair -> ChoiceCard x2 / DuelSeam
                         RoundFeedback / ExplicitNext / SaveDiscovery
  /results/[gameId]    ResultTicket / Discoveries / ChallengeCTA / PlayAgain
  /c/[slug]           ChallengeInvitation -> same DuelArena in fixed mode
  /how-it-works       Brief semantics, attribution, privacy and limitations
```

No enterprise sidebar, dashboard tiles, chat window, generic grid of small recommendations, decorative agent graph, gradient blobs, excessive glass, perpetual confetti or mandatory WebGL. Use original composition, not copied product trade dress. Artistic references may inform composition but do not license someone else's assets.

At 390 px, two choices can sit side by side if titles and targets remain readable; at 320 px stack when necessary. Never require landscape. Support keyboard, screen readers, high zoom and reduced motion. Correctness cannot depend on colour, animation or sound. No automatic advance or forced timer. Keep optional celebration brief and disable it under reduced motion.

Visual acceptance requires screenshots and inspection at **390×844, 1440×1000 and 320 CSS px**, including a long-title and failed-image case. A successful build alone does not pass the visual gate. Prototype before backend polish; resolve composition problems rather than decorating the AccessLife layout.

## Data sources and agent responsibilities

Check the current official sources in the references section during Prompt 2. Source availability, licence, event quota and key expiry are verification tasks, not facts established by this file.

| Source | Use | Credentials and rights | Decision |
|---|---|---|---|
| Qloo Search/Insights via official harness MCP | Resolve entities; ranked candidates; supported explainability; artwork metadata | Existing server-side Secret Manager reference; check event terms, limits, display and retention policy | Essential; sole ranking authority |
| Original SVG/CSS/typographic artwork | Branded fallback covers, empty states, social cards | Project-owned; retain source and font licences | Essential; always available |
| TMDB | Film metadata/artwork if Qloo imagery is insufficient | Separate API credential if needed; verify noncommercial terms and required attribution/logo; do not assume commercial rights | Optional, never ranking authority |
| Wikidata | External-ID and release/type enrichment | Structured data CC0; bounded queries and provenance | Optional; no need for bulk import |
| Wikimedia Commons | A small verified set of artist/person images | Per-file licence, creator/source and any relevant additional rights | Optional; no universal media licence |

Do not add Spotify OAuth, scrape Google Images/Letterboxd, fetch arbitrary cover sites or create fake film posters attributed to real works. Image presence in `properties.image` is metadata availability, not permission to mirror, transform or put it in an OG card. Use licensed imagery or original title-based cards with their fallback nature clear. A fallback must still look intentionally designed.

Cache only what the game needs, privately and with expiry. Keep minimal ranking evidence, not a local copy of Qloo's database. Record a reviewed policy for raw responses, normalized entities, ranking snapshots, challenge lifetime, logs and backups. The official kit does not establish a universal numerical retention period; do not invent one as a licence condition. Apply the documented terms, use conservative bounded defaults where terms leave discretion, and resolve genuine restrictions with the organizer without blocking unrelated UI work. A challenge must expire no later than its evidence may be retained. Expired evidence means an expired challenge; never silently re-query and change its answer key.

### Application agents versus Codex build agents

The application starts with **one bounded `RoundCuratorAgent`**, not a collection of microservices or invented Qloo-owned agents.

| Responsibility | Implementation |
|---|---|
| Decide the next allowed target domain and whether a bounded extra lookup is useful | RoundCuratorAgent with Vertex tool calling |
| Resolve/describe a seed; recommend/rank a candidate set | Official Qloo tools through an allowlisted adapter; inspect real tool schemas |
| Normalize results and enforce data/rights/duplicate/tie rules | Deterministic `CandidateValidator` |
| Construct/diversify pairs and provisional difficulty bands | Deterministic `DuelPoolBuilder`; agent can propose selections, validator can veto |
| Persist immutable evidence and make private/public DTOs | Application service and PostgreSQL transactions |
| Select an unused next round, accept a guess and update score | Deterministic `GameEngine` |
| Write a short reveal sentence | Optional bounded generation from supported evidence; factual template fallback |
| Freeze and replay a shared challenge | Deterministic `ChallengeService` |

Expose small application tools such as `inspect_seed`, `fetch_ranked_candidates`, `validate_candidates`, `propose_pairs`, `evaluate_pool` and `finish_pool`. Actual Qloo tool names/arguments come from `listTools()` and the pinned harness. Do not pretend these application tools are official Qloo tools. A normal adaptive score update is game logic, not an autonomous agent decision.

The official Qloo MCP process is local stdio inside the trusted backend runtime. The docs MCP endpoint is a development reference, not the production data API. Pin the harness and Node runtime, start one managed process per API instance, limit concurrent calls, detect process failure, close it on shutdown and forward only required child environment variables. Never expose that process or credentials to browsers. A direct HTTP adapter can remain a separately tested escape hatch for a documented harness limitation; do not silently switch transports or reshape unsupported parameters.

## Lean technical target and migration boundary

- Fresh Taste Duel application modules and UI. Preserve the existing work in Git history/tag and the original `/ai` reference files. "From scratch" means a deliberate new design, not deletion of `.git`, credentials, unrelated data or all cloud resources.
- Web: Next.js App Router, strict TypeScript, Tailwind, accessible React Aria controls and Motion for restrained interaction. Server-render the shell; narrow client boundaries around the game. Use Zod for forms/contracts where needed, not a second conflicting API schema.
- API: FastAPI, Pydantic, SQLAlchemy and Alembic. One small Vertex tool-calling loop through Google Gen AI. Add LangGraph only if a measured/state-management need justifies it; do not preserve the RAG supervisor by default.
- Runtime baseline: Node 24 and Python 3.12, exact compatible package/container versions and committed lockfiles checked during implementation. The Python API image also needs the tested Node runtime for the official harness; no runtime package downloads through `npx`.
- Persistence: PostgreSQL 16, ordinary relational tables. **No RAG, ingestion pipeline, chunking, embeddings, MiniLM, pgvector/PostGIS dependency, Redis, Kafka, Kubernetes or new vector service.** Legacy installed extensions can remain harmlessly on the reused instance; do not drop them blindly.
- Public Next.js Cloud Run service -> thin same-origin `/api/v1` forwarding -> private IAM-protected FastAPI Cloud Run service -> Cloud SQL/Qloo/Vertex. Vertex uses IAM/ADC. Secret Manager stores sensitive values. No independent service per tool.
- Pool generation is awaited inside a bounded request initially, with a database reservation, lease and idempotency key. Complete and commit before returning a ready result; an interrupted request can be retried against the same reservation. Do not return 202 and assume post-response work survives. If measured generation cannot fit its envelope, explicitly design durable dispatch in a later justified change, not ad hoc background tasks.
- Guests use secure HttpOnly host-scoped cookies, session ownership and transactional state transitions. Share links reveal a public challenge invitation, not the creator's private game, browser cookie or future answers.
- Suggested new tree retains the useful monorepo layout while replacing the domain:

```text
apps/web/src/app/
apps/web/src/components/ui/
apps/web/src/features/{seed,duel,reveal,results,challenges,discoveries}/
apps/web/src/lib/{api,assets,telemetry}/
apps/api/src/tasteduel/{api,domain,application,agents,ports,adapters,persistence}/
apps/api/migrations/
packages/contracts/                 # Pydantic OpenAPI -> generated web types
tests/{unit,contracts,integration,e2e,security}/
infra/{containers,terraform}/
scripts/
ai/{prd.md,Architecture.md,rules.md,phases.md,design.md,memory.md,prompts.md}
```

### Existing GCP is an input to migration, not a blank account

Repository snapshot: `saimaharana4/accesslife-ai`, project `project-bb13ecd8-9d67-408d-9a7`, region `asia-south1`. Re-inventory before changing anything; these are the documented baseline, not a live inventory performed for this prompt file.

- Existing dedicated SQL instance `accesslife-db`; old logical database/user `accesslife`.
- Existing web/API/worker, old migration/ingestion/reconciliation jobs, planning queue, five-minute scheduler, registry, buckets, service accounts, WIF, alerting and monitoring.
- Secret names include `accesslife-qloo-api-key`, `accesslife-db-password`, `accesslife-database-url` and `accesslife-worker-token`. References are not credential payloads. Do not fetch or print values just to inventory names.
- Remote Terraform state is documented at `gs://accesslife-tfstate-project-bb13ecd8-9d67-408d-9a7/accesslife/state`. Do not lose its resource ownership or treat a fresh empty state as permission to recreate infrastructure.
- The previous **US$78.48 forecast through 5 November** was close to the **US$80 total incremental envelope**. It is not a fresh allocation for this pivot, and that old window does not cover the entire judging period in IST. Recalculate actual incurred AccessLife cost plus remaining shared resources, Taste Duel, temporary overlap, restore checks, builds, currency and tax through at least **6 November 2026, 10:15 IST**, plus any required follow-up. Alerts are not caps. Stop provisioning if the updated total exceeds the envelope.
- Default migration: new `tasteduel-web` and `tasteduel-api` services, new least-privilege identities and a new `tasteduel` logical database on the existing dedicated SQL instance. Do not create a second billed SQL instance solely for naming. Reuse compatible registry/state infrastructure with documented legacy-name exceptions.
- GCP project IDs, SQL instance names, bucket names and secret names cannot all be changed as display labels. Where new physical names are necessary, create/migrate/verify/retire explicitly. Do not claim a renamed label also renamed a resource ID. Keep immutable legacy names documented if replacing them would violate the budget or preservation requirements.
- Rename the repository to `saimaharana4/taste-duel` in its dedicated stage if available, preserving history. Coordinate WIF before relying on the new name; do not overwrite another repository or broaden IAM trust. Existing repo-name trust and deploy permissions will not automatically cover new resources.
- Never modify unrelated PharmaGuard workloads or perform project-wide deletion. Never destroy production data, disable shared secrets or remove SQL deletion protection as cosmetic cleanup.

## Prompt sequence and gates

| Prompt | Deliverable | Gate before proceeding |
|---|---|---|
| 1 | Pivot inventory, preservation and rewritten specs | Scope and old/new ownership explicit |
| 2 | Qloo/data/rights feasibility and capability matrix | Genuine bounded cross-domain calls work |
| 3 | Original visual prototype | Inspected mobile/desktop composition |
| 4 | Complete fixture-based game frontend | Five polished, accessible local rounds |
| 5 | Domain/API contracts and database foundation | Schema and isolation checks pass |
| 6 | Official Qloo MCP adapter | Real schemas, lifecycle and contracts verified |
| 7 | Deterministic duel pool | Valid fair pairs from frozen contexts |
| 8 | Bounded RoundCuratorAgent | Actual tool use, validator authority preserved |
| 9 | Durable game APIs | Retry/concurrency/secrecy checks pass |
| 10 | Real end-to-end game | Search -> five live-backed rounds -> result |
| 11 | Adaptation, recovery and discoveries | Stable score and resumable gameplay |
| 12 | Exact challenges and social sharing | Two sessions replay identical five rounds |
| 13 | Accessibility, performance and security | Full audits and visual review pass |
| 14 | Containers, preflight and CI | Clean local runtime and remote CI pass |
| 15 | Real playtesting and round tuning | Observed fun/clarity, truthful evidence |
| 16 | GCP migration plan and revised cost gate | Reviewed non-destructive plan fits total budget |
| 17 | Repository identity, WIF and cloud foundation | Keyless access, scoped secrets and logical DB ready |
| 18 | Candidate deployment and recovery verification | Real private connectivity and external gameplay pass |
| 19 | Production cutover | Public Taste Duel healthy; rollback rehearsed |
| 20 | Legacy retirement after the release gate | No old runtime dependency silently remains |
| 21 | Production handoff and hackathon readiness | Public source/demo and factual release record |

## Prompt 1 — Establish the pivot from scratch without losing the old work

```text
Implement Prompt 1 only. Read ai/prompts.md in full and applicable AGENTS.md instructions. Use the available Codex agents with independent ownership for source inventory, product/spec rewriting and preservation/security review.

Inspect the current repository, maintained ai documents, source layout, Git status, ignore rules and deployment descriptions. Treat the attachment as reference; use the corrections and product contract in ai/prompts.md. Do not read credential-history files or print secrets. Do not change cloud resources or deploy.

Preserve a known-good AccessLife source checkpoint with a descriptive Git tag once the actual clean/dirty state is understood; do not discard uncommitted user work. Record hashes of the three original reference files and preserve their bytes. Keep rollback information, not an active second copy of the old application in the new build context.

Rewrite ai/prd.md, ai/Architecture.md, ai/rules.md, ai/phases.md and ai/design.md for Taste Duel from scratch. Keep dated factual history in ai/memory.md; clearly mark the pivot and historical AccessLife milestones. Update README with planned versus implemented status. Include API secrecy, fixed shared replay, source rights, adaptive solo mode and lean architecture. Remove the five-city requirement from the new product; the user explicitly selected a different product.

Ensure ignore rules retain ai/prompts.md and the six maintained specs while excluding original references, environment values, raw Qloo responses, state, datasets and local artifacts. Do not copy any pasted credentials. Identify the fresh Taste Duel module tree and a dependency-removal plan for maps, embeddings, ingestion, old planner and obsolete workers; perform removals only when their replacement stage is ready.

Gate: reference hashes unchanged, old source recoverable, no secrets staged, scope/roles/resource boundaries recorded, and no application/cloud completion claims. Report the exact baseline and next step: Prompt 2.
```

## Prompt 2 — Prove the data sources and Qloo capabilities before committing to them

```text
Implement Prompt 2 only. Read ai/prompts.md and Prompt 1 outcomes. Delegate official-source research, a bounded live capability spike, and independent score/rights review. No infrastructure provisioning.

Read the official Qloo kit, safe-use/API-access documents, MCP starter, current tool manifest and category parameter guides. Pin the inspected commits/package version. Validate that any advertised OpenAPI download actually contains endpoint paths: a generic OpenAPI meta-schema is not an API contract and must not drive code generation.

Use the existing Secret Manager reference server-side without printing or saving its payload. Inspect current harness capabilities/listTools first. Establish an explicit small smoke budget before live calls; target at most 12 upstream requests total, no concurrency bursts, bounded retries and a recorded actual count. If this cannot prove the matrix, report the precise remaining probes rather than silently exceeding the budget.

Verify artist/movie seeds and movie/artist targets, typed search ambiguity, a genuine cross-domain ranking, actual score units, affinity ordering, ties, image fields and explainability warnings. Inspect documented/returned quota and expiry metadata; never deliberately exhaust the event key. Test 429/deadline failures with synthetic contracts, using live calls only for the bounded capability spike. Count harness-internal upstream lookups too; instrument redacted HTTP counts or use verified conservative workflow maxima, not one HTTP request per MCP tool assumption. Try book/person support only within the remaining budget; otherwise leave it gated. Verify the configured Vertex model separately with at most one small schema-constrained call, or defer it to Prompt 8. API enablement alone is not model access proof.

Create a dated source/capability/rights matrix linked from ai/Architecture.md. Record permitted private cache/evidence retention and challenge expiry policy from applicable terms; identify actual unresolved restrictions rather than inventing blanket licensing claims. Determine whether original artwork is sufficient or optional TMDB/Commons enrichment is justified. No optional provider is required merely because it exists.

Save only permitted minimal private evidence in ignored artifacts; commit synthetic response contracts and source links, not live payloads. Gate: verified paths to five-round pool generation for supported seed types, explicit unsupported capabilities, score/display semantics and honest asset fallback. Do not claim all example names have coverage.

If a provider outage or missing external capability blocks this gate, proceed only with independent synthetic visual work in Prompts 3-4. Record the blocked live gate and do not claim later live integration passed. Return to resolve it before dependent provider/game integration.
```

## Prompt 3 — Design the visual experience before backend polish

```text
Implement Prompt 3 only. Read ai/prompts.md, the new product/design specs and Prompt 2's capability matrix. Use agents for art direction, prototype implementation and independent mobile/accessibility review. Do not provision GCP or build the whole backend.

Create the new Next.js/Taste Duel frontend shell from scratch. Do not reskin the AccessLife planner. Implement a runnable visual prototype with original composition: landing/seed search, unanswered duel, selected/reveal state, results ticket and challenge invitation. Use explicitly synthetic local content and project-owned fallback artwork; mark prototype mode clearly.

Follow the cultural fight-night editorial direction: distinctive wordmark, expressive local-licensed type, artwork-led choices, one DUEL seam, useful negative space, five-round pips and a shareable result ticket. The title/question and next action must be immediately apparent. Avoid dashboard layouts, feature grids, glass clutter, chat and decorative agent diagrams. Design useful loading and provider-error screens in the same visual language.

Produce original CSS/SVG artwork and a minimal font/asset licence manifest. Capture 390x844 and 1440x1000 screenshots plus 320px reflow, long titles and missing imagery. Inspect the actual renders, including font loading and contrast; make a second visual refinement pass where needed. Do not describe the UI as premium solely because it compiles.

Use narrow client boundaries and accessible controls. Keyboard focus, 48px targets, reduced-motion equivalents and readable titles are part of the prototype, not later decoration. No login gate or forced sound.

Gate: all five states are visually coherent, screenshots exist and have been reviewed, responsive composition is deliberate, and independent review findings are resolved or explicit. Return the runnable preview URL and artifacts. Do not make user confirmation an automatic blocker; incorporate their feedback if provided. Next: Prompt 4.
```

## Prompt 4 — Build a complete five-round frontend using isolated fixtures

```text
Implement Prompt 4 only. Read ai/prompts.md and preserve Prompt 3's visual direction. Split agent ownership across tokens/primitives, gameplay state/components, and independent keyboard/mobile review.

Extract reusable tokens and components into the documented frontend feature folders. Build the full five-round fixture journey: seed confirmation -> preparing -> two choices -> submitting -> reveal -> explicit Next -> result -> challenge invitation. Keep fixture transport behind an adapter and a visible development-only mode; synthetic outcomes must never masquerade as live Qloo.

Define a discriminated frontend state machine. Prevent double clicks and accidental navigation from applying an answer twice. Preserve titles during image loading/failure, avoid layout shifts, maintain focus after Next and announce the outcome once. Motion should reinforce the choice/reveal rather than delay interaction; reduced motion must convey identical information without flips, parallax or confetti.

Implement the accessible combobox with actual arrow/Escape/Enter behavior. Add selected, disabled, pending, empty, partial, retry, expired, interrupted and long-title stories. Keep any sound off by default and use only owned/licensed effects. Include a concise How it works explanation of Qloo ranking versus personal preference.

Add meaningful frontend state/interaction checks and an initial Playwright smoke for a full five-round run, keyboard completion and no overflow at 320px. Keep fixture controls out of production builds through explicit configuration boundaries.

Gate: a person can complete five rounds without a map, account, mouse, animation or audio; score is visibly out of five; screenshots match the prototype's quality; no backend or cloud has been presented as implemented. Next: Prompt 5.
```

## Prompt 5 — Define private/public contracts and the new database domain

```text
Implement Prompt 5 only. Read ai/prompts.md and current frontend contracts. Assign agents to domain/API schemas, database migrations, and independent secrecy/isolation review. Work against a clean local Taste Duel database, never overwrite the deployed AccessLife database.

Create apps/api/src/tasteduel with explicit domain, application, ports, adapters, api and persistence boundaries. Use Python/Pydantic as the contract source and generate frontend types from the application's exported OpenAPI. Do not hand-maintain competing schemas or generate from an unverified Qloo spec file.

Model guest sessions, generation reservations/leases, minimal entity metadata, ranking snapshots, private round pool, delivered rounds, accepted answers, game result, immutable challenges/replays, discoveries, bounded provider cache and usage counters. Persist query-context hash, timestamps, provider/harness and validator/scoring versions, expiry and source attribution where needed. Answer keys and raw provider payloads are private by construction.

Specify /api/v1 browser contracts for session creation/current/clear; typed entity search; game creation/read; current round; answer; explicit advance; results; discoveries; challenge creation/invitation/play; and health/readiness. The private FastAPI routes can use /v1 behind the same-origin forwarding boundary. Define status codes, error envelopes, idempotency signatures, conflicts, expiry and retry semantics. Use separate allowlisted PlayableRoundPublic and RevealedRoundPublic DTOs: the former omits answers/ranks/affinities; the latter may expose only an already-answered round after ownership/state checks. Reload can restore that accepted reveal without exposing any future answer.

Use immutable migrations and separate migration/runtime database privileges. Establish database constraints for one accepted answer per delivered round, sequential round advancement, owner/session isolation and challenge versioning. Tests must exercise real database constraints and public DTO serialization, not just mirror schema definitions.

Gate: migrations run on a clean local database; contracts export and generate web types reproducibly; tests prove playable DTOs never serialize answer fields and reveal DTOs expose only authorized answered rounds. Next: Prompt 6.
```

## Prompt 6 — Implement the official Qloo transport and normalized provider port

```text
Implement Prompt 6 only. Read ai/prompts.md and Prompt 2's verified tool/capability record. Assign agents to official MCP integration, synthetic contract tests, and subprocess/security review. Do not make unlimited live calls or provision infrastructure.

Implement QlooPort with typed seed resolution, ranked-candidate retrieval and supported evidence fields. Prefer the official pinned qloo harness local-stdio MCP process. Use its discovered listTools schemas and allowlist only required workflows. The docs MCP server is reference tooling, never a runtime data source and never a destination for credentials.

Package the tested Node runtime and harness into the backend image/reproducible development environment. Start/manage the subprocess once per API instance; handle readiness, concurrent requests, startup timeout, process exit, restart bounds and graceful shutdown. Forward only required environment variables. Keep stdout available for MCP framing and sanitize stderr; no protocol/log mixing or secret dumps.

Normalize all six verified result envelopes: ok, empty, needs_input, partial, degraded and error. Ambiguity must reach a useful user selection rather than a silent guessed entity. Configure per-call deadline, total request budget, bounded eligible retries, shared rate limits and circuit behavior. Authentication failures must not silently become a different provider or fabricated result.

Contract-test actual request construction with synthetic data, malformed envelopes, schema warnings, unsupported parameters, timeout, 429, auth failure, missing explanation, image metadata and process failure. If raw HTTP is necessary for a documented harness gap, keep it behind the same port, independently test GET/auth/parameter construction, and make the choice explicit.

Gate: no provider JSON reaches React/domain consumers directly, no browser key, contract tests pass and any live recheck stays within its recorded tiny budget. Next: Prompt 7.
```

## Prompt 7 — Build the deterministic duel-generation engine

```text
Implement Prompt 7 only. Read ai/prompts.md and verified provider contracts. Split agents across pair-generation logic, property/scenario tests, and independent score/fairness review. No LLM or cloud is needed to prove these rules.

Given a normalized ranking snapshot, build a small pool of roughly 10-15 potential pairs, sufficient for five non-repeating delivered rounds where coverage allows. Each pair must contain distinct same-type entities from the same context and verified ordering. Reject self/duplicate/ambiguous entities, ties/near-ties, missing required metadata, nonfinite scores and contradictory order. Treat fallback artwork as a supported explicit presentation state, not fake provider imagery.

Create deterministic validation reasons and a versioned pair-quality policy. Diversify eligible categories and balance left/right winner position without encoding the answer in IDs, artwork URLs or client fields. Choose provisional easy/medium/hard bands from within-snapshot evidence; record that these are game heuristics. Never compare raw scores across domains/queries or equate score gap with calibrated human difficulty.

Ensure the selection algorithm can produce a complete five-round path with no repeated contestant, not merely five individually valid pairs that exhaust each other. If the requested quality/diversity cannot be met, return explicit insufficient coverage. Do not manufacture five rounds, loosen a tie threshold invisibly or substitute generic LLM picks.

Tests should include permutations, duplicate metadata, missing scores/images, equal scores, near-ties, tiny pools, all candidates in one band, arbitrary external strings, reproducible RNG and no-repeat path exhaustion. Verify emitted first choices are not invariably winners and no upstream rank is encoded in public IDs/order. Validate the same snapshot always preserves its winners and versioned rules.

Gate: real normalized samples from the permitted private spike can produce plausible pools locally, while committed tests use synthetic fixtures. Report rejection counts and limitations, not invented win rates. Next: Prompt 8.
```

## Prompt 8 — Build one bounded RoundCuratorAgent with real tool use

```text
Implement Prompt 8 only. Read ai/prompts.md and the validated QlooPort/DuelPoolBuilder. Use agents for Vertex/tool orchestration, failure contracts and independent grounding review.

Implement a small RoundCuratorAgent using Google Gen AI and Vertex IAM/ADC. Verify one low-latency supported model and pin its configuration; do not assume an example model name exists. A typed tool loop should inspect the seed, choose among verified target domains, fetch a small ranked set, inspect validator findings, optionally make one useful bounded correction and finish a validated pool. The model must make real bounded tool decisions; a fixed pipeline narrated by an LLM must not be described as autonomous reasoning.

Choose and document hard limits before live use: target overall generation envelope about 20 seconds, at most six upstream Qloo requests including retries and harness-internal lookups, a normal target of two Vertex requests with a hard maximum of four, finite tool steps/tokens, repetition detection and an overall cancellation deadline. Reconcile the loop with measured latency and total token/cost limits; fewer calls are better when sufficient. Use shared per-key controls so scale-out and any overlapping legacy runtime do not multiply the quota unexpectedly. Do not confuse one MCP workflow with one upstream HTTP call.

Deterministic validators own eligibility/winners. Agent output can select only known IDs and cannot alter scores, invent candidates or override a rejection. Reveal copy must be based on returned evidence; otherwise use a factual sentence saying which entity ranked higher in this query. No inferred psychological or causal story from correlation alone.

Record a redacted action trace of selected tools, timings and statuses, never private chain-of-thought. If Vertex is unavailable, a labelled deterministic curator may build a valid Qloo pool; record the actual mode. It is resilience, not proof that live agent use passed.

Gate: malformed output, prompt injection in metadata, repeated calls, provider failure, deadline and validator-veto tests pass. A bounded live run shows genuine Vertex tool use and genuine Qloo ranking before claiming agent readiness. Next: Prompt 9.
```

## Prompt 9 — Implement authoritative gameplay, retries and session isolation

```text
Implement Prompt 9 only. Read ai/prompts.md, generated contracts and the curator/engine interfaces. Delegate persistence/API work, concurrency/restart testing, and independent security review.

Implement the session and gameplay APIs from Prompt 5. On game creation, reserve a generation record transactionally using the session, idempotency key and canonical request signature. Execute bounded generation in the awaited request, persist the private pool atomically and return a ready game only after commit. Separate transient reservation status from a completed playable game. Retry after a lost response must return the same game; changed input with a reused key must produce an explicit conflict.

Use expiring database execution claims with fencing so an interrupted/restarted request cannot publish twice. A reconnect can inspect state and retry after an expired claim. Do not rely on post-response FastAPI background tasks, in-memory promises or Cloud Run continuing after a response. If returning 202 for an already-running request, describe it as observation of that request, with a recovery path when its lease expires—not a promise of an undeployed queue.

Deliver only the current round's public DTO. Validate round/game/session ownership on answer. Accept an answer once under a transaction; duplicate identical answers return the saved result, conflicting answers return conflict, and future/expired/other-session round IDs fail. Make explicit advancement idempotent too. Recompute score from accepted stored answers, never client totals. Keep post-answer reveal separate from next-round delivery.

Tests must cover concurrent create/answer/advance, double taps, lost responses, API restart, stale claims, session clear during generation, out-of-order guesses, malicious IDs, replayed keys with changed bodies, expiry and attempted pre-answer leakage through every read endpoint.

Gate: a clean local database supports the full authoritative game flow; two isolated sessions cannot read each other's private state; no external provider calls occur on answer/Next. Next: Prompt 10.
```

## Prompt 10 — Connect the designed frontend to genuine Qloo-backed gameplay

```text
Implement Prompt 10 only. Read ai/prompts.md and preserve the visual prototype. Give agents ownership of search/session forwarding, game/reveal integration, and independent external-state/visual review.

Connect the existing Taste Duel screens to generated API types. Implement same-origin forwarding with strict path/header allowlists, secure host-scoped cookies, explicit mutation-origin validation and no public private-API credentials. Keep development localhost behavior intentional. Return useful typed errors; never expose upstream headers, private pool or secret-bearing diagnostics.

Wire typed seed search/disambiguation and cancellation of stale requests so selecting a new seed cannot show results belonging to an old query. Preserve an idempotency key for the same submission after an uncertain network failure; replace it only for changed input or a confirmed new game. Display truthful preparing progress based on real stages/status, not invented agent activity. Expose only a redacted action summary and only when useful, behind a small disclosure.

Integrate answer submission, reveal and explicit Next with server state. Press feedback starts immediately while correctness waits for the server. Reload/Back/reconnect must resume the actual game state, not restart at round one or submit the previous answer twice. Final score comes from the server. Clearly distinguish genuine agent, deterministic curator and development fixture modes.

Use licensed/approved imagery with a bounded allowlisted asset policy and original title-card fallback. Protect server image fetching from SSRF, redirects to private hosts, invalid content types and oversized files. Do not introduce an unrestricted image proxy.

Gate: a bounded live run completes search -> five genuine Qloo-backed rounds -> result, with real source status. Desktop/mobile screenshots retain the design quality; network inspection shows no hidden answers or key. Next: Prompt 11.
```

## Prompt 11 — Finish adaptive solo play, discoveries and interruption recovery

```text
Implement Prompt 11 only. Read ai/prompts.md and current gameplay results. Split agents across adaptive selection, discovery/session behavior, and independent interaction/recovery tests.

Finish deterministic adaptive solo selection from the already-persisted pool: begin with an appropriate calibrated band, increase challenge after a real streak and ease after a miss where unused valid pairs permit it. Resolve scarce-band fallback explicitly; never invent a new ranking or call Qloo on each turn. Preserve five total rounds, no repeated contestants, balanced presentation and the versioned rule set. Do not call this adaptation an LLM learning about the individual.

Implement discovery save/unsave with session ownership, useful empty/expired states and a compact result display. Saved entities are things the user selected, not evidence that an aggregate affinity predicts their preference. Respect the source retention policy and show what expires with the anonymous session. Session clearing must revoke private access and handle dependent share links according to the documented policy; do not claim it rewrites existing backups.

Handle refresh, offline/reconnect, another tab, Back, an answer accepted before response loss and an explicit Next accepted before response loss. Avoid focus traps, premature animations, duplicate score increments and inaccessible error notices. If an existing guest game has expired, say so and offer a fresh game without changing its historic answers.

Gate: scenario tests plus browser checks prove adaptation does not change existing round winners, scoring is stable after retries and recovery works across API/browser restart. Capture updated reveal/result screenshots and keep full keyboard/reduced-motion behavior. Next: Prompt 12.
```

## Prompt 12 — Build exact friend challenges and beautiful, safe sharing

```text
Implement Prompt 12 only. Read ai/prompts.md. Assign agents to challenge persistence/API, invitation/result/social design, and independent fairness/privacy review.

Create a high-entropy unguessable share slug from a completed creator game. Freeze exactly the five rounds actually delivered, their order/sides, seed, target domains, ranking-context references and scoring/validator versions. The public invitation exposes the seed and creator's actual score, not the private answer key, unused pool, creator session or identity. Shared play uses a new guest-owned game and the fixed snapshot; do not independently adapt it or re-query Qloo to replace an answer.

Set explicit expiry/revocation consistent with evidence permissions, session policy and backups. An expired/revoked challenge has an intentional page and can lead to a new solo game. It cannot silently become a new challenge. Creator retries must not create many slugs for the same request. Record that sharing is casual play, not a cheat-proof public competition: prior knowledge, external research and repeated attempts exist. No global leaderboard or fabricated percentile.

Build the result ticket, copy/share fallback and invitation in the visual system. Generate a social image from original artwork, seed title and authorized actual score; include external artwork only if its social reuse rights were verified. Social previews must contain no future choices or answers, personal identifiers or session data. Use the canonical production origin, never an assumed purchased domain. Guard server rendering/image fetches and prevent cached private responses.

Gate: two isolated browser sessions play identical stored five-round comparisons and produce correct independent scores; zero new Qloo/Vertex calls occur during replay. Test that provider rankings changing later cannot alter challenge rounds, sides, rules or winners. Test expiry, revocation, refresh, answer secrecy and accessible copy-link feedback. Inspect mobile and OG renders. Next: Prompt 13.
```

## Prompt 13 — Audit the complete product for accessibility, speed and abuse

```text
Implement Prompt 13 only. Read ai/prompts.md. Use independent agents for full accessibility/visual audit, security/provider-abuse review and performance analysis; the lead integrates fixes.

Run Playwright journeys for solo and fixed challenge, including landing, combobox, unanswered state, reveal, result, interrupted and expired states. Run full axe scans without exclusions to hide findings. Manually verify keyboard completion, focus restoration, announced outcomes, 200% zoom, 320px reflow, touch targets, image failure, long titles and reduced motion. Verify contrast using actual computed/rendered combinations. Screen-reader support is a separate manual result; an axe pass is not proof of user testing.

Measure the production build. Targets, until measured: LCP <=2.5s and CLS <=0.1 in an identified lab setup; initial route JS about <=180KB gzip and gameplay addition <=100KB; immediate client pressed feedback under 100ms; warm server-side answer-handler p95 <=500ms with no provider calls. Report sample size and network/cold-start conditions separately. Do not claim field INP/p75 from Lighthouse or a tiny local sample. Lazy-load animation features and avoid loading unnecessary maps/graphs/old model assets.

Harden session/mutation isolation, CSP/headers compatible with the actual framework, parameter validation, bounded request sizes, per-session/short-lived privacy-preserving abuse limits, global per-key Qloo budgets across scale-out, model daily usage limits and cache expiry. Do not implement one IP throttle that blocks all users behind the forwarding service. Never trust an unvalidated forwarded header.

Test malicious metadata/tool output, unavailable secrets, auth errors, throttling, empty pools and database failure. Avoid user-facing stack traces. Search built HTML/JS, DTOs, logs and OG output for answer-key and secret exposure. Dependency findings require severity/reachability review and fixes, not a false zero-risk promise.

Gate: unresolved serious/critical accessibility or security defects block release. Record precise remaining lower-risk limitations and measured performance. Next: Prompt 14.
```

## Prompt 14 — Package the local runtime and make remote CI trustworthy

```text
Implement Prompt 14 only. Read ai/prompts.md and current test results. Delegate containers/preflight, CI/contracts, and independent clean-clone verification.

Provide Docker Compose for web, API and PostgreSQL, with a one-shot migration command. No embedding/ingestion/model-cache/old worker service should be required. Bake tested dependencies and the official harness into immutable images; run as non-root where supported. Keep build contexts free of .env, ADC, private responses, Terraform state, old references, datasets and test artifacts. Do not download dependencies at runtime.

Implement a Windows PowerShell preflight for Docker Desktop, ports, required nonsecret configuration, ADC mounts, database readiness and migrations. Never delete a volume to make startup pass. Clone defaults may run an explicitly labelled fixture demo; genuine Qloo mode resolves only Secret Manager references and ADC. If optional credentials are unavailable, leave optional providers disabled.

Document start, health, migrate, test, stop and persisted-data behavior. Verify a clean local Taste Duel database migration, container restart and retained game/challenge state. Stop with docker compose down; data-volume deletion remains a distinct destructive operation.

Replace legacy CI with lint, domain/provider contracts, database integration, OpenAPI/type drift, strict typecheck, production builds, container smoke, full desktop/mobile Playwright/axe, secret checks and Terraform static validation. CI uses synthetic provider contracts and never event keys. Preserve full accessibility scans with realistic targeted timeouts. Store screenshots via testInfo.outputPath or a verified writable artifact directory so Linux runners work. Keep lockfiles.

Push only reviewed source/doc/config files, never private outputs. Inspect the actual remote CI result, not just a local pass or workflow syntax. Gate: reproducible clean runtime and a successful remote CI run for the current application SHA. Next: Prompt 15.
```

## Prompt 15 — Test whether the game is genuinely enjoyable and understandable

```text
Implement Prompt 15 only. Read ai/prompts.md and the latest live capability/test evidence. Assign agents to round-quality analysis, UX observation/analytics validation, and independent grounding review.

Exercise a small documented matrix of real artist/movie seeds within an explicit Qloo budget. Verify genuine cross-domain rounds, enough distinct contestants, image/fallback presentation, repeated names, tie rejection, domain variety and honest explanations. Do not publish raw proprietary results. Tune the versioned pair-quality/difficulty policy from observed outputs rather than from the attachment's illustrative numbers. Preserve existing game snapshots when policy changes.

Provide a simple playtest script for willing users: start from a familiar seed, explain the question in their own words, play five rounds, identify a discovery, and try a friend's challenge. If real participants are available, record actual anonymous counts and observations with consent. Do not pretend Codex agents, synthetic fixtures or API success constitute human playtesting. If no participants are available, mark the human gate pending and continue independent technical checks; do not manufacture findings.

Implement minimal first-party event accounting for game_started/completed, round_answered, replay, challenge_create/open/complete and discovery_saved. Avoid names, raw search text where unnecessary, persistent fingerprints or secret/ranking payloads. Define denominators, bot/test exclusions and retention. The UI must never display invented live counts, completion rates, user testimonials or percentiles.

Evaluate the actual product: are rounds understandable and surprising without feeling arbitrary? Does replay use the same five? Are users discovering anything worth saving? Remove confusing flourish before adding features.

Gate: documented technical round-quality results, an honest playtest status and repaired observed usability defects. Human impact remains unproven without actual users. Next: Prompt 16.
```

## Prompt 16 — Plan the GCP pivot and refresh the total cost gate, without applying

```text
Implement Prompt 16 only. Read ai/prompts.md, infra source/state ownership and the previous cost review. Use agents for read-only inventory/migration design, cost/IAM analysis and independent destructive-change review. This prompt does not authorize terraform apply or production traffic changes.

Inventory only the dedicated AccessLife resource metadata in project-bb13ecd8-9d67-408d-9a7, asia-south1: services/revisions/traffic, jobs/scheduler/tasks, SQL instance/logical databases/users, registry, buckets/state, secrets by name/version status, SAs/IAM/WIF, alerts and repository trust. Do not print payloads or touch unrelated PharmaGuard resources. Record actual old image digests and rollback targets. Reconcile drift before planning ownership changes.

Design the lean Taste Duel topology: public tasteduel-web, private tasteduel-api, one migration job and ordinary PostgreSQL on the existing dedicated SQL instance. Use a new tasteduel logical database and restricted runtime principal; retain the old logical database for rollback under a stated policy. Do not create a second always-on SQL instance or extra dev/stage/prod projects by default. Use local development plus short-lived no-traffic candidates inside the reviewed budget.

Create a resource-by-resource old -> new/reused -> retired mapping covering names, labels, secrets, identities, monitoring, URLs, workflows and state. SQL instance/bucket/secret IDs are not simply renameable. Retain documented immutable-name exceptions when migration would add cost without product value. Do not move the remote-state bucket/prefix at the same time as application identities; use explicit Terraform moved/import handling for legitimate ownership refactors. Preserve old logical database/user resource blocks at stable or moved legacy addresses until retirement: changing the existing database resource's name must not drop/replace AccessLife data to create Taste Duel.

Recalculate total incremental cost: actual AccessLife spend already incurred + remaining SQL/storage/backups + new runtime/model/API traffic + temporary overlap/restore/builds + currency/tax through at least 6 November 2026, 10:15 IST, plus required follow-up. The prior US$78.48 forecast is historical, not current capacity. Keep the US$80 total gate. Update budget-label coverage to include both migration identities and manually account for unlabeled costs; alerts do not cap spend.

Validate Terraform/container configuration without apply. Separate a reviewed foundation plan for Prompt 17 from the release plan in Prompt 18, which depends on published image digests. Do not apply nonexistent image references or use routine resource targeting to hide incomplete configuration. Plans must show no unexpected replacement/destruction or unrelated resources. Gate: supported regional services/models, scoped identities, explicit rollback/retirement plan and a passing refreshed cost estimate. If it fails, stop provisioning and present a priced adjustment. Next: Prompt 17.
```

## Prompt 17 — Migrate repository identity, keyless access and the cloud foundation

```text
Implement Prompt 17 only, after Prompt 16's current cost and plan gates pass. Read ai/prompts.md and the actual reviewed resource map. Delegate repository/WIF coordination, Secret Manager/database/IAM preparation and independent scope verification. This stage changes foundation resources only; do not serve the new product publicly yet.

Rename the existing public repository to saimaharana4/taste-duel if available, preserving history, licence and tags. Inspect connected GitHub capabilities first; use existing authenticated CLI/REST only if the connector lacks the operation. Never print tokens. If the target exists, do not overwrite it; record a specific naming conflict. Update local remote, badges/docs and workflow references. Coordinate trust changes before relying on the renamed repository.

Use restricted GitHub OIDC/WIF, preferably verified numeric repository/owner IDs plus main-branch/environment restrictions. Avoid broad owner-wide trust. Scope the deploy identity to Taste Duel services/jobs, registry writes and required service-account use; it does not need project-wide administration. Verify keyless authentication without triggering deployment first.

Apply only the reviewed saved foundation plan: identities, registry access, WIF, scoped secrets and the tasteduel logical database on the existing instance. Retain the old database/user resources explicitly. Do not deploy product services until the release images exist in Prompt 18; a maintenance bootstrap here requires a published reviewed bootstrap digest and controlled access. Separate migration-owner and runtime-DML roles. Put fresh database/application signing credentials, if needed, directly into Secret Manager with no source/local payload files. Vertex uses IAM. Web gets private API invocation, not secret access; API gets only required database/Qloo/model permissions. Do not copy every old optional credential into the new app.

For Qloo, retain the existing secret reference temporarily or deliberately migrate its name with scoped IAM. Copying the same key into a new secret is not provider-key rotation. Pin released versions, preserve old readers until cutover/rollback expiry and never disable a shared Qloo key prematurely. Keep Terraform ephemeral/write-only secret fields; audit state without printing sensitive values.

Replace the legacy deployment workflow before running it: it must never call AccessLife ingestion/reconcile jobs or deploy old source. Reconcile any hardcoded deployment-expiry check with the newly reviewed judging/follow-up window; do not remove the cost/expiry safeguard to make a run pass. Gate: WIF auth succeeds, database privileges and secret grants are verified, public source identity is correct, and no new public product traffic or unrelated mutation occurred. Next: Prompt 18.
```

## Prompt 18 — Deploy a no-traffic candidate and verify real cloud behavior

```text
Implement Prompt 18 only. Read ai/prompts.md and refreshed budget/headroom, reviewed Terraform state and successful CI SHA. Assign agents to immutable image/release execution, external browser/connectivity checks, and restore/security evidence. Recheck the cost gate before extra resources or restore targets.

Build/push immutable Taste Duel images. A brand-new Cloud Run service's first revision must not be assumed to support a zero-percent initial allocation. Bootstrap the new services with a controlled maintenance response and the intended IAM boundary, then deploy the actual candidate as a tagged no-production-traffic revision of that existing service. Alternatively document a genuinely IAM-restricted initial deployment and its real allocation; do not label it zero-traffic when it is not. A public web tag can still be reachable at zero percent and is not a security boundary. Keep the API IAM-private; use managed Cloud SQL connectivity. Run only the new tasteduel migration job, then seed only project-owned data required for the app. No RAG ingestion/model assets or legacy jobs. Record image digests, schema revision, actual secret versions and traceable source SHA.

Once image digests exist, generate and review the release plan against the foundation state, then apply only the reviewed changes. Configure canonical URL, exact allowed mutation origins and secure host-scoped cookies. For tagged candidate testing, explicitly allow only the required temporary candidate origin and remove it after release. Control preview access deliberately; a zero-percent tag can still receive direct requests, and it must never expose diagnostics or unfinished private data. Web-to-private-API ID-token audience remains the API service URL even if the request uses a revision-tag URL. Verify that unauthenticated direct API access is rejected; a readiness curl alone is not a gameplay test.

From an external browser, complete real search, a genuinely agent-curated Qloo game, five answer/reveal transitions, discovery save, exact friend replay in a separate session, interrupted-response recovery and expiry/error states. Inspect HTML/network/OG for answer/secret leakage. Run desktop/mobile axe, keyboard/reduced-motion and screenshot checks against the candidate. Distinguish transparent deterministic fallback from a passed live Vertex test.

Rehearse recovery using an explicitly priced disposable target and a private backup. Never restore over the live database. Record exactly whether this was a logical-database export/restore or a managed Cloud SQL backup restore; one does not prove the other. Verify actual restored counts and sample game/challenge behavior, then remove only the verified disposable target. Record the remaining managed-restore gate if not executed.

Gate: complete external product flow, private connectivity, measured warm/cold timing, source rights, recovery evidence and current total cost pass. No automatic production promotion on partial results. Next: Prompt 19.
```

## Prompt 19 — Cut over production to Taste Duel and prove rollback

```text
Implement Prompt 19 only after candidate gates pass. Read ai/prompts.md and the exact release/rollback plan. Use agents for controlled release, independent public-browser verification and IAM/observability review.

Promote the tested compatible web/API configuration deliberately. New tasteduel services are a service cutover, not a percentage split between two unrelated services. Do not randomly send users between AccessLife and Taste Duel. For later compatible Taste Duel revisions, Cloud Run revision traffic splitting is available; coordinate API/schema compatibility so independent traffic percentages cannot form invalid web/API combinations.

Set the canonical actual Taste Duel service/domain URL in metadata, session/origin configuration, share links, OG images, README, GitHub About and monitoring. Do not claim a custom domain exists unless it is owned and its DNS/TLS are verified. Old-origin cookies do not automatically transfer; provide a clear fresh guest experience rather than sharing a parent .run.app cookie. Remove temporary candidate origins and public diagnostic access.

Update release automation to build -> CI verification -> immutable publish -> migration -> no-traffic deploy -> external smoke -> explicit traffic promotion -> post-release checks. Maintain least privilege and rollback-compatible schema changes. Rehearse rollback to compatible Taste Duel revisions/configuration while preserving new data. Keep AccessLife recovery separately documented during its short migration window; do not erase accepted old work as a branding step.

Verify public landing/search, five rounds, correct score, exact two-session challenge, mobile, keyboard, reduced motion, private API rejection and secret/answer secrecy. Monitoring should reflect Taste Duel readiness and meaningful generation/error/cost signals without logging raw taste responses or PII. Report first-run/cold timing honestly.

Gate: the public URL serves Taste Duel end to end, current commit/digests match, monitoring works, rollback has evidence and total cost remains inside the approved envelope. Next: Prompt 20.
```

## Prompt 20 — Retire the AccessLife runtime without deleting shared dependencies

```text
Implement Prompt 20 only after Taste Duel production is healthy and the documented rollback/retention conditions allow each action. Read ai/prompts.md and the resource map. Delegate runtime dependency inventory, controlled retirement and independent preservation/IAM review. Do not interpret “replace everything” as project-wide destruction.

Stop accepting new AccessLife planning work and drain or explicitly resolve accepted runs. Pause the old reconciliation scheduler, then verify worker/queue dependencies before disabling legacy worker/jobs/tasks. Retire old ingestion, corpus/model assets and transport/map dependencies from active images and pipelines. Ensure the new app does not reference accesslife Python modules, old logical tables or legacy job commands.

Update all user-facing branding, dashboards, alerts, labels, workflow names and documentation to Taste Duel. Recheck alert filters during overlapping old/new labels; per-resource label changes must not make costs disappear from the report. Keep an explicit list of retained immutable physical names, such as the reused SQL instance, registry or state prefix, with their reason and owner. Do not falsely report those IDs were renamed.

Revoke old service grants and disable old secret versions only after all readers, queues and rollback requirements expire. Preserve the shared Qloo secret while referenced. Remove obsolete billed resources only when ownership, backup, retention and rollback checks establish they are no longer needed; do not destroy the reused SQL instance, state bucket or unrelated workloads. If irreversible old-data deletion is not covered by the migration policy, prepare the concrete deletion list and leave that action pending rather than improvising.

Do not keep legacy services publicly offering a second active product. Use a safe retirement response or redirect only where intended and tested. Maintain judging access to Taste Duel. Record expected savings and actual remaining charges, not just deleted names.

Gate: no old runtime or release path is needed by Taste Duel; secrets/data/state needed for recovery remain protected; Terraform ownership is intact and a refreshed plan has no unexplained drift. Next: Prompt 21.
```

## Prompt 21 — Finish production documentation, verification and submission materials

```text
Implement Prompt 21 only. Read ai/prompts.md and all recorded implementation/release results. Use independent agents for product/visual acceptance, source/security reproducibility and release-evidence review. Fix actual failures; do not repeat costly checks without a changed reason.

Update all six maintained ai documents, README, infra runbook, source/asset attribution and short memory entries to match the actual Taste Duel implementation. Include architecture/app flow, one agent's real responsibilities, public/private contracts, exact source semantics, adaptive solo versus fixed challenge behavior, limitations, operational commands, secret rotation, rollback, restore status and resource-name exceptions. Preserve original reference files. Remove obsolete current-tense claims that AccessLife is the active product while retaining its clearly historical audit trail.

Verify the public repository, detected open-source licence, reproducible lockfiles/container instructions, current remote CI, deployed source SHA/digests, canonical live URL and a final external five-round/two-session challenge journey. Check tracked files/build context for credentials, private Qloo captures, state, model caches and artifacts; record unchanged reference hashes. Verify production browser and image states with real permitted data, not screenshots from fixtures.

Prepare a concise Devpost description explaining the user benefit, why Qloo determines the game outcomes, real agent/tool behavior, data/asset licences and honest known limitations. Supply actual screenshots and an optional short walkthrough; current official rules require the live demo, public licensed source and description. Recheck rules before submission rather than assuming a video requirement. Do not submit or send materials unless the user separately instructs it.

Target feature freeze 30 October and submission by 31 October 2026, 09:15 IST, subject to official-rule verification. Preserve judging access through the full judging period: current rules end 5 November 23:45 Eastern, which is 6 November 10:15 IST. Reconcile the old cost window ending 5 November with that later endpoint and any required finalist follow-up; do not silently extend spend or tear down early. Reforecast and stop extra provisioning if the US$80 envelope cannot cover the actual period.

Gate: report only achieved outcomes, exact remaining blockers, tested live URL, source/CI links, actual cost window and a dated maintenance/teardown plan. Teardown is a separate deliberate operation, not an automatic post-submission action. The final report must distinguish a working production MVP from unmeasured popularity, retention or hackathon success.
```

## Official references to recheck at the relevant iteration

Research references inspected for this prompt plan on 24 October 2026. Pin implementation versions/commits later; links are not evidence that the new app has been built or that the current event key grants every capability.

| Reference | Use |
|---|---|
| [Hackathon overview](https://qloo.devpost.com/) and [official rules](https://qloo.devpost.com/rules) | Required integration, public release, judging and dates |
| [Developer guide](https://docs.qloo.com/reference/qloo-llm-hackathon-developer-guide) | Event-specific host/access guidance; use official mirror if unavailable |
| [Official hackathon kit](https://github.com/qloo/qloo-hackathon-kit) | Supported runtime routes and starter code |
| [API access](https://github.com/qloo/qloo-hackathon-kit/blob/main/docs/API_ACCESS.md) and [safe use](https://github.com/qloo/qloo-hackathon-kit/blob/main/docs/SAFE_USE.md) | Quota discipline, trusted server calls and handling boundaries |
| [Official MCP starter](https://github.com/qloo/qloo-hackathon-kit/blob/main/starter/mcp-client/README.md) and [manifest](https://github.com/qloo/qloo-hackathon-kit/blob/main/manifest.json) | Local stdio process, tool schemas and workflows |
| [Public documentation mirror](https://github.com/qloo/docs-public) | Cross-check actual reference content; validate advertised schema contents |
| [Entity search](https://github.com/qloo/docs-public/blob/main/reference/get-search.md) and [parameters by entity type](https://github.com/qloo/docs-public/blob/main/reference/available-parameters-by-entity-type.md) | Typed resolution and supported target parameters |
| [Insights reference](https://github.com/qloo/docs-public/blob/main/reference/insights-api-deep-dive.md) and [affinity interpretation](https://github.com/qloo/docs-public/blob/main/docs/interpreting-affinity-scores.md) | Ranking context, score semantics, images and explainability |
| [Qloo terms](https://www.qloo.com/legal/terms) | Applicable API/output terms; event-specific agreements may add conditions |
| [TMDB FAQ](https://developer.themoviedb.org/docs/faq), [Wikidata licensing](https://www.wikidata.org/wiki/Wikidata:Licensing), [Commons reuse](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia) | Optional enrichment, artwork permissions and attribution |
| [Next.js Server/Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components), [React Aria](https://react-spectrum.adobe.com/react-aria/components.html), [Motion accessibility](https://motion.dev/docs/react-accessibility) | Narrow interaction boundaries and accessible primitives/motion |
| [Cloud Run service management](https://docs.cloud.google.com/run/docs/managing/services), [deployment](https://docs.cloud.google.com/run/docs/deploying), [traffic and rollback](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration), [service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service) | New service identity, candidate releases and private API audiences |
| [Cloud SQL restore](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/restore), [secret editing](https://docs.cloud.google.com/secret-manager/docs/edit-secrets), [bucket naming](https://docs.cloud.google.com/storage/docs/buckets) | Data protection and immutable-name migration limits |
| [WIF for deployment pipelines](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines) | Restricted keyless GitHub identity, including rename-safe numeric claims |

## Final definition of done

Taste Duel is complete for this MVP only when a guest can open the real GCP web app, choose a supported real seed, play five valid Qloo-backed rounds, see an honest score, save a discovery and send a challenge another guest can replay identically. The UI must pass inspected visual/accessibility gates; answers and credentials stay server-side; local/remote runtime and failure/recovery checks pass; current costs and release limitations are documented.

Do not let infrastructure elegance substitute for an enjoyable game, let attractive fixture screenshots substitute for genuine Qloo, or let a passing API substitute for a usable production website.

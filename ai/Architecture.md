# Taste Duel architecture

Revision 5 — 25 October 2026 — Prompt 4 fixture frontend. **The full architecture remains a target; five-round local fixture play is implemented. No Taste Duel backend or deployment exists.**

The web entry point is now a fresh Taste Duel prototype. Python backend, containers and recorded cloud deployment remain AccessLife AI. Historical verification remains in [memory.md](memory.md) and Git history; it does not validate Taste Duel gameplay, its agent, data rights or cloud migration. [prompts.md](prompts.md) controls later iterations.

**Implemented boundary through Prompt 4:** Next.js server layout/pages, local licensed fonts/original SVG art, React Aria seed confirmation, reusable tokens/primitives and a client fixture provider/adapter. Five invented rounds compute the result from accepted answers, support save/unsave and derive a local invitation from the played sequence. No network provider, database, durable session, model, production scoring service or share link is involved. `/api/v1/*` still returns local `503 PROTOTYPE_ONLY`; the forwarding contract below is future work. Synthetic winners are public development code, not a secrecy implementation for real answers. Six legacy web modules/seven dependencies were removed in Prompt 3; three superseded single-round/result/invitation specimens are removed in Prompt 4. Old source stays in the preservation tag. Legacy generated OpenAPI declarations remain unused until Prompt 5.

### Implemented frontend boundary

- `app/` keeps pages/layout as Server Components; bare `tasteduel-fixture-entry` resolves to a client fixture entry only for the explicit development-server phase/flag. Other phases use a separate unavailable entry that imports no fixtures. Normal production builds exclude fixture pools/controls, even when the flag is set; their routes return 404.
- `app/tokens.css` and `components/ui/` own Button/ActionLink, RoundPips and StatusPanel. `features/{seed,duel,reveal,results,challenges,discoveries,curation}` own focused presentation components.
- `features/fixtures/` owns UI-only types, discriminated reducer, synchronous duplicate guards, operation identities, abort/recovery and `FixtureTransport`. The in-memory implementation accepts then simulates response loss; the same answer key recovers one accepted answer. No browser storage, backend or external requests are used.
- State sequence: idle → preparing → unanswered → submitting → revealed → advancing → unanswered/complete, with explicit issue/retry/interruption branches. Only the final explicit Next initiates result navigation; restored arenas cannot auto-redirect Back. Refresh intentionally clears state.
- `features/reveal/WhyThisDuel` accepts an **accepted-round-only** presentation contract: source label, factual ranking-context sentence, optional supported explanation/attribution and discovery action. `fixtureDisclosure` produces this only for the current revealed/advancing answer. No unsupported explanation is supplied.
- `features/curation/CurationSummary` explicitly projects typed domain/mode/count/path facts; it accepts no raw receipt, private reasoning, scores, contestant list or pair/answer data. Here it is nested inside the post-answer disclosure with unmistakable synthetic/no-agent labels. Later allowlisted API DTOs replace fixture facts; these UI types do not define the API.

Fixture tests prove local behavior only. Server authority, adaptive pools, ownership, persistence, MCP/Vertex and exact two-session challenge replay remain future gates. Production exclusion is a build boundary, not proof of future server secrecy.

**Prompt 2 evidence:** the [dated source/capability matrix](qloo-capability-matrix.md) pins harness `0.1.26` and official source commits. Twelve counted requests proved two raw cross-domain samples with five-pair numeric feasibility; canonical MCP Insights and same-domain cells remain unverified. No live payload or generated API client is committed. The advertised OpenAPI file is a meta-schema without endpoint paths and is rejected for code generation. This is a partial feasibility gate, not an implemented provider or game.

## 1. Product flow and decisions

A guest selects one favourite cultural entity, predicts five Qloo comparisons, receives a score out of five, saves discoveries and challenges a friend to the same five rounds. Initial seed/target domains are music artists and movies, subject to Prompt 2's live coverage and rights gates. Book/person support is later; a director's name must not silently resolve as a movie.

The question is **“Which ranks higher for this seed in Qloo's taste graph?”** Qloo supplies a query-specific aggregate ranking, not universal truth, an individual's preferences or a probability of enjoyment. Contestants in one duel share a target type and frozen query context. Different target domains can supply separate rounds; their scores are never compared.

```mermaid
flowchart TD
    Open[Open as guest] --> Search[Search and confirm typed seed]
    Search --> Prepare[Generate and validate private pool]
    Prepare -->|Valid five-round path| Round[Deliver one unanswered round]
    Prepare -->|Insufficient coverage| Retry[Explain and choose another seed]
    Round --> Answer[Accept guess once on server]
    Answer --> Reveal[Reveal accepted round and actual score]
    Reveal --> Next{Five answered?}
    Next -->|No; player selects Next| Select[Choose unused stored pair]
    Select --> Round
    Next -->|Yes| Result[Result ticket and discoveries]
    Result --> Freeze[Freeze actual five delivered rounds]
    Freeze --> Friend[Friend plays identical fixed sequence]
```

| Layer | Target | Boundary |
|---|---|---|
| Web | Next.js App Router, strict TypeScript, Tailwind, React Aria, Motion | Server shell, narrow search/game/reveal client boundaries; original UI |
| API | FastAPI, Pydantic, SQLAlchemy, Alembic | Modular application, not a deployed service per tool |
| Agent | One bounded RoundCuratorAgent through Google Gen AI/Vertex | Genuine tool decisions; never model-written winners/scores |
| Culture | Official pinned Qloo harness through local stdio MCP | Trusted backend only, normalized QlooPort |
| Rules | Deterministic validators, DuelPoolBuilder, GameEngine, ChallengeService | Server-authoritative eligibility, scoring, adaptation and replay |
| Storage | PostgreSQL 16 ordinary relational tables | No RAG, embeddings, spatial/vector requirement or Redis |
| Execution | Bounded awaited request plus persisted reservation/lease | No unowned post-response generation or required queue worker |
| Runtime | Node 24, Python 3.12, exact compatible dependencies/lockfiles | Backend image also includes tested Node/harness; no runtime npx |
| Cloud | Cloud Run web/private API, reused dedicated SQL, migration job | Terraform and GitHub Actions WIF; optional storage only if needed |

LangGraph, Cloud Tasks and extra services require a measured missing capability. They are not inherited because AccessLife already used them.

## 2. Deployment and trust boundaries

```mermaid
flowchart LR
    Browser[Mobile or desktop browser] -->|HTTPS host cookie| Web[Public tasteduel-web]
    Web -->|Forwarding and API-audience ID token| API[Private tasteduel-api]
    API --> DB[(Cloud SQL tasteduel database)]
    API --> Curator[RoundCuratorAgent]
    Curator --> Vertex[Vertex via IAM]
    Curator --> Port[Normalized QlooPort]
    Port --> MCP[Managed local qloo mcp process]
    MCP --> Qloo[Qloo hackathon API]
    Secrets[Secret Manager] --> API
    Migration[Scoped migration job] --> DB
    CI[GitHub Actions WIF] --> Registry[Immutable Artifact Registry images]
    Registry --> Web
    Registry --> API
```

Browser requests use same-origin `/api/v1/*`; Next.js forwards allowed paths to private FastAPI `/v1/*`. Validate mutation origins, strip untrusted internal identity headers and add an IAM ID token. Its audience stays the API service URL even for revision-tag testing. IAM-private is not network-only ingress; unauthenticated direct requests must fail.

Guests have cryptographically random host-scoped Secure/HttpOnly/SameSite=Lax cookies in production; only token hashes are stored. API checks ownership independently of the browser. No shared parent `.run.app` cookie or old/new-origin guest migration is assumed. Private game/session/answer/discovery responses are `no-store` and cannot enter shared RSC/CDN caches. Public challenge invitations grant no creator-session/game access.

Web gets API invocation, not database/secret access. API gets minimum required Qloo/database secrets, Cloud SQL and Vertex permissions. Migration owner and runtime DML principal are separate. Local genuine-provider mode uses ADC plus Secret Manager references; CI uses synthetic contracts. Keys never enter browser bundles, public MCP config, Terraform plaintext state, command arguments or model prompts.

The official `qloo mcp` is a local stdio process managed once per API instance through the Python MCP client. Pin Node/harness; discover `listTools()` schemas; allowlist necessary workflows; bound concurrency/startup/restarts; sanitize stderr; preserve stdout protocol framing; close on shutdown. Forward only required child environment variables. Docs MCP is development reference only. Raw HTTP may be a separately tested explicit adapter for a documented harness limitation, never a silent transport switch.

## 3. Modules, ports and folder structure

```text
apps/
  web/src/
    app/                         # Server pages/layouts and /api/v1 forwarding
    components/ui/               # Accessible primitives and shared tokens
    features/
      seed/                      # Search, typed results and confirmation
      duel/                      # Arena, choices, progress and state
      reveal/                    # Accepted feedback and explicit Next
      results/                   # Score ticket and replay actions
      challenges/                # Invitation and fixed replay
      discoveries/               # Guest save/unsave list
      curation/                  # Sanitized aggregate presentation facts
      fixtures/                  # Explicit development adapter/state only
      mode/                      # Fixture-free production composition root
    lib/{api,assets,telemetry}/
  api/
    src/tasteduel/
      api/                       # HTTP/session boundaries and public DTOs
      domain/                    # Pure entities and rules
      application/               # Use cases, claims and transactions
      agents/                    # Bounded RoundCurator tool loop
      ports/                     # Provider, persistence, clock and RNG
      adapters/                  # Qloo MCP, Vertex and licensed assets
      persistence/               # SQLAlchemy repositories/composition
    migrations/                  # New Taste Duel Alembic lineage
packages/contracts/              # Application OpenAPI -> generated web types
tests/{unit,contracts,integration,e2e,security}/
infra/{containers,terraform}/
scripts/
ai/                              # Six maintained specifications + prompts.md
```

This is the target tree with the current frontend boundary included. Existing `apps/api/src/accesslife` remains legacy until its replacement gates. Planner/place/trip/map web features were removed in Prompt 3; single-round specimens were replaced in Prompt 4. Do not create empty modules simply to fill this tree.

Dependency direction: API/UI → application → domain/ports. Adapters implement ports and are selected at a composition root. Domain code imports no FastAPI/provider SDK/React or raw Qloo JSON. Construction/import must not call networks, migrate data or mutate infrastructure. Pydantic owns application wire schemas; generate frontend TypeScript from actual exported FastAPI OpenAPI. Inspect upstream advertised specs before use: a generic OpenAPI meta-schema without endpoint paths is not a Qloo client contract.

| Port/service | Responsibility | Output |
|---|---|---|
| QlooPort | Typed seed resolution; same-context ranked retrieval | Normalized status, IDs/types, ordering/score semantics, warnings, attribution/time |
| CuratorModelPort | Typed bounded tool decisions and optional grounded wording | Known tool/ID references or explicit unavailability |
| ArtworkPort | Permitted asset or owned fallback | Source/licence/attribution, allowed uses and fallback status |
| CandidateValidator | Identity/type/order/score/rights/duplicate checks | Accepted candidates and reason-coded rejection |
| DuelPoolBuilder | Diverse pairs/bands, feasible no-repeat continuation | Versioned private pool and snapshot references |
| GameEngine | Delivery, answer acceptance, score and deterministic selection | Transactional changes with expected revisions |
| ChallengeService | Freeze completed path and fixed replay | Immutable five-round definition and guest-owned replay |
| Persistence ports | Session/reservation/game/snapshot/cache/usage transactions | Owned domain records, expiry and concurrency guarantees |

## 4. Data ownership and retention

| Record | Important fields/invariants |
|---|---|
| GuestSession | Token hash, expiry, revocation; no account requirement |
| GenerationReservation | Session/idempotency key, body hash, stable game ID, status, fenced lease/expiry, attempts and usage |
| EntityMetadata | Minimal used Qloo ID/type, title, approved artwork and source policy |
| RankingSnapshot | Seed/signals, target/filter context/hash, retrieval time, provider/harness version, verified order, permitted scores, expiry |
| PrivatePool | Pair references, private answers, bands, validator version and feasible five-round path |
| Game | Owner, solo/fixed mode, phase, revision, delivered rounds, scoring version and expiry |
| DeliveredRound | Opaque ID, ordinal, immutable pair/context, stored sides and private winner; no repeated contestant |
| AcceptedAnswer | Unique game/round acceptance, selected choice, time and saved reveal |
| Challenge | High-entropy slug; actual five/order/sides/context/answers, creator score, versions, expiry/revocation; no public creator identity |
| ChallengePlay | New guest-owned fixed game and independent score |
| Discovery | Explicit guest save/unsave of an allowed encountered entity |
| ProviderCache/UsageCounter | Minimal private scope, rights/version/expiry and shared per-key admission counters |

Opaque IDs do not replace authorization. Store instants in UTC; transmit RFC 3339 timestamps. Answer-defining versions are immutable. Foreign keys/unique constraints together with transactional ownership and expected-revision checks enforce ownership relationships, one answer per round and sequential delivery. No DB transaction/connection stays open during provider/model IO.

Prompt 2 must record the applicable event/API policy for raw responses, metadata, ranking evidence, assets, games/challenges, logs and backups. Minimal-cache guidance is not a universal numerical retention licence. Use bounded product defaults only where permitted. A challenge expires no later than its evidence; expiry never silently refreshes an answer key. Clear-session revokes private access and owned live challenges; active cleanup and backup expiry remain separate documented operations.

Qloo is the sole ranking source. Original title-based SVG/CSS cards are an always-available fallback. Optional TMDB/Wikidata/a small Commons asset set may enrich metadata/artwork after exact matching and rights checks, never determine winners. An image URL is not permission to mirror/transform/use it in social cards. Record per-asset provenance/uses. Raw live captures stay private/ignored; no corpus ingestion or embeddings are needed.

## 5. Public API and disclosure contracts

These are target contracts for Prompt 5, not existing endpoints. Browser prefix `/api/v1`, private FastAPI `/v1`. Private records require session ownership. Creation/mutation requests use `Idempotency-Key` scoped to session, operation and canonical body; changed input under the same key returns `409`.

| Method/path without prefix | Request | Successful behavior |
|---|---|---|
| POST /sessions | Empty object | 201, host cookie and safe expiry |
| GET /sessions/current | Cookie | Safe state and owned resumable game references |
| DELETE /sessions/current | Cookie/allowed Origin | 204, revoke session/outstanding publication/owned live shares; clear cookie |
| GET /entities/search | q, allowed seed type, bounded limit | Typed candidates/ambiguity/status and permitted artwork |
| POST /games | Confirmed seed_entity_id/seed_type, mode=solo, idempotency key | 201 after pool commit; 200 for same ready request; reservation behavior below |
| GET /games/{id} | Owner cookie | Safe phase/revision/ordinal/score; current accepted reveal only after answer; no future pool |
| GET /games/{id}/round | Owner cookie | Current unanswered DTO; answered-but-unadvanced gives 409 ROUND_AWAITING_ADVANCE |
| POST /games/{id}/answer | round_id, choice_id, expected_revision, idempotency key | Stable accepted reveal/score; conflicting answer 409 |
| POST /games/{id}/advance | answered_round_id, expected_revision, idempotency key | Next public round or completed state exactly once; no provider IO |
| GET /games/{id}/results | Owner cookie | Completed score/discoveries/challenge action; incomplete 409 |
| POST /discoveries | Allowed encountered entity_id, idempotency key | 201/200 owned save |
| GET /discoveries | Owner cookie | Owned unexpired permitted entries |
| DELETE /discoveries/{entity_id} | Owner cookie | 204 idempotent unsave |
| POST /challenges | Completed owned game_id, idempotency key | 201/200 exact frozen five, canonical share URL and expiry |
| GET /challenges/{slug} | Public slug | Seed/creator score/five-round count/expiry; no choices/keys/creator identity |
| POST /challenges/{slug}/plays | Guest cookie, idempotency key | 201/200 owned fixed game, no Qloo/model calls |
| GET /health/live and /health/ready | None | Minimal sanitized status; detailed diagnostics protected |

Illustrative synthetic unanswered DTO:

```json
{
  "game_id": "opaque-game-id",
  "round_id": "opaque-round-id",
  "ordinal": 2,
  "total": 5,
  "revision": 4,
  "seed": {"id": "opaque-seed-id", "name": "Example seed", "type": "artist"},
  "target_type": "movie",
  "question": "Which movie ranks higher for this seed in Qloo's taste graph?",
  "choices": [
    {"id": "opaque-left-choice", "name": "Synthetic Film A", "artwork": {"kind": "owned_fallback", "asset_id": "cover-a"}},
    {"id": "opaque-right-choice", "name": "Synthetic Film B", "artwork": {"kind": "owned_fallback", "asset_id": "cover-b"}}
  ]
}
```

No ordering, ID, URL, accessibility label or metadata encodes upstream rank/winner. Sides are independently assigned and persisted. Separate public schemas describe unanswered and accepted-reveal states. After acceptance only that round may expose selected_choice_id, winning_choice_id, correct, cumulative score and supported evidence wording. Raw score display requires verified units/permission. Reload resumes saved accepted feedback via owned game state; completed results show answered rounds only. Unused pairs/future answers never serialize.

Errors contain `error.code`, safe `message`, `retryable`, `request_id`, optional field errors/retry guidance. Codes include INVALID_INPUT, SEED_AMBIGUOUS, INSUFFICIENT_COVERAGE, PROVIDER_UNAVAILABLE, GENERATION_IN_PROGRESS, VERSION_CONFLICT, ANSWER_CONFLICT, GAME_EXPIRED and CHALLENGE_EXPIRED. Use 422 invalid fields, uniform 404 inaccessible private IDs, 409 state conflicts, 410 publicly known expired challenges, 429 admission limits and eligible retryable 503 dependency failures. No raw provider payload/header/exception.

## 6. Curator and generation flow

```mermaid
flowchart TD
    Reserve[Reserve request and fenced claim] --> Seed[Validate confirmed seed and domains]
    Seed --> Decide[RoundCurator chooses allowed tool]
    Decide --> Fetch[QlooPort obtains bounded ranking]
    Fetch --> Normalize[Normalize identity order and permitted metadata]
    Normalize --> Validate[Deterministic candidate and rights validation]
    Validate --> Pool[Build diverse feasible pair pool]
    Pool --> Gate{Five-round quality gate?}
    Gate -->|Not yet; budget remains| Decide
    Gate -->|No budget or coverage| Fail[Record useful failure]
    Gate -->|Yes| Copy[Grounded reveal copy or factual templates]
    Copy --> Commit[Recheck lease session expiry and atomically publish]
    Commit --> Public[Return first unanswered round only]
```

Application tools include inspect_seed, fetch_ranked_candidates, validate_candidates, propose_pairs, evaluate_pool and finish_pool. Actual Qloo names/arguments come from pinned discovered schemas; these application functions are not Qloo-owned agents. The model chooses allowed domains/a useful correction; validators veto invalid selections. Generate reveal copy before play from returned evidence or use a factual template. Aggregate correlations do not support psychological/causal stories.

Initial budgets to validate: about 20 seconds total generation, six upstream Qloo calls including retries/internal lookups, normally two and at most four Vertex requests, finite tokens/tool steps and repetition limits. Coordinate per-key usage across scale-out and overlapping old readers. Read quota metadata; simulate 429/timeouts instead of exhausting access. Exhaustion yields retry/coverage failure, never an unbounded loop. Label deterministic Qloo curation when Vertex fails; it is resilience, not proof of live agent tool use.

Reject ambiguous identity, self/duplicate/wrong-domain contestants, unverifiable ordering, contradictory metadata, ties/near-ties and missing/nonfinite required scores. Artwork failure selects an approved fallback. Build roughly 10–15 potential pairs where feasible and prove a five-round no-repeat continuation. Difficulty bands are versioned within-context heuristics, not calibrated confidence/cross-query quantities. Adaptive choice must preserve a remaining path; scarce-band fallback is explicit. Balance sides without leaking winners.

## 7. Request ownership, concurrency and replay

1. Reserve session/operation/idempotency key and body hash in a short transaction, assigning a stable game ID. Changed bodies conflict.
2. Acquire a bounded expiring request-owned execution lease/fencing token atomically. Release the transaction before IO. Persist usage reservations so retries/restarts cannot evade budgets.
3. Active HTTP generation awaits bounded work. Return ready only after private pool/first-round publication commits. A ready duplicate returns its saved game. A live duplicate may receive 202 GENERATION_IN_PROGRESS and observation/retry guidance, not a promise of queued completion.
4. If the handler dies or cancellation stops it, the reservation survives. Explicit retry may reclaim an expired claim under bounded attempts. No background task is assumed to survive after a response.
5. Publication rechecks session, deadline, evidence expiry and current fence; a stale claimant cannot publish after replacement or session clear.

Measure lease/attempt/connection/admission limits during implementation. Release permits on success/failure/cancellation. If generation cannot reliably fit a request, design durable dispatch explicitly before adding it; do not silently resurrect AccessLife's worker.

Answer/advance use short transactions, unique acceptance and expected revisions. Identical retries return saved outcomes even after revision advancement; contradictory retries conflict. Score is recomputed from accepted answers, one point each, maximum five. Persist selected next round before returning; retries cannot reshuffle. No Qloo/model call occurs on answer, Next or shared replay.

Solo mode adapts among valid unused stored pairs. Shared mode freezes the creator's actual five/order/sides/query contexts/answers/scoring and validator versions. Each replay is guest-owned and fixed. Compare scores only within that definition, not unrelated adaptive games. This is casual play, not cheat-proof competition: external research/repeat play exist. Later provider/policy changes never rewrite active challenge answers.

## 8. GCP and repository migration

This is a documented baseline to re-inventory in Prompt 16, not a Prompt 1 live inventory/mutation. Project `project-bb13ecd8-9d67-408d-9a7`, default region `asia-south1`; PharmaGuard resources are unrelated/out of scope.

| Historical resource | Target/action | Preservation requirement |
|---|---|---|
| saimaharana4/accesslife-ai | Rename to saimaharana4/taste-duel in Prompt 17 if available | Preserve history/tag/licence and coordinate WIF trust first |
| accesslife-web/api | New tasteduel-web/api | Candidate verification before service cutover, no random cross-product traffic |
| Dedicated accesslife-db SQL instance | Reuse same billed PostgreSQL instance | Keep legacy physical name; no second instance for branding |
| accesslife logical DB/user | New tasteduel DB; migration-owner/runtime-DML split | Old resources stay at stable/moved Terraform addresses until deliberate retirement |
| accesslife Artifact Registry | Reuse compatible registry or reviewed migration | Digest releases, priced retention and documented name exception |
| accesslife-qloo-api-key | Scoped retained reference or deliberate name migration | Copying key is not rotation; preserve required old readers |
| DB/password/worker-token secrets | Fresh new DB credentials where needed; retire old worker token later | Direct Secret Manager handling, reader/rollback checks before disable |
| Docs/backups buckets | No RAG docs needed; retain authorized backups/state | Lifecycle/rights checks, no cosmetic data deletion |
| Worker/tasks/reconcile/ingest/scheduler | Drain/retire in Prompt 20 | No accepted old work abandoned or inherited old jobs |
| SAs/WIF/monitoring/labels | New scoped identities, repo trust and Taste Duel operations | Both-label cost coverage and verified trust/readers |
| gs://accesslife-tfstate-project-bb13ecd8-9d67-408d-9a7/accesslife/state | Preserve existing bucket/prefix/ownership | Reviewed moved/import handling; no empty-state recreation |

SQL instance/bucket/secret IDs are not all renameable in place. Document immutable-name exceptions. Never change old logical DB/user resource names into destructive replacement or remove deletion protection for branding. Keep state migration separate from app identity changes.

Prompt 16 inventories/plans; Prompt 17 applies a saved foundation plan; Prompt 18 reviews image-dependent release changes. A new Cloud Run service's first revision cannot be assumed to receive zero-percent allocation. Bootstrap controlled maintenance/IAM or document the actual restricted initial allocation, then deploy tagged no-production-traffic candidates. Tags remain directly reachable; zero-percent is not access control. Candidate origins are exact/temporary and removed after release.

Use restricted GitHub OIDC/WIF with verified repository identity and intended branch/environment, no downloaded keys. Deploy permissions cover new services/jobs, required registry writes and service-account use, not project-wide administration. Rehearse compatible revisions/config/schema rollback before retiring old runtime. Recovery history/data is not an active second product.

## 9. Budget, operations and evidence

The **US$80 envelope is cumulative**: incurred AccessLife cost plus remaining shared SQL/storage/backups, Taste Duel runtime/models/API traffic, temporary overlap, builds, restore checks, currency and tax. The historical US$78.48 forecast through 5 November is not spare funding and omits part of judging in IST. Reprice through at least **6 November 2026, 10:15 IST**, plus required follow-up. Stop extra provisioning if the total fails. Alerts notify; they do not cap spending. Reconcile old/new labels, unlabeled usage and request/token ledgers.

Bound instances/concurrency, global provider/token admission, connection pools including migration/operations, image/cache/storage growth and log retention. Measure cold/warm timing separately. Logs contain safe correlation/game IDs, action/status/timing and rejection counts, never token/raw taste payload/hidden-answer dumps or chain-of-thought. Show truthful preparation stages.

Verify permitted-data backup retention and actual restore into a priced disposable target, never over live data. Logical export/restore does not prove managed Cloud SQL backup restore; record each result separately. Pin image digests, preserve compatible rollback targets and remove only verified disposable targets. Teardown remains deliberate, not automatic after submission.

Target freeze: 30 October. Submission target: 31 October 2026, 09:15 IST, subject to rules recheck. Maintain judging access through at least 6 November 10:15 IST and required follow-up within a reviewed cost window.

## 10. Replacement and verification gates

| Stage | Remove from active product when replacement passes | Required evidence |
|---|---|---|
| Prompts 3–4 | Planner/map/trip UI, unused MapLibre/chart/agent-graph imports | Original five-round fixture UI, visual/accessibility gate |
| Prompts 5–9 | AccessLife domain/schema/route/transport/weather/planning imports | New DB/contracts/engine/agent, concurrency and ownership checks |
| Prompts 6–10 | Place-specific Qloo and old generation composition | Typed MCP and genuine Taste Duel flow |
| Prompt 14 | MiniLM/ONNX/retrieval/ingestion assets, spatial/vector image requirement, old Compose worker | Reproducible new containers/CI, no remaining product imports/jobs |
| Prompts 16–19 | Old release commands and active branding | Cost/plan/WIF/candidate/public-release gates |
| Prompt 20 | Old worker/jobs/queue/scheduler/IAM and unused billed resources | Drain/readers/retention/rollback verified; shared SQL/state/secrets preserved |

Never delete original references, Git history, user data, installed reused-instance extensions or unrelated workloads for tidiness. Active product eventually stops importing accesslife; recovery stays in checkpoint/history and reviewed cloud policy.

Acceptance includes same-context winners/ties, no-repeat path feasibility, provider envelopes/auth/timeouts, agent veto/injection limits, pre-answer secrecy/post-answer recovery, duplicate requests/fencing/restart/session clear, exact replay/expiry, keyboard/mobile/reduced motion, rights, clean local runtime, real remote CI and actual cloud connectivity/recovery. Fixtures/provider spikes do not establish full integration; technical success does not establish popularity. Human fun/clarity claims need real consenting playtest observations.

## References and related specifications

### Prompt 2 source, capability and rights record

The dated [Qloo capability matrix](qloo-capability-matrix.md) pins the official kit/documentation commits and harness package, separates offline tool discovery from bounded live evidence, and records score, artwork, cache and challenge-policy limits. Its explicit result/status cells control feasibility claims; none establishes that the Taste Duel game, production adapter or agent has been implemented. In particular, strict MCP tool arguments are not interchangeable with raw Insights parameters, and the advertised documentation meta-schema is not a client API specification.

These references were collected in prompts.md for later recheck; Prompt 1 makes no fresh capability/licence/price/access claim.

- [Official Qloo kit](https://github.com/qloo/qloo-hackathon-kit), [MCP starter](https://github.com/qloo/qloo-hackathon-kit/blob/main/starter/mcp-client/README.md), [API access](https://github.com/qloo/qloo-hackathon-kit/blob/main/docs/API_ACCESS.md), [safe use](https://github.com/qloo/qloo-hackathon-kit/blob/main/docs/SAFE_USE.md).
- [Search](https://github.com/qloo/docs-public/blob/main/reference/get-search.md), [Insights](https://github.com/qloo/docs-public/blob/main/reference/insights-api-deep-dive.md), [affinity interpretation](https://github.com/qloo/docs-public/blob/main/docs/interpreting-affinity-scores.md), [Qloo terms](https://www.qloo.com/legal/terms).
- [Next.js components](https://nextjs.org/docs/app/getting-started/server-and-client-components), [Cloud Run authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service), [traffic/rollback](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration), [WIF pipelines](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines).

Related: [PRD](prd.md), [rules](rules.md), [phases](phases.md), [design](design.md), [memory](memory.md), [iteration prompts](prompts.md).

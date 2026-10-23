# AccessLife AI build phases

Revision 1 · 24 October 2026 · Phase 0 in progress; application and infrastructure phases have not started

## 1. How to use this plan

Finish a phase's exit checks before calling it complete. Parallel work is appropriate only after shared contracts are stable; provider retrieval may run concurrently, while identity matching, eligibility and publication have dependencies. A phase is a unit of delivery, not a requirement to create one service or branch per component.

The maintained documents live in `ai/`. Preserve the original reference files and exclude them from Git. This document describes future application paths; it does not imply they already exist. Keep completed work in [memory.md](memory.md), one or two lines per dated entry.

| Phase | Main output | Depends on |
|---|---|---|
| 0 | Documentation and public repository | Agreed scope |
| 1 | Five-city coverage dossier and contracts | 0 |
| 2 | Next.js foundations and intake | 1 contract baseline |
| 3 | Discovery, map/list and evidence components | 2 and normalized candidate fixtures |
| 4 | Backend adapters and retrieval | 1; can overlap 2–3 |
| 5 | Durable planning and replanning | 3 and essential Phase 4 providers |
| 6 | Five-city and multi-city trip integration | 5 |
| 7 | Managed GCP deployment and verified release | 6, cost gate and cloud prerequisites |

Documentation dependencies define behavior before cloud creation. A minimal provisional deployment may occur during Phase 7 integration, but it cannot bypass its cost and security gates.

## 2. Phase 0 — Specifications and repository

**Goal:** Give an implementer a coherent, self-contained starting point.

Deliver the six maintained documents in `ai/`, a root README, MIT license, placeholder `.env.example` and `.gitignore`. Create public `saimaharana4/accesslife-ai`, default branch `main`. Publish only an explicit file allowlist. Do not scaffold the app or provision cloud services in this first delivery.

Exit checks:

- [x] Specifications agree on London, New York, Paris, Berlin and Chicago, managed GCP, US$80 and user-arranged inter-city transfers.
- [x] Local documentation links resolve; source references use primary sources without broken copied citation markers. Qloo account/API checks remain Phase 1 work.
- [x] Git's explicit allowlist includes the six maintained specifications and excludes the three original reference files.
- [x] The publication allowlist contains no secrets, state, datasets, model weights or credential history; the pattern scan passed.
- [ ] GitHub repository is public, `main` is pushed, MIT is detected and local/remote heads agree.
- [ ] README and memory distinguish completed foundation work from unimplemented features.

## 3. Phase 1 — Coverage and shared contracts

**Goal:** Establish what the five-city product can truthfully support before building its full UI.

### City capability package

Create configuration for each city with slug, name, IANA time zone, chosen supported district geometry, source identifiers, provider capabilities and readiness state. Start all at `unvalidated`; the initial source leads are:

| City | Transit/access source lead | Required validation |
|---|---|---|
| London | TfL Unified API and official access information | Token/terms, supported journey filters and unresolved last-mile evidence |
| New York | MTA GTFS, elevator/access/service information | Feed validity, stop/trip facts and bounded route computation |
| Paris | Île-de-France Mobilités PRIM | Account/license, API/feed permissions and station/vehicle coverage |
| Berlin | VBB open data and lift information | Current feed/API access and usable feature-level evidence |
| Chicago | CTA developer feeds and access information | Terms, API keys where needed and stop/vehicle/facility coverage |

For each city, select a compact district based on actual overlap of venue access sources, routes and Qloo entities. Download only bounded samples permitted by source terms. Record candidate counts, ambiguous crosswalks, missing attributes, refresh policy and source rights. Do not substitute a fixture result for a live Qloo coverage test.

### Backend and contract foundation

Choose and pin supported Node LTS and Python versions, package managers and framework dependencies. Scaffold FastAPI's domain/ports/application boundaries and a local PostgreSQL environment with PostGIS/pgvector. Use Pydantic for city, evidence, candidate, requirements, plan/run/event and trip schemas. Export OpenAPI and generate the frontend types.

Create provider capability contracts and sanitized candidate fixtures covering every status and at least one contradictory-source example. Include fixture provenance and replay labels. Define source-specific freshness rules and Qloo score comparability/retention from actual terms.

Exit checks:

- [ ] All five city registries exist with supported districts and documented source gaps.
- [ ] Live Qloo access and sample entity matching work, or an explicit release blocker is recorded.
- [ ] Each city has a credible evidence path for one half-day persona scenario; coverage is not assumed from dataset size.
- [ ] API schemas, units, timestamps, ownership and error envelope are agreed and contract-checked.
- [ ] Authentication requirements, data rights, map tile terms and provider keys are documented without exposing keys.

## 4. Phase 2 — Next.js foundations and intake

**Goal:** A user can enter the inputs needed for a safe plan.

Build from the outside inward:

```text
Next.js App Router
  Server layout and page shell
    Design tokens and accessibility preferences
      Button / Field / Input / Select / Dialog / Tabs / feedback primitives
        CitySelector / PersonaLauncher / SetupForm
          LocalDateTimeField / RequirementPicker / DistanceLimitFields
          RestIntervalField / TasteSeedPicker / InputReview
```

Set up strict TypeScript, Tailwind variables, shadcn React Aria base, form validation and generated API types. Keep public shell rendering on the server; isolate stateful controls. Use local/context UI state before adding a global store. Anonymous session establishment and reset are explicit actions.

Exit checks:

- [ ] All five city options show coverage/support state.
- [ ] Per-leg and total distances use separate fields; zero/missing/invalid values are handled correctly.
- [ ] Date/time validation uses city time zones and handles ambiguous/nonexistent local times.
- [ ] A user can launch a synthetic persona, edit its values and review structured inputs.
- [ ] Keyboard, focus, labels, 200% zoom and small-screen intake work; no placeholder-only fields.

## 5. Phase 3 — Discovery, place intelligence and evidence

**Goal:** Build the product's decision surface before decorative landing-page work.

```text
PlannerShell
  DiscoveryToolbar
    CityContext / ActiveFilters / Sort / ListMapTabs
  PlaceResults
    PlaceCard
      PlaceHeader / AccessFeatureList / TravelSummary
      TasteReason / FreshnessLabel / PlaceActions
  MapPanel (lazy client boundary)
    MapCanvas / PlaceMarker / RouteLayer / MapLegend / MapControls
  ContextPanel
    PlaceDetails / EvidenceDrawer
      SupportedClaim / SourceLink / SourceDates / ConflictNotice
  Shared states
    Skeleton / NoEligibleResults / PartialData / Retry / MapUnavailable
```

Build against normalized contract fixtures first, then connect live API responses without changing component contracts. Preserve attribution on the map and imagery. Selection synchronizes cards, markers and details, without unexpected focus movement. Opening a source explains exactly which claim it supports.

Exit checks:

- [ ] Confirmed, limited, inaccessible, unknown, conflicting and stale evidence states are readable.
- [ ] The list provides every action required to use the product without the map.
- [ ] Missing provider data is visibly different from an empty search result.
- [ ] Map failure preserves cards, evidence and itinerary; closing overlays restores focus.
- [ ] No raw provider payload or fabricated confidence percentage reaches a card.

## 6. Phase 4 — Providers, persistence and bounded retrieval

**Goal:** Replace contract fixtures with independently verified adapters.

Implement repositories and migrations for places/facts, crosswalks, documents/chunks, sessions, runs/events, immutable plans, trip revisions and bounded caches. Add adapters for OSM/places, official access evidence, city transit, Open-Meteo, Qloo, Vertex AI and object storage.

Keep transit capabilities city-specific. Use an authorized journey API where suitable; otherwise build a bounded feed-based route path with explicit transfer and walk/roll evidence checks. Do not claim a comprehensive routing engine in every city. A leg lacking mandatory evidence remains unresolved.

Build the ingestion pipeline: allowlist/rights → bounded download → deduplicate/parse → quota reservation → tokenizer-aware chunking → CPU embedding → staged validation → promote. Begin with the smallest useful corpus across the five supported districts. MiniLM defaults, 384-dimensional vectors and all quotas come from Architecture.

Create a 50-question retrieval evaluation set with 20 questions held out from tuning. Record actual Recall@5, citation correctness and query/ingestion timing. Use exact filtered vector search initially; add HNSW only on measured need.

Exit checks:

- [ ] Each adapter passes normalized contract tests and safe error/freshness handling.
- [ ] Qloo has real credentialed smoke evidence, auditable entity matching and correct score semantics.
- [ ] Structured access facts remain separate from general RAG guidance.
- [ ] Source permissions, attribution and retention are recorded; quotas reject excess safely.
- [ ] Migrations preserve prior data; no API implementation creates tables implicitly at startup.
- [ ] Retrieval results and limitations are reported honestly against the target, without tuning on held-out labels.

## 7. Phase 5 — Durable planning, progress and replanning

**Goal:** Connect the UI and providers into one correct local planning flow.

Build the LangGraph state and nodes in this dependency order: validate → independent retrieval → normalize/enrich → eligibility → taste ranking → itinerary construction → claim/constraint verification → transactional publication.

Implement Cloud Tasks dispatch abstraction, local deterministic task harness, durable checkpoint/run events, worker leases, idempotency, pending-dispatch reconciliation and cancellation. Cloud-specific resources are created only after the Phase 7 provisioning gate. Do not use an in-process background task as the production substitute.

Frontend components add `AgentProgressRail`, `ItineraryTimeline`, `TravelLeg`, `RestBreak`, `PlanValidationSummary`, `ConstraintEditor`, `PlanDiff` and `RetryRun`. A graph inspector is optional/lazy and shows public actions, not private reasoning.

Exit checks:

- [ ] Duplicate requests/deliveries publish at most one intended version.
- [ ] Crash after publication and before acknowledgement is safe; expired leases and failed dispatch reconcile.
- [ ] SSE reconnects replay ordered durable events; duplicate/stale events do not regress the screen.
- [ ] Cancellation/superseding requests cannot publish over a newer plan.
- [ ] Mandatory facts, distances, opening windows and required rests pass deterministic checks before confirmation.
- [ ] A 500 m → 200 m per-leg change creates a visible replan diff; failure preserves the last good plan.
- [ ] Provider deadlines, retries and global concurrency bounds are exercised.

## 8. Phase 6 — Five-city and multi-city integration

**Goal:** Meet the required breadth without pretending inter-city transfers are validated.

Connect every city registry and adapter to the same planner. Add `TripBuilder`, `CitySegmentList`, `CitySegmentCard`, `SegmentDateEditor`, accessible reorder buttons, `TransferGapNotice` and aggregate status. Attach exact immutable local plan versions to revisioned trip segments.

Add Impact Lab with same-snapshot baseline/Qloo rankings, candidate mapping/score disclosure, table-equivalent chart and provider state. A candidate with no Qloo mapping remains clearly marked; no rank movement is hard-coded.

Exit checks:

- [ ] Each of the five cities passes an evidence-backed half-day persona flow in its declared supported area.
- [ ] Twenty local golden cases, four per city, include unknown/conflict/failure conditions and no unsupported strong claims.
- [ ] At least two multi-city scenarios pass, including cross-time-zone and daylight-saving behavior.
- [ ] Segment reorder/delete/date/city changes preserve revision safety and invalidate affected references correctly.
- [ ] Every inter-city gap remains user-arranged and unverified; aggregate UI never claims a fully validated trip.
- [ ] Three real taste personas show actual Qloo behavior and any insufficient coverage honestly.
- [ ] Full core flow works on mobile and keyboard, without map/animation; all mandatory unknowns stay outside confirmation.

## 9. Phase 7 — Managed GCP and release

**Goal:** A publicly usable, recoverable app with measured release evidence.

Before creation, verify billing/credit availability, quotas, regional model support and a complete incremental forecast through judging against **US$80**. If it does not fit, stop provisioning and present the priced adjustment. Do not shrink required five-city functionality silently or reuse the unrelated PharmaGuard database.

Implement AccessLife-only Terraform for Cloud Run web/API/worker, separate Cloud SQL, Cloud Tasks/Scheduler, GCS, Secret Manager, Artifact Registry and WIF/service identities. Review resource diffs and cost; deploy pinned images with bounded scaling. Add CI lint/types/contracts/backend/scenario/build/accessibility gates and protected deployment with scoped identity.

Verify web → authenticated private API → durable worker → separate database, plus streaming through the same-origin web route. Check that unauthorized direct API/worker calls fail and cross-session resource access fails. Establish backup/restore, compatible migrations and image rollback.

Release exit checks:

- [ ] HTTPS demo works in incognito on a separate device, without a private network/local dependency.
- [ ] Actual Qloo requests are exercised; browser bundles and responses expose no API keys.
- [ ] All five-city/multi-city acceptance gates pass; unresolved limitations are visible.
- [ ] Full target-page axe checks and manual keyboard/mobile/zoom/reduced-motion/map-free checks pass.
- [ ] Warm/cold/queued timings, provider variability and retrieval metrics are recorded separately.
- [ ] Duplicate tasks, VM-independent Cloud Run instance restart, database restoration and rollback are demonstrated.
- [ ] Source, rights/attribution, license, pinned dependencies, migrations, seeds and executable local setup instructions are public.
- [ ] Project description states what is implemented and how Qloo changes results; no unsupported benefit claims.
- [ ] Demo availability and resource ownership are scheduled for review through judging and required follow-up.

Do not make a video a substitute for the functional app. Maintain an optional narrated walkthrough only after the core release works.

## 10. Calendar, risks and delivery discipline

The submission deadline is **31 October 2026 at 9:15 AM IST**. All dates below are targets, not completed work.

| Date in IST | Target |
|---|---|
| 24 October | Phase 0; begin coverage and API access checks when implementation is authorized |
| 25 October | Phase 1 baseline and Phase 2 intake foundations |
| 26 October | Phase 3 discovery and essential Phase 4 adapters |
| 27 October | Phase 5 thin end-to-end local plan with live Qloo |
| 28 October | Phase 6 five-city/multi-city integration and retrieval evaluation |
| 29 October | Phase 7 deployment, restore/resilience and external tests |
| 30 October | Feature freeze, final release checks and early submission |
| Through 5 November | Keep app usable for judging and required follow-up |

This schedule is tight for five cities and managed infrastructure. Missing Qloo access, uncertain route evidence or an over-budget forecast are critical-path blockers, not reasons to fabricate completion. Reduce decorative effects, corpus size and optional diagnostics first. Escalate any unmet required scope with concrete evidence; do not relabel previews as usable city plans.

On 3 November, review unused AccessLife resources without deleting the live demo. Final teardown follows documented backup/export checks and inventory; it never destroys unrelated shared-project resources.

Related documents: [PRD](prd.md), [Architecture](Architecture.md), [rules](rules.md), [design](design.md), [memory](memory.md).

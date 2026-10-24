# AccessLife AI product requirements

Revision 2 - 24 October 2026 - Local provisional planner implemented; release gates remain open

## Current implementation

Five-city intake, editable personas, discovery/evidence, deterministic eligibility, provisional itineraries, rest suggestions, versioned replanning, SSE progress and revisioned multi-city collections work locally. Actual Qloo search/tags/Insights calls and Vertex structured generation have passed live smoke checks. Optional Groq/OpenAI/Ollama adapters are implemented but unconfigured.

The sourced catalogue contains 15 real venues and 12 narrow feature summaries. Art/history Qloo matching smoke results: London 2/3, New York 1/3, Paris 2/3, Berlin 2/3, Chicago 3/3. Unmapped candidates have no fabricated scores. This measures matching, not recommendation uplift or accessible-route coverage.

Every current outing remains **provisional**. Opening windows, route geometry, travel duration, door-to-door access and actual rest seating remain unverified. Straight-line distance can reject an impossible allowance; it cannot certify a feasible route. Mandatory unknown, conflicting and stale evidence never becomes eligible because of taste. No city is coverage-complete.

The requirements below remain release targets wherever not verified in memory.md. GCP rollout was subsequently authorized; its actual results are recorded separately. Accounts, bookings, collaboration, verified inter-city routing, multilingual retrieval and live alerts remain later work.

This maintained specification lives in `ai/`. The original local reference files remain unchanged and excluded from Git; only the six maintained specifications in this folder are published.

## 1. Product decision

Build an accessible, culturally personalized outing planner for **London, New York, Paris, Berlin and Chicago**. A user chooses a city, time window, mobility requirements and interests. The application gathers evidence, rejects unsuitable options, uses Qloo to rank eligible places and constructs an explainable local plan. Users can combine local plans into a multi-city trip, with travel between cities left for them to arrange.

This delivery establishes requirements and a public repository. It does not establish live data coverage, working providers or deployed infrastructure. The five-city scope and managed GCP deployment replace the earlier one-city and single-VM proposals.

### The problem

An entrance marked wheelchair-accessible does not establish whether the toilet, lift, route, boarding stop and vehicle meet a particular person's needs. Conventional recommendations also treat mobility suitability and cultural interests as separate problems. Users and caregivers must reconcile fragmented information themselves.

AccessLife should reduce that work while preserving uncertainty. It supports planning decisions; it cannot guarantee physical access or replace checking conditions with the venue or operator.

### Audience

| Audience | Need | Product implication |
|---|---|---|
| Wheelchair users | Specific entrance, toilet, lift and route requirements | Separate feature facts and journey-leg checks |
| Older adults and people with limited stamina | Short travel legs, seating, breaks and clear instructions | Per-leg and total limits; rest segments; readable controls |
| Caregivers and companions | Understand and edit another person's explicit requirements | Transparent structured inputs; no diagnosis inference |
| Hackathon judges | Try a coherent end-to-end product quickly | No-signup personas, reset controls and visible provider state |

Three synthetic demo personas represent a step-free cultural visitor, an older adult who needs frequent rests, and a caregiver planning a food-and-museum outing. They are test inputs, not fictional testimonials or asserted customer research.

## 2. Scope and success criteria

### MVP commitments

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-01 | Five-city selection | All five cities appear in the selector with time zone, supported area and coverage status. Each passes a local planning scenario before release. |
| FR-02 | Anonymous intake | A visitor can launch a persona or enter requirements without signup, review interpreted inputs and reset the session. |
| FR-03 | Explicit mobility limits | Store mandatory access features, assistance tolerance, maximum distance per leg, total distance, rest interval and transfer tolerance independently. |
| FR-04 | Evidence-led discovery | Every place card exposes available access features, unknowns, source links, freshness and eligibility reasons. |
| FR-05 | Real taste personalization | Resolve user-selected cultural interests to Qloo entities and use supported returned signals in ranking. Show provider state and unmapped candidates honestly. |
| FR-06 | Local itinerary | Produce a bounded half-day plan of two or three stops, including time windows, travel legs and needed rest breaks, or explain why one cannot be validated. |
| FR-07 | Deterministic eligibility | No confirmed stop or leg fails a mandatory requirement. Missing or conflicting mandatory evidence stays outside the confirmed plan. |
| FR-08 | Replanning | A structured constraint change creates a new run and immutable plan version; preserve the prior version and show the changes. |
| FR-09 | Multi-city trip | Create an ordered trip with city segments, local dates and attached plan versions; support changing or removing segments. |
| FR-10 | Transfer gaps | Each inter-city handoff is labeled user-arranged and unverified. No journey duration, accessibility or transfer feasibility is invented. |
| FR-11 | Qloo Impact Lab | Compare baseline and Qloo rankings using the same eligible candidate IDs, evidence snapshot and constraints. Explain genuine movement or absence of movement. |
| FR-12 | Visible activity | Show queued/running/completed/partial/failed/cancelled states, meaningful tool progress and evidence count, without private chain-of-thought. |
| FR-13 | Resilient use | Support reconnecting progress, map failure, empty eligibility, unavailable providers and stale evidence without false success. |
| FR-14 | Inclusive interface | Core flow works by keyboard, at 200% zoom, on mobile and without map interaction or animation. |
| FR-15 | External delivery | Public HTTPS app works in incognito on a separate device, backed by real Qloo calls and reproducible public source. |

“Confirmed” means supported by the documented evidence policy at the recorded time. It is not an independent audit or a promise that facilities remain unchanged.

### Five-city coverage policy

The initial city registry uses these stable identifiers and IANA time zones:

| City ID | Display name | Time zone | Initial source leads |
|---|---|---|---|
| `london` | London | `Europe/London` | OSM, official venue pages, TfL Unified API |
| `new-york` | New York | `America/New_York` | OSM, official venues, MTA GTFS and access/service information |
| `paris` | Paris | `Europe/Paris` | OSM, official venues, Île-de-France Mobilités PRIM |
| `berlin` | Berlin | `Europe/Berlin` | OSM, official venues, VBB open data and lift information |
| `chicago` | Chicago | `America/Chicago` | OSM, official venues, CTA data and service/access information |

These are source leads, not verified coverage. The registry starts with every city `unvalidated`. Phase 1 records provider access, source rights, Qloo crosswalks, supported districts, required evidence and test outcomes. A city moves to `limited` or `ready` only through measured results.

Start with a compact documented central district in each city. Do not claim citywide wheelchair routing. Readiness requires at least one evidence-backed half-day scenario for a declared persona, plus explicit failure/unknown cases. All five cities need usable local planning at release; previews do not satisfy this requirement. Record any shortfall as a release blocker rather than silently reducing the scope.

Venue data abundance does not prove usable routing or taste coverage. A GTFS feed is not a journey planner, and accessible stops alone do not establish an accessible door-to-door route.

## 3. Core user journeys

### First local plan

1. Open the landing page and launch a persona or start a new plan.
2. Select a city and supported district; choose a local date and outing window.
3. Enter explicit mobility requirements and interests. Clarify missing critical inputs rather than guessing them.
4. Review the structured interpretation before planning.
5. Watch concise progress while providers gather facts and Qloo resolves interests.
6. Compare eligible places in a list, optionally using the synchronized map.
7. Inspect feature-level evidence and any uncertainty, then open the proposed itinerary.
8. See validated stops, travel legs, rest breaks and the distinction between factual support and personal preference.

### Change a requirement

The user lowers maximum per-leg distance from 500 m to 200 m. AccessLife starts a versioned replan and reruns affected route and eligibility checks. The old plan remains available. The new plan shows removed/replaced stops and changed effort. A failed replan does not overwrite the last successful plan.

### Create a multi-city trip

The user adds London and Paris on different dates, in the order they want to visit. Each city segment has its own time zone, plan and validation status. The app presents a transfer placeholder between them: “Travel between these cities is yours to arrange; timing and accessibility have not been verified.” Local plans may be validated while the trip's transfer status remains `unverified`.

Changing a segment's city invalidates its attached plan. Changing dates triggers a new local plan because opening windows, transport and weather may differ. Moving segments validates chronological order but does not prove the transfer can be made. Ambiguous daylight-saving times require explicit resolution.

### Understand Qloo's contribution

The user opens the Impact Lab. Both columns use the same eligibility snapshot. The baseline ranks by shortest travel duration, then category preference and stable place ID; the Qloo ranking adds supported taste ordering over mapped candidates. Show matched seed entities, provider state, comparable scores where permitted and rank changes. An unchanged order is a valid result, not an error to conceal.

## 4. Trust, data and recommendation behavior

### Access and evidence

- Represent each feature as `confirmed`, `limited`, `inaccessible` or `unknown`; represent source conflict separately.
- A mandatory requirement passes only with compatible evidence and no unresolved material conflict. “Limited” requires a supported, explicitly accepted accommodation; never treat it as an automatic pass.
- Unknown information is not the same as inaccessible, but cannot satisfy a mandatory condition.
- Preserve source URL, provider identifier, source type, retrieval time, source update time when known, rights and transformation version.
- Distinguish “retrieved” from “verified.” Do not display a scrape timestamp as a venue inspection date.
- RAG supplies attributable guidance; it cannot certify today's lift operation, pavement conditions or opening hours.

### Qloo and ranking

Maintain an auditable place-to-Qloo crosswalk using names, location and provider identifiers. Ambiguous matches remain unresolved. Do not assume every OSM object exists in Qloo.

Only eligible candidates enter preference ranking. Preserve returned score semantics and the comparability scope; do not convert affinity into a probability of enjoyment. Unmapped candidates have no invented taste score. Any deterministic secondary rules and unmapped ordering must be disclosed in the Impact Lab.

The development provider may match explicit categories and text. Label it “Development taste engine.” A saved-response mode says “Replay.” Neither qualifies as the real Qloo submission path.

### Provider degradation

| Failure | Required behavior |
|---|---|
| Qloo unavailable | Offer clearly labeled generic ranking if useful; mark live Qloo unavailable and disable unsupported contribution claims |
| Missing mandatory access/route evidence | Keep affected options out of the confirmed itinerary; show verification-needed alternatives |
| Weather unavailable | Show the missing check; any weather-dependent mandatory condition remains unresolved |
| RAG unavailable | Omit guidance citations; continue only where structured factual checks remain sufficient |
| Generation API unavailable | Render deterministic plan facts and a template explanation if validation succeeds |
| No eligible candidates | Explain unmet requirements and allow explicit edits; never relax mandatory constraints silently |
| Map unavailable | Preserve list, evidence and itinerary functionality |

## 5. Quality, privacy and operational targets

These are acceptance targets, not measured results:

| Area | Target and measurement |
|---|---|
| Factuality | Zero unsupported strong access claims across 20 golden local cases, four per city; retain evidence IDs and results |
| Constraints | Every confirmed stop and leg passes the deterministic mandatory-feature, timing and distance checks |
| Multi-city | Test at least two multi-city trips, including a cross-time-zone and daylight-saving boundary case |
| Qloo influence | Exercise three taste personas; publish real supported effects and coverage gaps without forced rank changes |
| Retrieval | Held-out Recall@5 target at least 0.85 on 20 held-out queries from a 50-question evaluation set |
| Planning | Target first live progress within 1 second after stream connection; warm-run p95 below 20 seconds at three active local runs; hard run deadline 30 seconds |
| Queue/cold starts | Report separately from planning latency; make no subsecond queued or cold-start guarantee |
| Web | Target LCP ≤2.5 s, INP ≤200 ms and CLS ≤0.1 under recorded device/network conditions |
| Accessibility | Automated axe checks plus manual keyboard, focus, 200% zoom, reduced-motion and map-free tests |
| Recovery | Demonstrate duplicate-task handling, reconnectable progress, worker restart and a database restore before release |

Use synthetic personas by default. Keep user accessibility preferences session-scoped, out of the knowledge corpus and out of ordinary logs. Send Qloo only the taste/location information necessary for its task, without mobility details. Anonymous sessions expire after 24 hours by default; users can clear them immediately. Document backup expiry separately so “clear session” does not imply historical backups are rewritten instantly.

The initial retained corpus is curated English material. Source titles/excerpts may remain in their original language with a clear label. General multilingual retrieval is later scope.

## 6. Delivery requirements and future work

The [official rules](https://qloo.devpost.com/rules) require a working Qloo-integrated agentic application, functional demo link, public open-source repository and project description. The [overview](https://qloo.devpost.com/) requires externally published access and says a video is not required. Requirements were reviewed on 24 October 2026; verify again before submission.

Feature freeze target: **30 October 2026**. Submission deadline: **31 October 2026, 9:15 AM IST**, equivalent to 30 October at 11:45 PM EDT. The official rules and schedule differ on the precise judging end time; preserve access through 5 November and any required organizer follow-up. A 3 November cleanup must not remove the working demo.

The initial GCP target is **US$80 incremental spend through judging**, excluding existing unrelated resources. A priced regional forecast must pass before provisioning; documented targets do not guarantee that five cities and managed services fit that envelope.

### Deferred features

| Later capability | Prerequisite |
|---|---|
| Verified inter-city rail/air/coach routing | Authorized transport providers, assistance/transfer evidence and jurisdiction-specific validation |
| Booking and payments | Provider agreements, payment integration and separate product/security review |
| Accounts, shared plans and caregiver collaboration | Identity, authorization, retention and consent design |
| Live journey monitoring | Reliable realtime feeds and notifications, plus recovery from stale updates |
| User accessibility reports | Moderation, provenance, abuse controls and correction workflow |
| Multilingual retrieval | Suitable embeddings, per-language evaluations and new corpus versions |
| More cities and broader districts | The same source-rights, Qloo-mapping and local acceptance gates |
| Advanced visuals | Measured value without weakening accessibility or performance |

## 7. Primary source register

- [TfL Unified API](https://tfl.gov.uk/info-for/open-data-users/unified-api)
- [MTA developer resources](https://www.mta.info/developers)
- [Île-de-France Mobilités PRIM GTFS](https://prim.iledefrance-mobilites.fr/en/reutilisations/reutilisation/gtfs)
- [VBB digital services](https://unternehmen.vbb.de/digitale-services/)
- [CTA developer center](https://www.transitchicago.com/developers/)
- [Qloo developer guide linked by the organizer](https://docs.qloo.com/reference/qloo-llm-hackathon-developer-guide)
- [OSM attribution and licensing](https://www.openstreetmap.org/copyright)
- [GTFS accessibility](https://gtfs.org/getting-started/features/accessibility/)
- [Open-Meteo terms](https://open-meteo.com/en/terms)

Dataset existence is established by these public sources; account access, field completeness, redistribution permission for each asset and usable five-city coverage remain implementation checks.

Related documents: [Architecture](Architecture.md), [engineering rules](rules.md), [phases](phases.md), [design](design.md) and [project memory](memory.md).

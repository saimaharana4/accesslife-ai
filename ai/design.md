# AccessLife AI design specification

Revision 1 · 24 October 2026 · Status: intended design, no screens implemented

## 1. Product experience

Use a calm, readable map-and-itinerary workspace with welcoming travel imagery and explicit evidence. The core questions are: where could I go, does it meet my requirements, and why is it recommended? Structured cards and timelines carry decisions; conversational input is an optional way to describe intent.

The five cities are London, New York, Paris, Berlin and Chicago. The city selector is always discoverable, with time zone, supported area and coverage state. Changing a city must not silently preserve an incompatible plan. A multi-city trip has independent local plans and visible user-arranged, unverified transfer gaps.

This specification lives with the other maintained files in `ai/`. Original reference files remain local, ignored and unchanged. Build one coherent design system rather than combining unrelated template styles.

## 2. Color, typography and layout tokens

### Light theme

| Semantic token | Value | Use |
|---|---|---|
| `canvas` | `#F7F8FA` | Page background |
| `surface` | `#FFFFFF` | Cards, dialogs and evidence panels |
| `text` | `#172033` | Main reading text |
| `text-muted` | `#475569` | Secondary text that still meets contrast |
| `primary` | `#0F766E` | Main actions and selected navigation |
| `primary-hover` | `#115E59` | Hover/pressed action surface |
| `on-primary` | `#FFFFFF` | Text on primary buttons |
| `taste` | `#6D28D9` | Cultural preference information |
| `taste-surface` | `#F3E8FF` | Taste explanation panels |
| `warning` | `#92400E` | Uncertainty and verification-needed text |
| `warning-surface` | `#FEF3C7` | Warning panels |
| `danger` | `#B91C1C` | Failed requirements, destructive actions |
| `positive` | `#166534` | Supported success state, always text-labeled |
| `focus` | `#1D4ED8` | Visible keyboard focus |
| `control-border` | `#64748B` | Necessary control boundaries |
| `divider` | `#CBD5E1` | Decorative separators only |

Teal marks actions, not a blanket accessibility guarantee. Violet marks taste, not eligibility. Every status includes text and an icon; color is supplemental. Verify contrast in the final rendered compositions, including overlays, disabled states and chart labels. Target at least 4.5:1 normal text and 3:1 large text/necessary nontext boundaries under applicable WCAG criteria.

### Themes and preferences

Light is the default. High-contrast mode uses white surfaces, `#000000` primary text, `#334155` secondary text, `#115E59` primary actions, `#000000` control borders and `#1D4ED8` focus. Remove glass/blur and decorative shadows in that mode. Do not invert map tiles as an accidental dark theme.

Respect system reduced-motion and forced-colors settings. Add user controls for reduced motion and reduced transparency without disabling essential state feedback. Store only these nonsensitive display preferences locally. A separate dark theme is deferred until its entire state matrix can be checked.

### Typography

Use the system sans-serif stack initially: `ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. No external font request is needed. Use tabular numerals for times and distance comparisons. Avoid all-caps passages and thin/light body text.

| Role | Size / line height | Weight |
|---|---|---|
| Page heading | 40/48 px desktop, 30/38 px mobile | 700 |
| Section heading | 28/36 px | 700 |
| Card title | 22/30 px | 600 |
| Body | 18/28 px | 400 |
| Controls | 18/26 px | 600 for actions |
| Secondary body | 16/24 px | 400 |
| Metadata | 14/22 px minimum; prefer 16/24 for important facts | 400 |

Use relative CSS units so browser zoom works. Font sizes are product defaults, not a claim that WCAG mandates 18 px. Long prose stays around 65–75 characters per line and aligns left.

### Space, shape and interaction

- Base spacing: 4 px, then 8, 12, 16, 24, 32, 48 and 64 px.
- Primary control target: at least 48 × 48 CSS px; clear spacing between adjacent actions.
- Card radii: 16 px standard and 24 px large; input/control radius 12 px.
- Focus: visible 3 px outline with 2 px offset; never hidden by sticky panels.
- Cards: subtle border and restrained shadow; evidence remains opaque.
- Motion: 150–250 ms for drawer/card/rank state transitions; instant or simple opacity change in reduced-motion mode.
- Glass: navigation/short controls only, roughly 85–95% opacity over imagery, with an opaque fallback. Avoid blur on large scrolling reading surfaces.

## 3. Routes and responsive screens

| Route | Primary job | Core components |
|---|---|---|
| `/` | Explain value and launch a useful flow | Hero, honest planner preview, PersonaLauncher, primary CTA and data/Qloo explanation |
| `/plan/new` | Collect inputs | CitySelector, LocalDateTimeField, RequirementPicker, DistanceLimitFields, TasteSeedPicker and review |
| `/plan/[id]` | Discover and understand a local plan | PlannerShell, PlaceResults, MapPanel, ItineraryPanel and ContextPanel |
| `/trip/new` | Create ordered city/date segments | TripBuilder and CitySegmentEditor |
| `/trip/[id]` | View/edit the multi-city aggregate | CitySegmentList, TransferGapNotice, local statuses and attached plan versions |

Evidence and Impact Lab open as routed/dialog context inside the planner, with keyboard/deep-link state preserved. Agent details are optional and lazy. Do not add separate dashboards, profile/account pages or a live-journey screen to the MVP simply because earlier research lists them.

### Desktop at 1280 px and above

Use a stable header with city/trip context and help/settings. The local planner has an approximately 320 px itinerary/results rail, a flexible map/workspace and an optional 360 px detail panel. The map shrinks or collapses before text becomes unreadable. Keep the primary Generate/Replan action and coverage summary visible without obscuring content.

### Tablet from 768 to 1279 px

Use two visible panes at most. Evidence/details replace the secondary pane or open an accessible sheet. The same data model drives list/map selection. Keep input fields and source dates readable without horizontal page scrolling.

### Mobile below 768 px

Use list/map/plan tabs with the list as the default. Open place details in a bottom sheet or full-screen dialog; complex filters use a full-screen sheet. Trip segments stack vertically with explicit reorder buttons. Keep selected place and scroll position when switching views, without forcing a map fly-to animation.

### Server and client boundaries

Server-render page shell, route metadata and initial nonsensitive catalogue data. Isolate interactive forms, map, planner edits, SSE subscription and optional visualizations in client components. Session-specific output must not enter public shared caches. Dynamic map loading with SSR disabled belongs inside an appropriate client boundary, not a Server Component using a browser-only API.

## 4. Component hierarchy and responsibilities

```text
AppShell (server layout)
  AppHeader / SkipLink / DisplayPreferences
  SetupPage
    PersonaLauncher
    PlanSetupForm
      CitySelector / CoverageNotice / LocalDateTimeField
      MobilityRequirements
        AccessFeaturePicker / LimitationConsent
        MaxLegDistanceField / TotalDistanceField / RestIntervalField
      TasteSeedPicker / InputReview
  PlannerShell (interactive region)
    PlannerToolbar / ProviderStatus / CoverageNotice
    PlaceResults
      PlaceCard
        PlaceHeader / AccessFeatureList / TravelSummary
        TasteReason / FreshnessLabel / AddToPlanButton
    MapPanel (lazy)
      MapCanvas / PlaceMarker / RouteLayer / MapLegend
    ItineraryPanel
      ItineraryTimeline / ItineraryStop / TravelLeg / RestBreak
      ValidationSummary / ConstraintEditor / PlanDiff
    ContextPanel
      PlaceDetails / EvidenceDrawer / ImpactLab
    AgentProgressRail
      AgentStep / RetryRun / AgentInspector (lazy)
  TripWorkspace
    CitySegmentList
      CitySegmentCard / SegmentDateEditor / SegmentActions
      TransferGapNotice
    TripValidationSummary
```

### Shared primitives

Build Button/IconButton, labeled fields, Input/NumberField, Checkbox/RadioGroup, Combobox/Select, Tabs, Dialog/Sheet, Alert, Card, Badge, Skeleton, EmptyState and StatusAnnouncement. Use shadcn/React Aria semantics and test the actual compositions. An icon-only action always has an accessible name and adequate target area.

### Domain component contracts

| Component | Receives | Responsible for |
|---|---|---|
| `CitySelector` | Registry cities and selected ID | City/time zone/coverage choice; never claims untested readiness |
| `PlaceCard` | Normalized `CandidateEvidence` view model | Name, feature facts, travel effort, taste rationale and actions |
| `AccessFeatureList` | Feature facts and requirements | Required/optional distinction, status, conflict and evidence links |
| `EvidenceDrawer` | Evidence record and exact claim | Source type/rights, retrieval/update dates and permitted excerpt |
| `TravelLeg` | Normalized leg and validation | Duration/distance, mode, boarding/vehicle/walk links and unknowns |
| `ItineraryTimeline` | Published plan version | Stops, arrival windows, rests and overall local validation state |
| `PlanDiff` | Prior/new immutable versions | Changed stops, time, travel effort and constraint results |
| `ImpactLab` | Same-snapshot baseline/Qloo result | Honest rank comparison, mapped inputs, missing scores and provider state |
| `AgentProgressRail` | Ordered public run events | Concise stage/status feedback, cancellation and retry |
| `TransferGapNotice` | Neighboring trip segments | User-arranged, unverified transfer status; no guessed feasibility |

Components do not receive raw OSM, Qloo, GTFS or weather payloads. Normalize at backend boundaries and map generated API types into small rendering props. Keep source/eligibility calculations outside JSX.

## 5. Information hierarchy and copy

Place cards prioritize: place name → mandatory access features → unresolved conditions → journey effort → taste reason → source freshness → actions. Use real, properly licensed imagery only when it does not delay important facts. No decorative star ratings or “open now” label without source support.

| State | Example wording | Action |
|---|---|---|
| Confirmed fact | “Step-free entrance: supported by venue information” | View source |
| Limited | “Entrance access has conditions” | Read conditions and explicitly accept if compatible |
| Inaccessible | “This entrance does not meet your step-free requirement” | View alternatives |
| Unknown | “Accessible toilet information is missing” | View available sources; keep out of confirmed plan if required |
| Conflict | “Sources disagree about entrance access” | Compare the statements and dates |
| Generic fallback | “Development taste engine — Qloo is unavailable” | Retry live ranking; no Qloo-powered claim |
| Transfer gap | “Travel between London and Paris is yours to arrange” | Show dates and unverified status |
| Replan failure | “The new limits could not be met. Your previous plan is still available.” | Edit requirements or view prior plan |

These are copy examples, not live venue assertions. Use plain terms with short definitions where needed: “Per-leg distance is the maximum walking or rolling distance between travel steps.” Do not expose environment variables, stack traces, Terraform or internal provider codes in normal user flows.

Show separate access, travel, weather and taste information instead of one opaque overall percentage. A source date is labeled “Retrieved” unless it really describes an observation/update. Avoid “safe route,” “guaranteed accessible,” “94% chance you'll love it” and “verified today” without the corresponding evidence.

## 6. Interaction and state matrix

Every applicable component designs these states before implementation:

| State | Required rendering and behavior |
|---|---|
| Initial | Clear purpose, visible input labels and next action |
| Loading | Skeleton/progress with stable layout and accessible state; no fake output |
| Queued | Explain that the run is waiting; allow cancellation; do not show it as tool execution |
| Partial | Preserve useful facts, list missing checks and suppress unsupported confirmation |
| Success | Display the published version and validation/evidence summary |
| Empty | Explain no results versus no eligible results; offer relevant explicit edits |
| Error | Safe action-oriented message, retained user input and appropriate retry |
| Stale | Show source freshness limitation and refresh option; do not hide previously published history |
| Cancelled | Stop live progress and preserve the last published plan |
| Reconnecting | Keep current content; replay new events without duplicated cards or announcements |

Generation and replan buttons prevent accidental duplicate submission while preserving explicit idempotent retry. SSE updates do not move keyboard focus. Ignore events for obsolete run generations. Replace a plan only after server publication; preview/failed results cannot silently replace the confirmed itinerary.

Map marker/card selection shares a stable selected-place ID. A selected marker opens details without making the map the only interaction path. Draw only provider-supported geometry, and label unverified segments; never style a straight line as an assured accessible route.

Reorder actions have Move up/Move down buttons in addition to any drag behavior. Dialogs manage focus and return it to the launcher. Prefer native/primitive keyboard conventions rather than custom shortcuts that interfere with assistive tools.

## 7. Visualizations and agent activity

- `RankDeltaChart`: baseline rank → Qloo rank over identical candidate IDs, with an equivalent table. No fabricated movement or similarity graph.
- `RouteEffortChart`: each walking/rolling distance against the explicit per-leg cap; also show the total separately in text.
- `EvidenceCoverageBar`: known/limited/unknown counts with exact labels; conflict and stale state are not reduced to a percentage of safety.
- `AgentProgressRail`: public action, status, elapsed time and evidence count. Show “Checking venue sources,” not hidden chain-of-thought.
- Optional `AgentGraph`: lazy tool dependency/status view, sanitized and available on demand. Detailed operational errors remain protected.

Provide plain textual summaries and tables so graphs are optional. Prefer short state transitions rather than continuous pulsing, automatic carousels or background motion. Disable nonessential effects when motion/transparency preferences require it.

## 8. Infrastructure behavior visible to users

The browser uses same-origin Next.js forwarding to the private API. It never receives Qloo/Vertex secrets. Session-specific screens and event streams are not cached publicly. A visible provider state distinguishes live, cached, replay, development, unavailable and stale where applicable.

Cold starts and queue waits have honest waiting states; do not invent progress percentages. On reconnect, resume from durable event sequence. If the session expires, explain it and offer a fresh persona; never restore another user's data. Clear-session controls cancel pending work and remove active personal records according to the documented retention policy.

Readiness/operations failure produces a usable error page with retry/help, not an endless spinner. The main UI should explain what the user can do; deployment revision IDs, IAM settings and database connection details belong in protected operations tools.

## 9. Design acceptance and references

Check every main route with keyboard only, screen-reader-oriented semantics/live announcements, 200% zoom, 320 CSS px reflow, reduced motion/transparency and forced-colors behavior. Test long names, no images, no map, slow providers, partial access evidence, unknown routes, Qloo outage, stale events and expired sessions. Run automated axe checks on complete target pages and inspect mobile/desktop screenshots manually.

Initial body/metadata/button contrast should be checked numerically, then rechecked in rendered components. An automated pass alone does not establish accessibility or correctness of venue information. Performance budgets and city acceptance targets are in the PRD.

### Implementation documentation

- [Next.js Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components)
- [Tailwind theme variables](https://tailwindcss.com/docs/theme)
- [shadcn CLI and primitive base](https://ui.shadcn.com/docs/cli)
- [React Aria accessibility primitives](https://react-spectrum.adobe.com/react-aria/)
- [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/)
- [Motion for React](https://motion.dev/docs/react)
- [Recharts](https://recharts.github.io/)
- [React Flow](https://reactflow.dev/)
- [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing)
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)

### Visual inspiration

Use the welcoming destination imagery and structured presentation of [Wix travel templates](https://www.wix.com/website-template/view/html/wh-1061), [Framer Wayfare](https://www.framer.com/marketplace/templates/wayfare/) and [Airbnb](https://www.airbnb.com/) as inspiration for original compositions. Use [Linear](https://linear.app/) as a reference for compact activity presentation. These links are inspiration, not endorsements, asset licenses or instructions to copy templates. No Wix/Framer subscription or external hosted-site dependency is part of the architecture.

Related documents: [PRD](prd.md), [Architecture](Architecture.md), [rules](rules.md), [phases](phases.md), [memory](memory.md).

# Taste Duel design specification

Revision 2 · 25 October 2026 · Synthetic visual prototype implemented; full game remains planned

## Status and visual goal

The fresh Taste Duel shell now implements this direction as a local synthetic prototype. It replaces the planner's web entry point; backend/cloud remain AccessLife. Planner screenshots and historical accessibility results cannot satisfy this game's gates. Preserve original reference files unchanged.

Follow [prompts.md](prompts.md), [prd.md](prd.md), [Architecture.md](Architecture.md) and [rules.md](rules.md); record real results in [memory.md](memory.md).

Prompt 2 found image metadata in both cross-domain samples but established no asset display/mirroring/social rights. Prompt 3 uses four original geometric SVGs and local Barlow Condensed 700/Manrope 400–600 with OFL notices and pinned provenance; see the [asset manifest](../third_party/taste-duel-assets.md). No optional image provider is needed. Use rank wording rather than automatically turning decimal affinity into a percentage. The [capability matrix](qloo-capability-matrix.md) records the unchanged partial live gate.

**Prompt 3 render refinement:** the first desktop render exposed a third grid child pushing the second poster into another row and the CTA below the fold. The second pass positions the registration star independently, restores paired covers and keeps the form/action visible. Mobile uses a smaller deliberate two-line headline at 390px and stacked choices at 320px. Titles stay outside the artwork, failed images receive an original title card, and reveal moves focus to its outcome heading. Loading/error pages disclose their static specimen status. This is one sample round, not the five-round fixture journey of Prompt 4. Actual captures/checks are recorded in memory and README; no human screen-reader or real-user enjoyment claim is made.

The experience should feel like **a cultural fight-night editorial**: one favourite, two oversized opponents, a quick prediction and a revealing result. Type and artwork create impact. The game must be understandable before explaining infrastructure.

## 1. Art direction and tokens

Use an original typographic wordmark, near-black canvas, warm paper text and electric chartreuse actions. A narrow DUEL seam between large choices is the signature composition. Five round pips create continuity; the result resembles a collectible printed ticket rather than dashboard statistics.

No enterprise sidebar, generic recommendation grid, statistics tiles, chat, decorative agent graph, gradient blobs, heavy glass, perpetual confetti or mandatory WebGL. Do not decorate the AccessLife planner. Inspiration does not license another product's trade dress or imagery.

| Token | Starting value | Use |
|---|---|---|
| `canvas` | `#101014` | Full-page ink background |
| `surface` | `#1B1B23` | Opaque reading/reveal/control surfaces |
| `text` | `#F4F1EA` | Main warm paper text |
| `text-muted` | `#B9B7C3` | Secondary readable labels |
| `primary` | `#DBFF5E` | Main action/selected emphasis |
| `on-primary` | `#101014` | Text on chartreuse |
| `secondary` | `#B9A9FF` | Restrained supporting accent |
| `incorrect` | `#FF9A9A` | Incorrect outcome with icon/text |
| `focus` | `#DBFF5E` | Focus ring, with dark offset where necessary |
| `control-border` | `#858191` | Necessary dark-surface boundaries |

Verify actual rendered combinations: ≥4.5:1 normal text and ≥3:1 large text/necessary nontext boundaries. This table is not a blanket contrast pass. Essential text sits on a readable surface, not an uncertain artwork gradient. Colour never solely communicates correctness, selection or failure.

Typography: locally hosted licensed **Barlow Condensed** display plus **Manrope** reading/control type, or verified equivalents with system fallbacks. Use at most two families and three necessary weights, retaining licence notices. Inspect screenshots after fonts load. Short fluid display approximately 48–112px; body 18px; useful metadata 14–16px. Relative units, comfortable line heights, tabular score numerals; no tiny long-name truncation or condensed paragraph text.

Spacing scale: 4/8/12/16/24/32/48/64px. Large arena cards: roughly 20–28px radius; compact controls: 10–14px. Result ticket perforation may use original SVG/CSS without complicating pointer/reading order. Primary actions have ≥48px hit areas; visible focus is unclipped and distinct from selection.

Dark is the deliberate default. Respect forced colours and reduced motion; do not promise an unimplemented light theme. Original subtle grain is optional and nonessential.

## 2. Routes and hierarchy

```text
AppShell (Server Component)
  SkipLink / Wordmark / HowItWorks / optional SoundOff
  / LandingSeedStage
      EditorialHeadline / GamePreview
      SeedCombobox -> SeedResults / SeedIdentity
      ExampleSeeds / StartDuel / PreparingState
  /g/[gameId] DuelArena (narrow client boundary)
      SeedChip / RoundPips / Question
      ChoicePair -> ChoiceCard x2 / DuelSeam
      PendingAnswer / RoundFeedback / ExplicitNext
      SaveDiscovery / SafeRetryNotice
  /results/[gameId] ResultTicket
      ActualScore / Discoveries / ChallengeCTA / PlayAgain
  /c/[slug] ChallengeInvitation
      SeedContext / CreatorScore / Expiry / GuestPlay
      same DuelArena in fixed mode
  /how-it-works
      RankingMeaning / SourcesAndAttribution / PrivacyAndExpiry
```

Use the same arena renderer for solo/fixed challenge. Props come from normalized generated contracts; raw Qloo envelopes never reach React. Server-render the shell/public metadata; narrow client boundaries contain active forms/gameplay. Private session/round data never enters shared page caches.

### Landing and seed selection

Suggested headline: **“One favourite. Five duels.”** Supporting line: “Can you predict what ranks higher in Qloo's taste graph?” The initial viewport provides wordmark, game promise, search and an intentional visual example. Label synthetic previews clearly. Example seeds are “Try a favourite,” not unsupported “Trending.”

Accessible combobox: visible label, arrows/Enter/Escape, stable loading/empty state, real type/identity metadata and explicit selection. A typed string alone is not a confirmed entity; director/person results cannot silently become films.

### Duel arena

Order: seed context → round number → question → two choices → accepted feedback → Next. Specify the target domain; both contestants are identifiable without artwork. Persistent title/type/useful date sit on a readable surface.

Each complete choice is one named button. Do not nest save/link buttons inside it. Hover/focus communicates interactivity; selected/pending communicates submission, not correctness. Disable competing submissions while pending. Server acceptance determines the reveal, with only supported authorized answered-round ranks/values.

Explicit Next gives time to read. No automatic advance, forced timer, speed points or meaning hidden in animation. Announce accepted result once; after Next focus predictably moves to the new question/first choice. Provider status must not steal focus.

### Reveal and result

Copy: “Correct prediction” or “Not this round,” then “Qloo ranked [winner] higher for [seed] in this query.” Never call the losing work bad or the player's taste wrong. Richer copy needs returned supporting evidence; otherwise the factual template is complete.

Result ticket prioritizes actual **n / 5**, discoveries and Challenge friends. A playful achievement name is an explicit score-derived game reward. No invented percentile, “taste IQ,” audience count, diagnosis or testimonial. Saves are optional session-owned user choices, not inferred enjoyment; explain their expiry where relevant.

### Challenge and sharing

Invitation shows seed, actual creator score, expiry and one-tap guest play. Replay uses fixed creator rounds/order/sides/context/scoring; no fresh adaptation. Expired/revoked links offer a new solo game without changing the old challenge.

Social image uses original branding/title art and authorized score. External imagery requires separate social-reuse rights. HTML/metadata/OG never contain answers, future choices, raw rankings, personal identifiers or session data. Copy-link fallback gives accessible feedback. Use the verified canonical origin, not an assumed purchased domain.

## 3. Responsive composition

| Viewport | Intended composition |
|---|---|
| 1440×1000 desktop | Central arena, two substantial artwork cards, narrow seam, readable question/pips/feedback; no dashboard rails. |
| 390×844 mobile | Compact header, large choices; two columns only if titles and 48px targets stay readable; Next never obscures content. |
| 320 CSS px/reflow | Stack where necessary, preserve comparison/question, no horizontal page scroll or required landscape. |
| High zoom/long names | Natural wrap/vertical scroll, no clipped title or fixed arena height hiding controls. |

Sticky controls cannot obscure feedback or focus. Reserve artwork aspect ratios to avoid layout shifts. Permitted responsive images fall back to intentional branded title cards on slow/failure paths, never broken-image gaps. Displaying an image URL does not establish its licence.

## 4. State and interaction matrix

| State | Required behavior |
|---|---|
| Initial | Clear task, seed input and next action |
| Search loading/empty/ambiguous | Stable space, preserved query, useful identity/refine action |
| Preparing | Truthful stages or neutral wait; no invented percentage/agent activity |
| Unanswered | Two identifiable choices; no delivered winner/rank/affinity |
| Submitting | Immediate pressed state, safe pending lock and retained round |
| Revealed | Accepted outcome/evidence, optional save, explicit Next |
| Recovering | Retained content and same request identity, reconcile with server state |
| Insufficient coverage | Explain unavailable five-round set, choose another seed; no fake result |
| Provider unavailable | Useful retry/new-seed action; preserve accepted progress where valid |
| Expired/revoked | Explain what expired and offer fresh play; no silent answer refresh |
| Image failure | Intentional original title-card fallback with full identity |
| Fixture/deterministic mode | Visible honest mode, no claim of live agent execution |

Use a discriminated state machine. Lost creation response keeps the same idempotency key. Lost answer/Next responses cannot duplicate animations or points. Refresh restores the accepted reveal via an authorized reveal DTO; pre-answer DTO never contains hidden answers. Winner-independent choice ordering and opaque IDs are backend requirements, not something visual randomness alone proves.

## 5. Motion, sound and accessibility

Selection: 120–180ms; reveal ≤450ms; short route fade roughly 150–220ms. Prefer opacity/transform and measure frame stability. Motion cannot delay acceptance or make the result understandable only while watching.

Reduced motion removes flips, parallax, confetti and count-up dependency while preserving all meaning. Sound is optional, off by default, deliberate to enable and controllable through a named persistent mute button. Omit it if unnecessary; audio never gates play.

Use React Aria or suitable native semantics, real buttons and labelled fields. Dialogs manage/restore focus. Artwork alternative text adds information; use empty alt when the adjacent full title makes it redundant. Live announcements report an outcome once, not every score tick. Verify forced colours, keyboard-only flow, touch, zoom, browser Back and manual screen-reader behavior separately from axe.

## 6. Frontend and performance boundaries

Next.js App Router/strict TypeScript, Tailwind tokens, accessible React Aria and restrained Motion. Primitives: Button, IconButton, Combobox, Dialog, Alert, Skeleton, StatusAnnouncement. Domain folders: seed, duel, reveal, results, challenges, discoveries. JSX does not decide winners or eligibility.

Lazy-load optional animation; do not ship old maps, graphs or model/planner assets. A score out of five needs no chart library. Answer/Next access persisted state without Qloo/LLM calls. Bound/allowlist any server-side image fetching; no unrestricted proxy or asset URL carrying answer semantics.

Targets until measured: initial-route JS about ≤180KB gzip, gameplay addition ≤100KB, pressed state <100ms, lab LCP ≤2.5s/CLS ≤0.1. Backend warm answer p95 ≤500ms is separate from network/cold start. Report actual sizes/sample conditions; Lighthouse does not establish field INP or enjoyment.

## 7. Infrastructure-facing UI

Browser uses canonical same-origin `/api/v1` forwarding to private API. No Qloo/database/Vertex credentials reach client code. Terraform, MCP commands, service-account details and stack traces belong in protected operations records, not gameplay.

Differentiate genuine agent-curated Qloo, deterministic Qloo curator and fixture mode. Show concise redacted action summaries only when useful, not private chain-of-thought. An expired cookie cannot resume another guest's state. Candidate origins/old AccessLife URLs must disappear from canonical metadata/share links at cutover.

## 8. Design delivery and acceptance

Prompt 3 creates runnable landing/unanswered/reveal/result/invitation prototypes using owned labelled synthetic content. Prompt 4 extracts primitives and completes five fixture rounds with keyboard/reduced-motion/error states. Prompts 10–12 integrate genuine gameplay/sharing without losing the composition. Prompt 13 audits the complete product; Prompts 18–19 repeat relevant external checks.

Capture and inspect 390×844, 1440×1000 and 320px renders including long names, failed/slow images, empty/error, expiry, reveal and result. Inspect loaded fonts and actual contrast; refine composition rather than declaring “premium” from build success. Private screenshots stay ignored; CI artifact paths must be writable on Linux.

Run full axe without weakened coverage, complete keyboard journey, 200% zoom/reflow, reduced motion and computed contrast checks. Report actual screen-reader checks independently; automation is not user testing. Serious/critical accessibility defects block release. Attractive fixtures do not prove live Qloo, and a polished API does not prove a usable UI.

References to recheck during implementation: [Next.js Server/Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components), [React Aria](https://react-spectrum.adobe.com/react-aria/components.html), [Motion accessibility](https://motion.dev/docs/react-accessibility), [Playwright accessibility](https://playwright.dev/docs/accessibility-testing), [WCAG 2.2](https://www.w3.org/TR/WCAG22/) and the dated [Qloo/source capability matrix](qloo-capability-matrix.md). Original title-card artwork is the complete baseline while external-image rights remain unestablished; image-field presence is not licence evidence. Links and source checks do not establish a passed UI/rendered-design gate.

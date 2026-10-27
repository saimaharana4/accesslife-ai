# Taste Duel willing-user validation

Prepared 27 October 2026. Status: **protocol ready; human evidence pending**.
No real participants were recruited or observed during this implementation.
Codex reviews, browser automation, fixtures and successful provider calls are
technical evidence only. They do not establish enjoyment, surprise or impact.

## Consent and collection

Use willing adults for a short, optional session. Read: “We are testing a cultural
prediction game, not you. May we record anonymous task outcomes and short comments
to improve it? You may skip any question or stop. No name, email, recording or
personal profile is needed. Do not disclose sensitive information.” Record yes/no
consent before observing. Declining has no consequence; do not collect their play.
Do not automatically contact participants or publish quotes.

Assign a study-local code such as P01; do not join it to cookies, IP addresses,
analytics identifiers or accounts. Record date, build/policy version, genuine Qloo
versus fixture mode, device class and relevant assistance. Use genuine Qloo play
for cultural-grounding outcomes; fixture usability observations must be separate.
Do not save raw search text, contestant lists, rankings, scores, answers, provider
payloads or screenshots in public notes. A facilitator may note a reveal's local
round number without reproducing proprietary response content. If the participant
names a cultural item in a quote, keep it private/redact it from published notes.

Anonymous study notes have a maximum 30-day operational retention, separate from
24-hour game/evidence expiry; delete earlier on request using the study code.
Keep notes access-limited outside Git. These are product defaults, not additional
Qloo licence permissions. No screen/audio recording is required. Backups follow
their documented retention; do not promise immediate erasure of every backup.

## Facilitator script

1. Show the opening screen without explaining the answer. Ask: “In your own
   words, what do you think you are being asked to predict?” Record verbatim
   interpretation privately, then code clarity before giving help.
2. Ask them to choose a familiar artist or film and confirm the exact entity.
   Record whether selection needs help, without recording their search text.
3. Invite five predictions at their own pace. Do not suggest winners, explain
   away confusion, or call an unexpected mismatch “good surprise.” Observe
   question clarity, explicit Next, reveal comprehension, interruption/recovery
   and use of Why this duel. Record assistance and blockers.
4. After a reveal, ask neutrally: “Was that connection interesting, unexpected,
   arbitrary, familiar, or something else? What made you say that?” Do not infer
   human surprise from an affinity gap or from an incorrect prediction.
5. At results ask: “Is there anything here you would consider exploring?” Then
   allow Save Discovery without requiring a save. Separate expressed curiosity
   from an actual explicit saved discovery.
6. Ask: “What does your score tell you? Does a different prediction mean you
   personally dislike either choice?” Code understanding before clarification.
7. Show the challenge action. Ask whether they would want a friend to try the
   same five. Creating a link is optional. Where a second consenting participant
   is available, open that actual link in an isolated guest session and invite
   them to finish. Verify identical delivered comparison identifiers, sides,
   context and rules privately without publishing the answer key. Do not use
   an independently generated solo game as the friend test.
8. Ask directly: **“Did Taste Duel surface at least one cultural connection you
   would not have expected on your own? If yes, which moment and why?”** Allow
   “no,” “not sure” and skipped responses without pressure.

If a provider or expired link prevents a task, record that blocker and the
affected denominator. Offer a fresh solo game explicitly; never relabel it as the
expired challenge. A facilitator repair makes that task assisted, not unassisted.

## Outcome definitions and denominators

For each row report numerator / eligible denominator plus skipped, blocked and
assisted counts. Do not silently remove failures or report 0/0 as 0%.

| Outcome | Numerator | Eligible denominator |
|---|---|---|
| Opening clarity | Correctly describes predicting Qloo's request-specific relative ranking before help | Consenting participants shown the opening and asked the question |
| Interesting connection | Reports at least one real Qloo reveal as interesting/unexpected rather than merely arbitrary, with a reason | Participants who saw at least one accepted genuine Qloo reveal and answered this question |
| Exploration interest | Identifies at least one item they would consider exploring | Participants shown results and asked about exploration |
| Explicit discovery save | Personally activates Save Discovery at least once; a correct guess alone never counts | Participants offered a usable save action on at least one accepted reveal/result |
| Five-round completion | Has five accepted predictions and the server result | Consenting participants who started a ready genuine game; separately disclose failure to reach ready |
| Ranking versus taste understanding | Explains score as prediction performance, not personal likes/dislikes, before corrective help | Participants asked the score-understanding question |
| Challenge value | Creates a share link or explicitly expresses interest in a friend challenge; report these two subcounts separately | Participants shown the usable challenge action and asked about it |
| Friend completion | Second consenting participant completes the identical stored challenge | Distinct eligible friend attempts opened by a second consenting participant; report invitation-only and start counts separately |

Also report recruited, consented, opening-exposed, ready-game-started,
result-reached and opted-out totals so funnel failures are visible. One participant
counts once per outcome, even after retries. Technical test accounts/bots and
staff rehearsals are excluded from human findings and reported separately.
If someone withdraws consent, remove their notes and exclude them transparently.
Qualitative answers may be mixed or negative; preserve their meaning. Do not
publish testimonials without separate permission.

Current evidence: **0 recruited; 0 consented; all eight outcomes unmeasured**.
There is no human denominator, completion rate or statistical impact claim.
No participant quotes or observations are available. The human gate remains
pending; independently verified technical checks may continue.

## Product decisions after observation

Log each observed defect, evidence, severity, fix and recheck. Prioritize an
unclear question, arbitrary-feeling explanation, inaccessible interaction or
recovery problem over decorative effects/new features. Do not automatically tune
all misses into easier pairs: question comprehension and genuine discovery value
require separate observations. Difficulty bands remain versioned engineering
heuristics until supported by human evidence. Policy changes apply to new games;
existing games/challenges preserve frozen comparisons and rules.

Use descriptive small-sample counts and actual quotes only where permitted.
State sample size, recruitment bias, familiarity, assistance, device and any
provider failure. Do not claim statistical significance, population preference,
retention, a win-rate benchmark or universal cultural surprise from this study.

## Generic LLM-only comparison

This is a conceptual capability comparison, not a measured performance contest.
No baseline experiment, participant preference percentage or superiority metric
has been collected.

| Capability | Generic LLM from its own knowledge | Taste Duel with genuine Qloo evidence |
|---|---|---|
| Suggestions and playful pairings | Can generate plausible cultural suggestions and prose, subject to hallucination and knowledge limits | Curator may choose a strategy; candidates and answers must come from validated provider evidence |
| Relative preference claim | Can guess an association; fluent prose does not verify a Qloo result | Server checks ordering within the specific frozen Qloo query; not universal truth or personal enjoyment probability |
| Explanation | Can invent a convincing cultural story without supporting facts | Factual higher-ranked-in-this-query template; richer statements only where supported and permitted |
| Adaptive journey | Can propose varied rounds | Deterministic eligibility/no-repeat/continuation checks constrain bounded curation and adaptive selection |
| Fixed replay | Could implement storage too; replay is not unique to Qloo | Stores the actual delivered five with sides/context/versions, independent score and no reranking |
| Discovery value | May suggest interesting items, but usefulness requires real users | Request-specific grounding is inspectable; whether it is useful or surprising still requires real users |

Removing Qloo removes the production game's request-specific cultural ranking
evidence, although a generic LLM can still produce suggestions. Removing the
curator leaves a possible deterministic Qloo game but removes its adaptive
candidate-strategy decisions. Neither fact alone proves a better human
experience. The study above tests clarity, grounding, discovery and challenge
value rather than asking only whether users liked the styling.

Reference policies: [product contract](prd.md), [source/capability/rights record](qloo-capability-matrix.md),
[architecture](Architecture.md), [execution plan](prompts.md).

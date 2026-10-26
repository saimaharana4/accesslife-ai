# Adaptive solo and explicit discoveries — Prompt 11

New solo games use `solo-performance-v1`; old games retain `fixed-path-v1`.
Additive `td0007` freezes the private 256-bit selection seed, policy and delivered
orientation. Original snapshots, scores, pair winners and earlier migrations stay
unchanged. No selection seed/context is projected into browser contracts.

## Selection policy

Request medium first. Two consecutive matching predictions raise the requested
band; a miss eases it. These are within-snapshot engineering heuristics, **not
human-calibrated difficulty**, confidence or enjoyment probabilities. Select only
a persisted unused pair that preserves a complete five-round path without repeated
contestants and meets the original category/band requirements. If the requested
band has no feasible pair, choose the nearest feasible band, easier first on ties,
and record requested/actual band and fallback reason privately. Never relax score,
tie or identity validity to manufacture a round.

Private HMAC draws make decisions reproducible. Side patterns with 2/3 splits
have weight four; every other pattern has weight one. All 32 patterns remain
possible: a hard 3/2 quota would reveal the last winner after some prefixes.
Balance is an objective, not a per-game guarantee. Public IDs cannot reproduce
the private draw. Every delivered orientation/choice ID is frozen transactionally.

Correctness affects challenge and score only. It never creates likes/dislikes or
discoveries. The chosen favourite and explicit Save Discovery are separate user
signals. Answer, Next, save, unsave and recovery use stored state without provider IO.

## Saves, expiry and clearing

POST discoveries requires an owned entity from an accepted round and an idempotency
key. Either contestant is eligible, regardless of winner or prediction. Seed-only,
future, unanswered and foreign IDs do not grant eligibility. Identical retries
return the saved record; changed input conflicts. An old save key after unsave
returns `DISCOVERY_REMOVED`, rather than resurrecting a removed preference. A new
explicit save can use a fresh key. DELETE is idempotent desired-state removal.

GET returns at most 100 live owned discoveries, a bounded expired count without
expired identities, and session expiry. Effective expiry is the earliest session,
entity and accepted game/snapshot expiry. No silent re-query extends evidence.
The 100-retained-row limit includes expired saves. Logical access expiry is
verified; physical purge/backup retention remains an operational release obligation.

Clearing serializes against mutations, revokes private access and dependent owned
challenge definitions, and cancels generation. Runtime RLS hides revoked state.
Historical correctness remains stored; clearing does not rewrite backups.
Challenge endpoints remain 501. **Before Prompt 12 enables sharing, migrate
challenge freezing/validation to use DeliveredRound orientation with legacy pair
fallback. Existing challenge triggers alone cannot freeze adaptive sides correctly.**

## Browser behavior

Owned reads restore accepted reveals and settle uncertain mutations; keys/bodies
remain stable through explicit retries. Cross-tab hints contain only an event
kind and ephemeral sender token, never entities, answers, credentials or preference
payloads. Receivers refetch authoritative state. Focus/visibility/reconnect provide
fallback refresh when BroadcastChannel is unavailable.

Clearing aborts game/search/creation work and ignores late responses; result views
use a revocation epoch. Save stays inside a closed optional native disclosure so
Next is primary. The result shows explicit saves compactly; other answered choices
are collapsed. Missing/expired saves and failed operations have useful notices.
Prediction correctness never becomes an implicit personal preference.

## Commands and actual evidence

```powershell
uv run --no-sync python scripts/tasteduel_local.py migrate
uv run --no-sync python scripts/tasteduel_local.py test -q
corepack pnpm contracts
corepack pnpm test:web-contracts
corepack pnpm test:solo
uv run --no-sync python scripts/tasteduel_prompt11_recovery_check.py
# With the nonfixture web running on 3003; this check owns local API8004:
uv run --no-sync python scripts/tasteduel_prompt11_browser_check.py
corepack pnpm build
corepack pnpm check:fixture-production
```

The checks create only new synthetic guests/games in the recognized local DB;
they never reset data or adopt existing listeners. Cookies use stdin/in-memory
handoff, never storageState files or command arguments. No provider/Secret Manager
access is needed for tests. Ctrl+C stops previews; the dedicated database stop
retains its data: `uv run --no-sync python scripts/tasteduel_local.py stop`.

Passed: **638 backend tests, 53 Node checks, 18 distinct intercepted browser cases**
plus six affected reruns, and 21 full axe/screenshot executions without exclusions.
Five actual API restarts preserved answers/Next/saves. Three separate Chromium
processes through real same-origin forwarding restored accepted reveal, explicit
save, Next and score with exactly one answer/Next/save. Actual desktop/390/320
renders were reviewed, including a compact-reveal refinement. Evidence is ignored
under `.data/tasteduel-prompt11/` and `test-results/tasteduel-prompt11/`.

Manual assistive-technology/zoom testing, human band calibration, broader live
coverage, live corrective-agent value and cloud release remain unverified. The
prior metered provider preview retains its existing ledger/Secret Manager/ADC
configuration; never renew the Prompt 10 eight-Qloo/six-Vertex ceiling. At final
audit it records eight Qloo and two Vertex dispatches: the earlier two/two journey
plus six preview searches whose origin cannot be established from redacted logs.
The Qloo allowance is exhausted; fresh uncached search/generation is unavailable.
Existing stored-game answer/Next/save/recovery remains usable without provider IO.
These preview requests are separate from this phase's zero provider test calls.

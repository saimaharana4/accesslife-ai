# Authoritative gameplay — Prompt 9

Implemented locally on 26 October 2026. Browser integration remains Prompt 10.
The verification below uses explicitly synthetic provider/model contracts, not
new live Qloo/Vertex evidence. Prompt 8's stronger live adaptive-value gate stays
open. No cloud resource, deployed database or release workflow changed.

## Run

```powershell
uv run --no-sync python scripts/tasteduel_local.py migrate
uv run --no-sync python scripts/tasteduel_local.py test tests/tasteduel -q
corepack pnpm contracts
uv run --no-sync python scripts/export_contracts.py --check
corepack pnpm typecheck
uv run --no-sync python scripts/tasteduel_local.py api
# http://127.0.0.1:8002/docs ; Ctrl+C stops the API.
uv run --no-sync python scripts/tasteduel_local.py stop
```

The existing local fixture web preview is separate at port 3001. Its forwarding
route remains disabled. Default API startup neither loads credentials nor creates
a model: `TASTEDUEL_QLOO_ENABLED=false`, `TASTEDUEL_GENERATION_ENABLED=false`.
Typed search needs explicit provider configuration. Curator composition additionally
requires generation enabled; IAM/ADC and the existing Secret Manager reference
are server-only. The explicit HTTP transport/typed-search settings from Prompt 8
remain necessary for its verified path. Do not treat enabling settings as passing
live integration, rights, quota or deployment gates.

Tests inject a private Python generator through `create_app(generator=...)`.
There is no HTTP fixture switch. A default runtime rejects fixture-mode generation;
tests can persist and play unmistakably fixture-labelled games. Synthetic bridge
tests exercise the actual curator code with invented typed provider/model responses.

## Request and transaction boundaries

`POST /v1/games` requires an active guest, owned typed seed and an
`Idempotency-Key` of 16–128 permitted characters. Canonical typed inputs bind the
key within the session and operation; omitted default mode and explicit `solo`
are equivalent. Reusing a key with changed input gives `409 IDEMPOTENCY_CONFLICT`.

The short reservation transaction locks **session → reservation/game**. It creates
a transient `preparing` game and a generation reservation, never a playable DTO.
A claim has a random execution owner, incrementing fence, 30-second lease and
20-second generation/publication deadline. Generation is awaited outside database
transactions. Each attempt retains the curator's six-Qloo/four-Vertex/tool/token
bounds. A reservation permits at most three attempts; this is not a six-request
lifetime quota across all retries. Participating instances still share key-wide
SQL admission. Overlapping legacy readers must be coordinated before rollout.

Publication locks the session and claim again, checking active ownership, exact
execution owner/fence, lease, deadline, seed, normalized snapshot and policy.
One transaction inserts minimal entities, a ranking snapshot/candidates, private
pairs, the frozen feasible path, the full receipt (including versioned policy configuration) and the **first** delivered round,
then marks generation succeeded. Fresh internal entity IDs isolate guests;
`provider_entity_id` retains the real external identity. Receipt JSON preserves
that external seed execution fact while its SQL seed column is an owned foreign key.
The game expires at the earliest relevant session/metadata/evidence lifetime.

Ready is returned only after commit. Lost-response create retries return the same
game without a second pool or receipt. A live competing request observes `202`
with lease time and `Retry-After`. This describes the already-running request;
there is no queue or promise that work continues after a response.

`GET /v1/games/{game_id}/generation` exposes only game ID, coarse status, lease
time, retry delay and recovery action. After a lease expires, resend the same
create input/key. A reclaimed fence prevents the old attempt from publishing.
Failed attempts may be retried within the limit; exhausted status directs a new
game. Session clearing takes the same session-first lock, cancels reservations
and revokes access. A race either publishes before revocation or cannot publish
after it. No response exposes a cleared session's private state.

No FastAPI background task, in-memory promise registry or worker is involved.
Cancellation propagates through awaited generation; a lost request can leave a
lease to expire. Cancellation cannot instantly preempt an already-running short
SQL transaction in a thread. Atomic commit, deadline checks and fencing determine
the authoritative outcome, which a permitted retry reads from PostgreSQL.

## Answers, explicit Next and recovery

`POST /v1/games/{id}/answer` accepts current delivered round/choice IDs plus
`expected_revision`. Session/game/round ownership and expiry are checked under
transactional locks. Database constraints accept one answer; the stored comparison
determines correctness. Identical accepted guesses recover the saved reveal;
different guesses conflict. Reusing an idempotency key with changed body conflicts,
including across different games. New-key aliases bind their own immutable input
signature to the original outcome revision.

An answer returns only that accepted reveal. `POST /advance` requires that answer
and revision, delivers the next stored path pair once, and returns an unanswered
DTO. No automatic advance occurs. Duplicate Next recovers the saved outcome,
including after later answers or API restart. Historical retry projections restore
the saved revision, ordinal, answer state and prefix score, rather than serializing
today's later navigation state. Final explicit Next returns the completed game.

Score is recomputed from accepted database answers, never client totals. Final
results contain exactly five accepted rounds. Answer, Next and results make zero
Qloo/model calls. Selection currently follows the proven stored witness path;
performance-based difficulty adaptation is Prompt 11, fixed friend replay Prompt 12.

## Private curation evidence

Additive `td0006` stores validated, bounded full receipt JSON beside immutable
receipt columns, removes the obsolete rule that deterministic fallback must have
zero attempted model calls, and adds publication/fence/alias constraints. Previous
migrations remain byte-for-byte unchanged. One unique receipt belongs to each
published game; failed/reclaimed attempts cannot overwrite it. Completed receipt
facts are not a claim to retain raw provider responses or hidden model reasoning.

The receipt has no public route or OpenAPI schema. During an unfinished game,
even an accepted earlier reveal has **no curation summary**. Global counts,
rejection reasons and strategy diagnostics could disclose information about
unplayed comparisons. Only after all five answers does the explicit summary
allowlist expose source/mode, target domains, aggregate candidate/primary rejection
counts, correction count and verified path. Full traces, score values, context
hashes, unused pool/order, future contestants and private execution data stay private.
Only the accepted round can reveal its winner; no generic ORM/receipt serialization.

## Verification and limits

`scripts/tasteduel_gameplay_check.py --clean` refuses an existing check container,
temporarily pauses the verified original local container, creates a separate
labelled PostgreSQL 16 container at the guarded loopback endpoint, applies all
migrations and runs the suite. It then restarts a real Uvicorn process midway
through a fixture game, completes five rounds, verifies receipt equality and
rejects another guest. Finally it stops the check container and restores the
original. Both datasets remain available; there is no deletion/reset command.
Inspect port 8003 availability before using this check. A repeat invocation refuses
to call retained data “clean”; it does not discard the previous evidence.

On this delivery: 587 tests passed against the empty database migrated through
`td0006`; two additional actual-curator/SQL bridge tests passed on the retained
local database. The final full backend suite passed all 589 tests. TypeScript, generated contracts and Ruff passed. Artifacts live
in ignored `.data/tasteduel-prompt9/`, including `clean-tests.xml`,
`curator-bridge-tests.xml`, `clean-runtime.json` and `verification.json`.

The tests cover concurrent create/answer/Next, exact retries/restart, failed
publication, stale claims, session clear, changed keys/bodies, future/malicious
IDs, expiry, owner isolation and receipt secrecy. They prove local authority and
durability, not live discovery quality, browser accessibility, remote CI or GCP
connectivity. Expired immutable entity metadata fails closed; refreshing it within
the same session needs a later explicit version policy. Discovery mutations and
challenge endpoints remain unimplemented. Next: **Prompt 10**, carrying the open
live-agent/coverage gates into dependent integration.

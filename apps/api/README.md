# Taste Duel local API foundation

Prompt 5 adds a separate application under `src/tasteduel`. The old `accesslife`
entry point, migration lineage, deployed database and containers are unchanged.
The browser fixture game is not connected to this API yet.

Prompt 7 adds the private [deterministic pool engine](DUEL_POOL.md), typed
evidence bridge and safe aggregate curator feedback. Existing public routes and
OpenAPI remain unchanged. No schema/DB changes, authoritative gameplay, model or
cloud work occurred; live normalized-sample acceptance is explicitly blocked.

Prompt 6 adds the typed private [Qloo runtime](../../runtime/qloo/README.md),
bounded stdio lifecycle and shared key-wide SQL admission through `td0005`.
The new isolated container is separate from legacy Compose/CI. Provider mode is
disabled by default; explicitly enabled startup may access the existing Secret
Manager reference through server ADC. No credential lookup or live Qloo call was
exercised in this delivery. Public handlers below remain as listed; adding the
private port does not connect search or gameplay to the browser.

From the repository root, with Python 3.12, uv and Docker Desktop running:

```powershell
uv sync --locked
uv run --no-sync python scripts/tasteduel_local.py start
uv run --no-sync python scripts/tasteduel_local.py migrate
uv run --no-sync python scripts/tasteduel_local.py test -q
corepack pnpm contracts
uv run --no-sync python scripts/export_contracts.py --check
uv run --no-sync python scripts/tasteduel_local.py api
# http://127.0.0.1:8002/docs ; Ctrl+C stops the API.
uv run --no-sync python scripts/tasteduel_local.py stop
```

The dedicated container binds only `127.0.0.1:55435`. Runtime and migration URLs
must name `tasteduel_prompt5` and their distinct roles; there is no fallback to
`DATABASE_URL`, `.env`, Cloud SQL, Secret Manager or ADC. Generated local-only
passwords are supplied through child-process environment and dedicated Docker
configuration, never repository files or command arguments. Docker retains its
own metadata locally. Stop preserves this synthetic local database.

## Contracts and actual handlers

Python/Pydantic owns the wire schema. `scripts/export_contracts.py` exports this
application's real OpenAPI paths, then `corepack pnpm contracts` generates the
frontend declarations. Public schemas forbid extra fields. No upstream Qloo
specification is used for generation. `ChoicePublic.id` is the opaque delivered
contestant identifier accepted by `AnswerRequest`; `ChoicePublic.entity.id` is
the metadata identity used by discovery requests. They are different identities.

Private routes below use `/v1`. The declared browser base `/api` produces
`/api/v1` after the later same-origin integration. The current web proxy remains
disabled; no browser fixture request reaches this backend.

| Operation | Current foundation behavior | Intended later success |
|---|---|---|
| POST `/sessions` | Create/reuse guest; 201/200, HttpOnly host cookie | Same |
| GET/DELETE `/sessions/current` | Safe active/expiry references; clear/revoke with 204 | Same; full in-flight publication coordination later |
| GET `/entities/search` | 501, typed q/type/limit contract | Real typed resolution/ambiguity |
| POST `/games` | 501, confirmed seed + idempotency contract | 201/200 ready result, bounded 202 existing lease |
| GET `/games/{id}` | Owned safe state; current playable or accepted reveal | Same with live generated games |
| GET `/games/{id}/round` | Owned current playable only; answered current returns 409 | Same |
| POST `/games/{id}/answer` | 501, choice/round/revision contract | Saved accepted reveal, idempotent retries |
| POST `/games/{id}/advance` | 501, answered-round/revision contract | Explicit sequential next/completion |
| GET `/games/{id}/results` | Owned completed five answers only; incomplete 409 | Same |
| GET `/discoveries` | Owned permitted unexpired records | Same |
| POST `/discoveries`; DELETE `/discoveries/{entity_id}` | 501, save/delete contracts | Owned idempotent save/unsave |
| POST `/challenges` | 501, completed game contract | Frozen five-round definition and share path |
| GET `/challenges/{slug}` | 501, safe invitation DTO | Public seed/score/expiry only |
| POST `/challenges/{slug}/plays` | 501, guest/idempotency contract | Owned exact fixed replay |
| GET `/health/live` | Process liveness, generation unavailable | Later generation capability reported truthfully |
| GET `/health/ready` | Exact local schema revision `td0005`, generation unavailable | Later dependency checks |

Database tests insert clearly synthetic private graphs through trusted fixtures.
Reading those graphs is not evidence that public game creation, acceptance,
replay, adaptation or provider integration has been implemented.

## Identity, errors and retries

The random session cookie is hashed in storage; neither the token nor hash is
returned as JSON. Production-default cookies are Secure, HttpOnly, SameSite=Lax,
host-only, Path=/; the local HTTP launcher explicitly disables Secure for local
use only. Mutation origins are exact allowlists. Untrusted session/forwarding
headers cannot select an owner. A cookie UUID only selects a possible session
row; its complete random-token hash, expiry and revocation are verified before
any private game query. Session clear irreversibly revokes access and owned live
challenges; provider/backups/retention cleanup remain separate later work.

Errors use `error.code`, safe `message`, `retryable`, UUID `request_id`, bounded
field location/type and optional retry guidance. Responses are `no-store`.
Validation errors omit submitted values, arbitrary field names and Pydantic
input/context. Actual received mutation bodies are bounded to 16 KiB, including
missing/forged Content-Length. SQL parameters and raw exceptions are not public.

| Status | Meaning |
|---|---|
| 401 | Missing/invalid/expired/revoked session |
| 403 | Mutation origin rejected |
| 404 | Uniform absent or inaccessible private identifier |
| 409 | State conflict, awaiting explicit Next, incomplete result; later signature conflicts |
| 410 | Owned game/evidence expired; later public expired challenges |
| 413/422 | Bounded-body or safe input validation failure |
| 429 | Declared browser admission failure; private Qloo port now has shared admission, browser wiring remains later |
| 501 | Defined operation not connected in this stage; no fixture fallback |
| 503 | Sanitized unavailable configuration/database/stored state |

`Idempotency-Key` is a bounded opaque header. Canonical typed JSON signatures
include session and operation, with sorted object keys and no nonfinite JSON.
Generation reservations store body hash/lease/fence. Mutation receipts uniquely
bind owner/operation/key to a signature and checked typed outcome reference.
Completed answer receipts require a genuine saved answer and authoritative
revision. The database cannot compare an incoming HTTP body by itself: durable
claiming, body-conflict responses and lost-response replay handlers are Prompt 9.

## Private/public boundary and storage

`PlayableRoundPublic` contains only current question/context and two choices.
`RevealedRoundPublic` is built only after owner/state/accepted-answer checks. An
owned game read can restore its current accepted reveal; subsequent unanswered
rounds omit prior reveals. Completed results can include only their five accepted
rounds. No endpoint exposes the unused pool, ranks, affinities or private IDs.

Private `CurationReceipt` records bounded execution counts, modes, domain choices,
versions, timing and status. It has no raw JSON/prompt/chain-of-thought field.
`CurationSummaryPublic` explicitly projects successful safe aggregate facts only.
Optional post-answer evidence includes source, seed/target/timestamp context and
an optional supported explanation; richer text is absent in this foundation.
Neither private receipt is an OpenAPI response model. Raw bounded provider cache
payloads stay private; only synthetic data is stored by these tests.

The [separate migration lineage](tasteduel_migrations/README.md) creates 20 ordinary
PostgreSQL tables without spatial/vector extensions. Composite owner references,
forced RLS, immutable snapshots/answers/results/challenge rounds, sequential
delivery and derived correctness enforce real SQL constraints. Runtime cannot
perform DDL, create temporary objects/roles or become the migration owner.

The session GUC is trusted application context, not a cryptographic database
identity. A holder of the private runtime password can set it; API authentication
and the private database boundary are still essential. Cross-session challenge
copying, generation execution, verified external quota metadata, retention purge and
cloud/CI and full Compose migration are later prompts. Prompt 6 adds an isolated
offline-tested image and engineering admission controls, not verified provider
quota metadata or live game readiness. Run isolated tests with the
provided helper so legacy `tests/conftest.py` is never imported.

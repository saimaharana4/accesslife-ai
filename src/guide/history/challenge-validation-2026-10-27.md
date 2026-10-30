# Exact friend challenges —

> Historical validation record. Statements below describe the dated checkpoint, not current deployment status. See the [current documentation](../README.md).

Implemented locally on 26–27 October 2026. No cloud resources changed or provider
credentials accessed. The tests use clearly labelled synthetic source games.

## Frozen comparison and authority

`ChallengeService` accepts a completed, owned **solo** game. A 32-byte random
capability becomes a 43-character URL-safe slug. Its hash scopes private lookup;
neither a sequential ID nor the creator's session is a public capability.
Session-first transactions and mutation receipts bind idempotency keys to input.
Retries, including different keys for the same completed game, recover its one
challenge rather than minting slugs. Reusing a key with changed input conflicts.

Additive migration `td0008` freezes **DeliveredRound** orientation, with the legacy
pair-side fallback, fixing the Prompt 11 prerequisite. Exactly five delivered
rounds retain order, sides, seed, target/context references, winners and validator/
scoring versions. Earlier migration files stay unchanged.

A replay copies only those five comparisons and their minimal retained evidence
into a new guest-owned, fixed-path game. New opaque entity/choice/round IDs prevent
cross-owner access. It never adapts, generates a new ranking, or invokes Qloo or
Vertex. A collision with different retained entity metadata returns an explicit
conflict instead of changing the frozen presentation. Result DTOs identify fixed
mode; original curation provenance is historical, not a claim of fresh agent work.

Fixed replays cannot create detached child challenges. This prevents resharing
from circumventing the original creator's revocation. Start another solo game
to make an independent challenge. Play retries return the same game for the same
key; a deliberately new attempt can use a new key. This is casual play: prior
knowledge, outside research and repeated attempts exist. There is no leaderboard,
cheat-proof claim or fabricated percentile.

## Public interface, expiry and revocation

- `POST /api/v1/challenges` with `{game_id}` and `Idempotency-Key`: 201 or retry 200.
- `GET /api/v1/challenges/{slug}`: seed, actual creator score, source and expiry;
  never the creator identity/session, choices, unused pool or answer key.
- `POST /api/v1/challenges/{slug}/plays` with `{}` and key: new owned game 201,
  identical retry 200. Only its current playable round is delivered.
- `DELETE /api/v1/challenges/{slug}`: owner-only idempotent revocation, 204.

Private FastAPI uses `/v1`; strict same-origin forwarding owns `/api/v1` and
mutation-origin/cookie protections. Unknown capabilities are 404; known expired
or revoked challenges are 410. Changed-key inputs, incomplete sources, detached
resharing and retained metadata conflicts are explicit 409 responses.

Expiry is the earliest creator session, game, seed, delivered entity and snapshot
expiry. Existing evidence defaults remain at most 24 hours; this is a conservative
operational default, not an invented licence grant. Known earlier permission
termination must also revoke access. There is no reranking or silent replacement.
Creator clearing revokes invitations and already-started replay access. Discoveries
supported only by that replay lose access too; independent accepted context may
still support an explicit save. Guest clearing revokes that guest's private access.
Physical purge and backup retention/restore reconciliation remain release work.
Neither clearing nor revocation rewrites backups or recalls downloaded previews.

## Sharing and social rendering

`TASTEDUEL_CANONICAL_ORIGIN` must equal an allowed web origin. Production requires
HTTPS; loopback HTTP needs the explicit local flag. No purchased domain, Host,
Forwarded or Referer is assumed. Missing canonical configuration disables sharing.

Server-rendered metadata and `/c/{slug}/social` perform anonymous, bounded,
allowlisted no-store invitation reads through the same validator as browser API
forwarding. They carry no visiting cookie. API destinations are configuration,
never slug-derived URLs; redirects, extra/private DTO fields and oversized bodies
fail closed. Private game/results, invitations and social responses are no-store
and use no-referrer. Third-party preview caches cannot be remotely recalled.

The 1200×630 social PNG uses original geometry, local OFL Barlow, the authorized
seed title and actual score. No external artwork is fetched. Unsupported glyphs
use a documented bounded raster fallback; HTML/metadata retain the original name.
No contestant, answer, session token or personal identifier is in the card.
Copy/share has an accessible status and manual selectable-link fallback. Nothing
is sent automatically.

## Run and verify

```powershell
uv run --no-sync python scripts/tasteduel_local.py migrate
# Terminal 1: provider-free stored-game/replay service, dedicated local DB only.
$env:TASTEDUEL_ALLOWED_ORIGINS='["http://127.0.0.1:3003"]'
$env:TASTEDUEL_QLOO_ENABLED='false'
$env:TASTEDUEL_GENERATION_ENABLED='false'
uv run --no-sync python scripts/tasteduel_local.py api --api-port 8005
# Terminal 2:
$env:TASTEDUEL_PREVIEW_PORT='3003'
$env:TASTEDUEL_PREVIEW_API_PORT='8005'
corepack pnpm dev:live
# http://127.0.0.1:3003 ; Ctrl+C stops each server.

corepack pnpm contracts
corepack pnpm test:web-contracts
corepack pnpm test:challenges
uv run --no-sync python scripts/tasteduel_local.py test -q
# Stop terminal 1 first: this proof owns API8005 and preserves the existing DB.
uv run --no-sync python scripts/tasteduel_challenges_browser_check.py
corepack pnpm build
corepack pnpm check:fixture-production
```

Provider-free mode can replay retained games; it cannot create new Qloo solo
games. The earlier live ledger remains exhausted, not reset. This phase does not
claim a fresh genuine-provider generation or production deployment.

Verification: 648 backend tests, 58 Node checks, 15 intercepted browser scenarios
and a real API/database/BFF journey with three isolated browser contexts passed.
Two fixed replays produced independent 3/5 and 2/5 scores from identical sides,
order and winners; refresh restored reveals, and creator clearing blocked both
invitation and completed replay access. All replay calls were provider-free.
Successful browser captures include 23 full axe scans without exclusions (15
intercepted + eight real-boundary), desktop/390/320 layouts and the actual OG PNG.
Typecheck/build/OpenAPI/Ruff and production fixture exclusion are separate checks.
Artifacts are ignored `.data/tasteduel-challenges/` and `test-results/tasteduel-challenges/`.
Manual screen-reader/zoom work, external crawler behavior, physical cleanup and
deployed IAM/cache verification remain open. Next: Prompt 13.

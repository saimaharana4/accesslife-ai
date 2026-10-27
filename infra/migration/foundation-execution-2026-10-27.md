# Verified foundation execution — 27 October 2026

**Foundation gate: PASS.** Taste Duel application services and public traffic are
not deployed. The next release requires reviewed image digests, cloud-ready
application migrations, RLS acceptance and external gameplay checks.

## Cost and saved plan

The user approved **US$90**, keeping the seven-backup policy. The conservative
cumulative forecast is **US$82.84**, with US$7.16 headroom, through 7 November
2026 10:15 IST. It includes all unallocated posted gross usage as an upper bound,
a reporting-lag reserve, tax and currency reserves; future credits are ignored.
Exact unlabelled allocation remains unavailable and is not represented as known.
See [cost approval and release limits](cost-approval-2026-10-27.md).

The independently reviewed full-root saved plan contained **24 creates, seven
updates, 18 state-only forgets, zero deletions and zero replacements**. The old
logical database, user and database-URL secret version were no-op. Existing SQL
changed labels only. The preserved backend/prefix were unchanged.

- Terraform source SHA256: `1863825fafa20f7d99818bb1f71959081a6bdc7874b32c6cd9dcda4ac9405e4a`.
- Saved-plan SHA256: `6d396eb63c934b647d3dad42e2d839ff6cb7c190e0ef10923480008094662e8a`.
- Exact saved plan applied successfully **27 October 23:48:40 IST**.
- Post-apply state serial: **18**. No state bucket/prefix migration occurred.

Private plans, state-derived evidence and execution journals remain ignored.
Never apply the retired historical checkout or blindly repeat an apply after a
partial failure; write-only credential recovery requires deliberate review.

## Repository and keyless authentication

The existing repository was renamed to
[saimaharana4/taste-duel](https://github.com/saimaharana4/taste-duel), preserving
numeric repository ID `1431472864`, owner ID `60200140`, history, main and tags.
Local origin follows the new name. The `foundation-review` environment permits
only main. WIF requires the exact numeric repository/owner, main and that
environment. The deploy identity has scoped registry writes and actAs on the
three new execution identities, without project administration.

[Authentication-only run 40559171936](https://github.com/saimaharana4/taste-duel/actions/runs/40559171936)
passed for SHA `734c64d7f1eef6b5aefc054ed29230fb48179065`. It verified the expected
deploy account, existing registry access and credential cleanup. It deployed
nothing. This is authentication evidence, not an application CI or release result.

## Secrets and cloud metadata

Live metadata checks passed for:

- Runtime URL secret version **1**, readable by the new API identity.
- Migration URL secret version **1**, readable by the migration identity.
- Existing Qloo secret version **1**, with the API reader added and old readers
  retained. Its payload was not copied, printed or rotated.
- No secret access for the new web or deploy identities through the reviewed
  grants; new project-role assignments match the narrow expected sets.
- API Vertex custom role contains only prediction and Service Usage permissions.
- New SQL-user/secret-version state payload fields are empty; no new credential
  payload files were written. Credentials reside in Secret Manager.
- Both logical databases and existing SQL capacity/seven-backup policy remain.
- `tasteduel-web` and `tasteduel-api` remain absent.

Secret policy checks establish reviewed grants, not a blanket claim about every
possible organization-level inherited policy. Vertex IAM is prepared; no model
inference or Qloo ranking was invoked during this foundation operation.

## Database privilege verification

The initial all-in-one bootstrap rolled back when the administrative login could
not create a schema owned by the migrator. The resolved bootstrap used three
explicit stages confined to the new database: restrict new roles and temporarily
grant schema-creation permission; create the schema through the real migration
login; revoke the temporary permission and verify the result. No migration role
was granted to the old administrator, and no old database/user privileges changed.

Independent runtime/migrator logins passed. Both roles have no elevated
memberships, SUPERUSER, CREATEDB, CREATEROLE, replication or RLS-bypass powers.
Runtime has CONNECT and schema USAGE; the migrator owns the `tasteduel` schema.

Five actual runtime probes were denied: CREATE SCHEMA, application CREATE TABLE,
CREATE TEMP TABLE, SET ROLE migrator and SET ROLE legacy owner. A real migration
CREATE TABLE probe succeeded and rolled back. Runtime SELECT against the old
private sessions table failed; catalog-only aggregates found no privileges on
old non-extension application tables or executable application SECURITY DEFINER
functions. No old rows were retrieved. Old PUBLIC
CONNECT was preserved, so this is data denial, not a claim of connection denial.

No application migrations or real application tables were created. The existing
local Alembic guard must be deliberately adapted before release. Application DML,
FORCE RLS and game/session isolation must be tested against that released schema.

## Remaining release boundaries

Publish tested immutable images, enforce the smaller runtime/model envelope,
review a fresh release plan/cost estimate, migrate only Taste Duel, then verify
external genuine gameplay/replay and restore behavior. A late cutover extending
the seven-day rollback window requires repricing. Human impact and manual assistive
technology acceptance remain separate. No public release is authorized merely by
this foundation pass.

## Alert-label correction ? 28 October IST

A separate full-root saved plan contained exactly one update: the new migration
alert display changed from USD80 to USD90. Independent review verified all SQL
users/secret versions no-op. It applied successfully at 00:06:35 IST; the INR6,972
amount was unchanged. A metadata read verified the display/amount, state serial
**19**, and no credential payload read. Current source hash is
`17bc10f86ecfb60b5b59cc5b81597ba54aa0db143a3fde2903e7814c147bc99d`; correction
plan hash is `27a68eb6e5b2561e1096ed66d219c1717bf4f00c81e23b82dabba44fcfec8d04`.
The historical AccessLife alert remains preserved.

Local source checks passed: 73 distinct targeted contracts across the affected
runs, Ruff, six synthetic cost-gate plans, Terraform schema/Compose validation
and staged-source secret scanning. Authentication-only remote success is linked
above; a new full application CI result is separate and must not be inferred.

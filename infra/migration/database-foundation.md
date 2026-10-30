# Empty Taste Duel database privilege preparation

27 October 2026. Source implementation is available in
[`scripts/tasteduel_database_foundation.py`](../../scripts/tasteduel_database_foundation.py).
The staged variant ran successfully against Cloud SQL after approved cost and
saved-plan reviews. Independent runtime/migrator logins and real permission
probes passed; see [verified execution](foundation-execution-2026-10-27.md).
Application migrations and table RLS remain release work.

The administrative caller must pin the existing dedicated instance connection
name from the reviewed resource map and connect to **`tasteduel` only**. The
library accepts existing psycopg connections; it does not fetch credentials,
accept SQL from users, read old rows, write payload files or expose a CLI apply.
Use fresh generated credentials held in memory for the new logins; never recover
credentials from conversation/history or print a DSN/server error. A failed
bootstrap must be reported using its sanitized exception message only.

## Bootstrap boundary

`bootstrap(admin_connection)` checks the actual database, rejects an app principal
as administrator, locks concurrent bootstrap execution and requires exactly the
two already-created principals `tasteduel_runtime` and `tasteduel_migrator`.
The administrative connection must be idle before invocation so success commits
the transaction rather than merely releasing a nested savepoint.
It rejects nonempty databases, unexpected schemas/ownership, unknown role
memberships and privileged superuser/replication/RLS-bypass attributes.

Inside one transaction it removes known `cloudsqlsuperuser` memberships,
disables role/database creation and inheritance, revokes PUBLIC/new-user database
privileges, grants only CONNECT, revokes public-schema privileges, and creates
the dedicated `tasteduel` schema owned by the migration principal. Runtime gets
schema USAGE only. No table privileges, app schemas/migrations, roles, old-user
changes or old-database grants are introduced. Every statement is constant or
uses exact allowlisted identifiers. Unknown state aborts rather than guessing.

Cloud SQL administrators are not true PostgreSQL superusers. The script asserts
superuser/replication/BYPASSRLS are already false and does not attempt to toggle
those special attributes. The supplied administrator still needs legitimate
role-admin/grant authority and authority to create a schema for the migrator.
If Cloud SQL's current administrative role cannot revoke membership, alter the
new roles or assign schema ownership, the transaction rolls back. Record that
precise capability failure; do not grant broader persistent app powers merely
to make preparation succeed.

## Independent-login verification

After commit, open separate real runtime and migrator connections rather than
testing through an administrative `SET ROLE` alone:

- `verify_runtime(connection)` checks the actual user, all elevated role flags,
  absence of memberships, CONNECT/USAGE and denial of database CREATE/TEMP and
  schema CREATE. It performs only catalog reads inside a rolled-back transaction.
- `verify_migrator(connection)` checks the actual user, safe role flags and no
  memberships, then creates a random-named probe table in the owned schema and
  rolls the whole transaction back. No probe table is retained.

These helpers deliberately report application-table RLS and old-database access
as **unverified**. No application tables exist at this foundation stage. Release
verification must exercise synthetic cross-session DML/RLS and immutable-table
permissions after the cloud-ready migration lineage is implemented. Current
Alembic configuration intentionally rejects cloud connections and cannot simply
be run unchanged against the new database.

## Staged owner-login variant

`bootstrap_staged(admin_connection, migrator_connection)` supports the verified
Cloud SQL limitation where the administrator can restrict the new users but
cannot create a schema authorized to a different role. It does not grant the
migrator role to the old administrator or modify any old-database privileges.
Both connections must be idle, and the independent migrator identity is checked
before any administrative write.

The first committed transaction guards the empty new database, restricts both
roles and temporarily grants only database CREATE to the new migrator. The
second transaction runs as that migrator to create its own schema and grant
runtime USAGE. The third removes temporary database CREATE and verifies effective
database/schema privileges plus all role restrictions. It is explicitly **three
committed stages**, not an atomic single transaction.

Failures expose a static stage and two factual status flags:
`preparation_committed` and `temporary_create_cleanup_completed`. After preparation
commits, failure triggers a narrow best-effort CREATE revoke; cleanup is reported
complete only after checking effective denial. A failed cleanup blocks readiness
and requires that exact new-database grant to be reconciled. Retrying permits
only the still-empty schema owned by the expected migrator. No public workloads
may start during this preparation; application migrations remain a later step.

PostgreSQL PUBLIC CONNECT on the old database can remain inherited even when
old table data is inaccessible. Do not claim connection denial. Separately
verify old-data/table/function denial using approved metadata or a known-table
`SELECT ... LIMIT 0` with the runtime login; do not print old rows. Changing old
PUBLIC grants would affect retained recovery readers and needs separate review.

## Verification status

Synthetic tests in `quality/tasteduel/test_database_foundation.py` cover wrong
database/principal rejection before writes, unknown inherited roles, nonempty
database, exact new scope, sanitized rollback on failure and separate-login/
rolled-back probe contracts. They are executor guard tests; the separate live execution record supplies actual
Cloud SQL login/permission evidence. Synthetic tests alone do not prove live isolation.

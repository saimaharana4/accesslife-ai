# Taste Duel foundation module

The reviewed foundation plan was applied on 27 October 2026. See the
[verified execution record](../../../migration/foundation-execution-2026-10-27.md)
for cost approval, saved-plan hashes, keyless authentication, secret grants and
database privilege results. Product services and public traffic are not deployed.
The root default `tasteduel_foundation_enabled=false` is a safety default, not an
instruction to disable already-owned resources; subsequent full-root plans must
preserve the applied foundation and pass the current cost/preservation gates.

The module owns four new identities, one new logical database on the existing
instance, separate built-in SQL users, fresh URL secret containers/write-only
versions, and additive IAM members. It owns no SQL instance, old database/user,
bucket, registry, WIF provider, Cloud Run service/job, image, scheduler or traffic.
Root ownership is `module.tasteduel_foundation[0]`; keep that stable once applied.
The old `google_sql_database.app` and `google_sql_user.app` remain unchanged.

## Credentials and released references

Fresh distinct runtime/migration credentials enter only ephemeral sensitive
inputs, never committed values or local payload files. Passwords and database
URLs use provider write-only fields. Increment `credential_version` only as a
reviewed rotation; changing this revision is not provider-key rotation. Secret
version outputs are references, not payloads. Releases must pin the actual
numeric references returned after authorized creation, never `latest`.

Only API reads the runtime URL and existing Qloo secret. Only migration identity
reads the migration URL. Web/deploy receive no secret access. Existing Qloo
secret/readers remain intact; its release reference is pinned to observed
version 1. Secret Manager IAM is secret-level, not per-version isolation: the
application must request that pinned reference, and future versions require
separate review. No secret payload data source is used. Vertex uses API IAM.

No signing key is added: the current application uses server-persisted opaque
guest sessions rather than a configurable signing-key requirement. Optional
generation providers receive no credentials or IAM.

## IAM and remaining release work

The deploy identity receives writer on the reused registry only, plus actAs on
the three new execution identities. It receives no project-wide administration
or deploy role. WIF binding/trust is coordinated in the existing root owner.
Service/job deployment and web-to-API invocation grants must be added against
real release resources later; the foundation does not grant project-wide Run
administration to anticipate nonexistent resources.

`roles/cloudsql.client` is a predefined project-level connectivity role. Vertex
uses a project custom role containing only `aiplatform.endpoints.predict` and
`serviceusage.services.use`; its live model compatibility remains unverified. SQL IAM permits connection, not table authorization; API
Vertex access is not a model-specific spending cap. Effective inherited IAM,
model budgets and actual database role isolation still require verification.

The execution record verifies the new-database privilege bootstrap, independent
logins, denied elevated/runtime DDL actions and denial of old private application
table access. Application-table DML, FORCE RLS and game/session isolation remain
release checks because application migrations have not run. The migrator
username is `tasteduel_migrator`, matching current application configuration.
User creation alone must never be used as proof of restricted SQL privileges.

## Plan and rollback constraints

Do not use resource targeting, fake images/passwords, a new backend or synthetic
state to create an apply plan. Keep observed legacy image/scheduler inputs in the
full-root plan. New database/users/secret containers have destruction guards;
secret versions abandon rather than delete on ownership removal. These guards
do not establish a restore test or permit automatic retirement. Disablement
after creation would propose deletion and must be rejected/reviewed, not used as
a rollback mechanism. Retain old rollback resources and state ownership.

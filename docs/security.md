# Security, privacy and rights

Production uses Secret Manager references and IAM/ADC. Qloo keys and database URLs never belong in browser settings, examples, source, screenshots or test fixtures. Vertex uses IAM. Released secret references pin numeric versions; keeping a shared secret’s immutable old name is not provider-key rotation.

Web can invoke the private API but receives no database/Qloo secrets. API and migration identities have distinct database principals and secret grants; the migration job receives no Qloo key. Within Taste Duel, only the API identity reads its required runtime references. The API remains IAM-private.

## Guest and answer isolation

The public runtime entry point is the web service, including its allowlisted same-origin API routes. Direct unauthenticated requests to the Cloud Run API service are rejected. Source and Wiki pages are intentionally public for judges; that does not grant backend or Secret Manager access. Authorized operators still use IAM.

The dedicated SQL instance has no authorized IP networks; the app uses authenticated Cloud SQL connectivity. The instance retains a public IPv4 address and is not described as a private-IP-only deployment. Production credentials differ from disposable localhost test values. CI generates and masks fresh database credentials per job and never receives Qloo event keys.

- Secure, HttpOnly, SameSite=Lax cookies are host scoped. Old-origin cookies do not transfer to a new service.
- Mutations validate exact allowed origins; unvalidated forwarded headers do not establish identity.
- Forced PostgreSQL RLS and authenticated transaction ownership isolate guests.
- Playable DTOs omit answers/ranks/affinities; reveals require an accepted owned round.
- Private pools, full receipts, model reasoning, unused pairs and raw provider responses never belong in curation summaries or analytics.
- Invitations expose only permitted seed/score/expiry; social images use original art and approved public fields.

Input schemas, bounded bodies/deadlines, per-session controls and shared per-key database admission limit work. They do not rely on one forwarded-IP throttle that would block all guests behind web. Authentication failures do not silently become another provider. Entity/tool metadata is untrusted input, not permission to alter tools or deterministic rules.

## Evidence, assets and retention

The application uses owned SVG/CSS title cards and locally hosted OFL fonts. An image URL does not grant poster/photo/social reuse rights. [Asset notices](../third_party/README.md).

Qloo evidence stays private and expiry scoped. A challenge cannot outlive its evidence. Access fails closed on expiry; physical cleanup is a reviewed bounded manual operation. Session clear revokes access and owned live shares without claiming immediate backup deletion.

Operational events contain allowlisted numeric facts. Monitoring excludes future Taste Duel HTTP request-URL logs; historical entries age out under their existing policy. First-party activity counters exclude tests by default and do not establish verified humans, personal preferences or popularity.

Credentials, provider captures, state, datasets and browser artifacts are ignored and excluded from container contexts. Synthetic contracts remain tracked because they test these boundaries without event keys. These controls and inspected samples are not a zero-risk guarantee. [Evidence boundaries](verification.md).

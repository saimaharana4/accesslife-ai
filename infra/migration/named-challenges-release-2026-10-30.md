# Taste Duel named challenges: production release

The nickname, friend challenge and shared-verdict release is live at
**https://tasteduel-web-902056825143.asia-south1.run.app**. Use this exact
origin in public links. The alternate Cloud Run service hostname is not in the
API's allowed-origin list and returns `ORIGIN_REJECTED` for session requests.

The public web and private API serve source `e0107488ebdd209b9af4cbb535f07afaf093bed9`
at revisions `tasteduel-web-nfs-e010748` and `tasteduel-api-nfs-e010748`.
Schema `td0014` was migrated before traffic promotion. The feature web
revision has 100% traffic. The final full-root Terraform review found zero
changes across 86 resources. The tested rollback to the bridge revision
preserved an existing nickname session; traffic was then returned to the
feature revision.

The recorded ordinary-public-origin play completed a real Qloo/Vertex
five-round solo game, isolated friend replay of the frozen rounds, shared
verdict, discovery save, session recovery, revocation and privacy checks. The
release record is in the ignored local evidence directory at
`.data/tasteduel-named-duels/production-verification-ledger.json` and its
referenced reports. An earlier expiry check used the same immutable feature
images and schema; expiry was not freshly retested after traffic promotion.

The dedicated `tasteduel-cleanup` scheduler is enabled every ten minutes UTC.
At 2026-10-30 08:20 UTC its natural dispatch completed successfully; its
aggregate cleanup log reported `PASS` and zero expired-budget backlog.
The separate manual cleanup rehearsal physically deleted expired sessions,
challenges, games and dependent rows. Console alert policies exist, but
external notification delivery has not been demonstrated. Backup and export
retention limits are documented in [named-challenges.md](../../docs/named-challenges.md).

The conservative release cost forecast through 2026-11-07 04:45 UTC is
US$95.38 against the approved US$100 ceiling. This is a forecast, not an
invoice. Existing US$90 alerts are early warnings. Do not extend runtime
past that horizon without a fresh cost review. Older AccessLife data,
secrets, IAM, shared SQL and Terraform state remain protected for recovery;
their retirement is a separate gated operation after retention and accepted-run
review. No old product runtime is publicly active.

The source release did not change the API's allowed-origin list. A visitor
using the alternate service hostname may see "A LITTLE HOLD-UP" at nickname
entry. The documented canonical origin returns the expected new-visitor
response and creates a named session successfully. A later change can add a
safe redirect or alternate-origin support after independent release review.

# Full-root foundation plan runner

`tasteduel_foundation_plan.py` is plan-only. It does not apply infrastructure,
rename GitHub, change traffic, bootstrap SQL privileges or claim any live gate
has passed. Do not invoke it while actual cumulative billing is unresolved.

The nonsecret approved cost JSON must contain exactly these fields:

| Field | Required verified input |
| --- | --- |
| `cost_gate_status` | `PASS`, only after actual incurred charges plus remaining forecast fit the explicitly approved US$90 ceiling |
| `billing_reconciled`, `cost_review_passed` | Boolean `true` backed by the completed review |
| `reviewed_total_usd` | Actual cumulative reviewed number, not remaining capacity |
| `reviewed_through_utc` | RFC3339 priced horizon, at least 7 November 2026 04:45 UTC and still future |
| `billing_account` | Actual retained billing-account ID, not credentials |
| `budget_currency` | `INR` matching the reviewed notification configuration |
| `budget_alert_units`, `migration_alert_units` | Reviewed positive integer notification amounts; not spending caps |
| `accrued_cost_evidence` | Reference to the real attributed accrued-charge evidence |
| `approved_at_utc` | Actual review approval time within the previous 24 hours |

No credential fields, pasted values, Terraform variable overrides or arbitrary
project/backend IDs are accepted in that file. This is an operator-reviewed
input, not a mechanism to manufacture a passing cost assessment. The runner
validates the gate shape; the reviewer must verify the evidence and arithmetic.

```powershell
uv run --project runtime/python --frozen python scripts/tasteduel_foundation_plan.py --review .data/tasteduel-cloud-review/approved-cost.json
```

On explicit execution the runner uses ADC, resolves only the existing legacy
database-password version 1 in memory, and generates distinct new ephemeral
credentials. It never reads credential-history wrappers or Qloo payloads. It
passes values through environment variables, never CLI arguments or payload
files. Docker receives a read-only single ADC file mount and only named Terraform
variables. Provider output is captured privately in memory rather than streamed.

The source snapshot contains only root/module Terraform and its lockfile. The
fixed backend remains the existing AccessLife bucket/prefix. No targeting,
empty state, fake image, destroy plan or routine replacement is permitted. The
binary `foundation.tfplan` is saved under an ignored, unique `.data` directory;
it contains sensitive state and must never be committed or published. The
redacted `review.json` contains source/plan hashes, addresses/actions and gate
metadata, never resource attribute values. `REVIEWABLE` requires independent
full-plan review; it is not apply authorization or a verified deployment.

Only exact foundation create addresses, reviewed legacy cost-label updates,
numeric/main/environment-restricted WIF update and explicit forget-only retired
addresses pass the automatic scope filter. Unexpected legacy password/secret
updates, replacements, deletions, runtime recreation, tier/network/backup drift
or unrelated actions block. Resolve real drift in source/state deliberately;
never expand the allowlist merely to make a plan green.

## Saved-plan ephemeral-input handoff

Terraform deliberately does not save ephemeral values. A later separately
reviewed apply process must supply ephemeral variables again. For a pristine
first apply, fresh values can be generated at apply time, provided each SQL user
and its corresponding URL secret receive the identical value in that same
execution. Plan-time values alone are not a recovery store.

After a partial apply or a prior successful creation, **do not blindly regenerate
credentials while keeping revision 1**. Write-only version counters can leave an
existing SQL password unchanged while a missing URL secret receives a different
value. Stop and review actual resource/version state; recover the established
credential privately where available, or deliberately rotate both SQL password
and matching secret with a new reviewed credential revision. Verify privilege
bootstrap and credential connectivity before any workload is deployed.

The current runner has no apply command precisely so that this handoff,
independent plan review, preserved rollback state and SQL privilege bootstrap
cannot be skipped accidentally.

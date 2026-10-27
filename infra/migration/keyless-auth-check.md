# Verified keyless foundation authentication

The existing public repository is [saimaharana4/taste-duel](https://github.com/saimaharana4/taste-duel).
Rename preserved repository ID `1431472864`, owner ID `60200140`, main, history
and tags. Local origin follows the new URL. The GitHub connector was inspected;
rename/environment/dispatch required authenticated REST through the existing
credential helper. No token was printed or written to a payload file.

## Verified access boundary

The existing WIF pool/provider were retained. Trust requires exact numeric
repository and owner, `refs/heads/main`, and environment `foundation-review`.
That environment has a verified main-only branch policy; no required human
reviewer is claimed. The deploy-SA binding uses the numeric repository principal
set. Registry writes and actAs are resource scoped; no project administrator
role or public service was created.

The workflow uses immutable official action revisions, validates explicit
provider/account references and performs authentication plus metadata reading
only. It never deploys, runs Terraform, invokes old jobs, reads secrets or prints
access tokens. Its ephemeral runner credentials are removed by post-job cleanup.

## Actual run

[Run 40559171936](https://github.com/saimaharana4/taste-duel/actions/runs/40559171936)
completed **SUCCESS** for SHA `734c64d7f1eef6b5aefc054ed29230fb48179065`.
OIDC authentication, exact active deploy-account verification, existing Docker
registry metadata access and credential cleanup all passed. Allowlisted log
inspection verified those facts without saving raw logs or credentials.

Repository variables contain only the WIF provider reference, deploy-account
reference and explicit enable flag. They contain no provider/API/database keys.
The user-approved cumulative ceiling is US$90; [cost review](cost-approval-2026-10-27.md)
passed at US$82.84 before foundation application. The workflow enable flag is not
a spending cap or a substitute for that review.

## Limits and recovery

Authentication does not prove application deployment, model inference, database
RLS or external gameplay. Those remain separate release gates. The retired old
repository-name WIF binding is retained as historical ownership, not claimed to
work after rename; rollback uses reviewed administrative recovery and recorded
images/source. No broad owner-wide trust was introduced to keep it working.

The bounded helper is [tasteduel_github_foundation.py](../../scripts/tasteduel_github_foundation.py).
Dispatch requires an expected published main SHA. A skipped authentication job
is never a passed verification. Do not upload generated credential files.

"""Apply one independently reviewed saved foundation plan, with private inputs.

No generic apply, targeting, credential files, provider log dumps or retries.
Partial execution needs deliberate credential recovery before another attempt.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

import tasteduel_foundation_plan as planner


def source_hash(directory):
    digest = hashlib.sha256()
    for path in sorted([*directory.glob('*.tf'), *directory.glob('modules/**/*.tf'), directory / '.terraform.lock.hcl']):
        relative = str(path.relative_to(directory)).replace('\\', '/')
        digest.update(relative.encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def verify(directory, review, approval, cost):
    if review['status'] != 'REVIEWABLE' or approval.get('independent_review') != 'PASS':
        raise planner.PlanBlocked('INDEPENDENT_REVIEW_REQUIRED')
    if approval['source_sha256'] != review['source_sha256'] or approval['plan_sha256'] != review['plan_sha256']:
        raise planner.PlanBlocked('APPROVAL_HASH_MISMATCH')
    if source_hash(directory) != review['source_sha256'] or source_hash(planner.ROOT / 'infra/terraform') != review['source_sha256']:
        raise planner.PlanBlocked('SOURCE_CHANGED_AFTER_REVIEW')
    if hashlib.sha256((directory / 'foundation.tfplan').read_bytes()).hexdigest() != review['plan_sha256']:
        raise planner.PlanBlocked('SAVED_PLAN_CHANGED')
    variables = planner.approved_variables(cost)
    if variables['reviewed_total_usd'] != review['reviewed_total_usd']:
        raise planner.PlanBlocked('COST_CHANGED_AFTER_REVIEW')
    if (directory / 'apply-journal.json').exists():
        raise planner.PlanBlocked('PRIOR_ATTEMPT_REQUIRES_RECOVERY_REVIEW')
    return variables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--cost', required=True, type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    journal = None
    try:
        expected_parent = (planner.ROOT / '.data/tasteduel-cloud-review').resolve()
        if directory.parent != expected_parent:
            raise planner.PlanBlocked('PLAN_DIRECTORY_OUTSIDE_PRIVATE_BOUNDARY')
        review = json.loads((directory / 'review.json').read_text())
        approval = json.loads((directory / 'independent-approval.json').read_text())
        cost = json.loads(args.cost.read_text())
        variables = verify(directory, review, approval, cost)
        adc = planner.adc_path()
        # Full JSON exists only in memory; repeat the scope filter, never dump it.
        audit = planner.audit_plan(json.loads(planner.terraform(directory, adc, {}, 'show', '-json', 'foundation.tfplan')))
        if audit['status'] != 'REVIEWABLE':
            raise planner.PlanBlocked('SAVED_PLAN_SCOPE_FAILED')
        from google.cloud import secretmanager
        secret = secretmanager.SecretManagerServiceClient().access_secret_version(request={'name': planner.LEGACY_PASSWORD})
        environment = planner.ephemeral_environment(variables, secret.payload.data.decode())
        del secret
        journal = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'STARTED',
                   'plan_sha256': review['plan_sha256'], 'source_sha256': review['source_sha256'],
                   'payloads_written_to_files': False, 'public_services_created': False}
        (directory / 'apply-journal.json').write_text(json.dumps(journal, indent=2))
        command = ['docker', 'run', '--rm', '--mount', f'type=bind,source={directory},target=/work',
                   '--mount', f'type=bind,source={adc},target=/adc.json,readonly', '--workdir', '/work',
                   '--env', 'GOOGLE_APPLICATION_CREDENTIALS=/adc.json']
        for key in environment:
            command += ['--env', key]
        command += [planner.IMAGE, 'apply', '-json', '-input=false', '-lock-timeout=60s', 'foundation.tfplan']
        result = subprocess.run(command, env={**os.environ, **environment}, capture_output=True, text=True)
        # Raw output remains memory-only; summaries deliberately omit diagnostics.
        journal['status'] = 'APPLIED' if result.returncode == 0 else 'FAILED_REQUIRES_RECOVERY'
        journal['completed_at'] = datetime.now(timezone.utc).isoformat()
        journal['exit_code'] = result.returncode
        (directory / 'apply-journal.json').write_text(json.dumps(journal, indent=2))
        print(json.dumps(journal))
        return 0 if result.returncode == 0 else 2
    except Exception as exc:
        reason = str(exc) if isinstance(exc, planner.PlanBlocked) else type(exc).__name__
        print(json.dumps({'status': 'BLOCKED', 'reason': reason, 'apply_started': journal is not None}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

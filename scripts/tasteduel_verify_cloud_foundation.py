"""Read exact foundation IAM/version/state metadata, never secret payloads.

Raw state/policies stay in memory. Output contains booleans and pinned references
only; unrelated IAM members and historical sensitive values are never exported.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

import google.auth
from google.auth.transport.requests import AuthorizedSession

PROJECT = 'project-bb13ecd8-9d67-408d-9a7'
ROOT = Path(__file__).resolve().parents[1]


def main():
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    http = AuthorizedSession(credentials)
    result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'secret_payload_reads': 0, 'checks': {}}

    def get(url):
        response = http.get(url, timeout=25)
        if response.status_code != 200:
            raise RuntimeError(f'Metadata HTTP {response.status_code}')
        return response.json()

    def sa(actor):
        return f'serviceAccount:tasteduel-{actor}@{PROJECT}.iam.gserviceaccount.com'

    def readers(policy):
        return {member for binding in policy.get('bindings', [])
                if binding.get('role') == 'roles/secretmanager.secretAccessor'
                for member in binding.get('members', [])}

    try:
        for secret, actor in [('tasteduel-runtime-database-url', 'api'), ('tasteduel-migrate-database-url', 'migrate'), ('accesslife-qloo-api-key', 'api')]:
            base = f'https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets/{secret}'
            policy = get(base + ':getIamPolicy')
            actual = readers(policy)
            expected = sa(actor)
            allowed = expected in actual
            allowed &= all(sa(other) not in actual for other in ('web', 'api', 'migrate', 'deploy') if other != actor)
            allowed &= not ({'allUsers', 'allAuthenticatedUsers'} & actual)
            version = get(base + '/versions/1')
            result['checks'][secret + '_grant_and_pinned_version'] = bool(allowed and version.get('state') == 'ENABLED')
        response = http.post(f'https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT}:getIamPolicy', json={'options': {'requestedPolicyVersion': 3}}, timeout=25)
        if response.status_code != 200:
            raise RuntimeError('Project policy unavailable')
        bindings = response.json().get('bindings', [])
        for actor in ('web', 'api', 'migrate', 'deploy'):
            actual = {b['role'] for b in bindings if sa(actor) in b.get('members', [])}
            expected = {'api': {'roles/cloudsql.client', f'projects/{PROJECT}/roles/tasteduelVertexPredictor'},
                        'migrate': {'roles/cloudsql.client'}, 'web': set(), 'deploy': set()}[actor]
            result['checks'][actor + '_project_roles_exact'] = actual == expected
        role = get(f'https://iam.googleapis.com/v1/projects/{PROJECT}/roles/tasteduelVertexPredictor')
        result['checks']['vertex_permissions_exact'] = set(role.get('includedPermissions', [])) == {'aiplatform.endpoints.predict', 'serviceusage.services.use'}
        sql = get(f'https://sqladmin.googleapis.com/sql/v1beta4/projects/{PROJECT}/instances/accesslife-db')
        settings = sql['settings']
        result['checks']['sql_capacity_and_backups_preserved'] = (
            settings['tier'] == 'db-custom-1-3840' and settings['dataDiskSizeGb'] == '20'
            and settings['storageAutoResizeLimit'] == '40'
            and settings['backupConfiguration']['backupRetentionSettings']['retainedBackups'] == 7)
        for database in ('accesslife', 'tasteduel'):
            item = get(f'https://sqladmin.googleapis.com/sql/v1beta4/projects/{PROJECT}/instances/accesslife-db/databases/{database}')
            result['checks'][database + '_database_present'] = item.get('name') == database
        bucket = 'accesslife-tfstate-' + PROJECT
        state = get(f'https://storage.googleapis.com/storage/v1/b/{bucket}/o/accesslife%2Fstate%2Fdefault.tfstate?alt=media')
        new = [r for r in state.get('resources', []) if r.get('module') == 'module.tasteduel_foundation[0]']
        private = [instance.get('attributes', {}) for r in new if r['type'] in ('google_sql_user', 'google_secret_manager_secret_version') for instance in r.get('instances', [])]
        result['checks']['new_state_payload_fields_absent'] = len(private) == 4 and all(
            not attributes.get(key) for attributes in private for key in ('password', 'password_wo', 'secret_data', 'secret_data_wo'))
        result['state_serial'] = state.get('serial')
        del state, private
        for service in ('tasteduel-web', 'tasteduel-api'):
            response = http.get(f'https://run.googleapis.com/v2/projects/{PROJECT}/locations/asia-south1/services/{service}', timeout=25)
            result['checks'][service + '_not_deployed'] = response.status_code == 404
        result['status'] = 'PASS' if all(result['checks'].values()) else 'BLOCKED'
    except Exception as exc:
        result.update(status='BLOCKED', failure_type=type(exc).__name__)
    (ROOT / '.data/tasteduel-cloud-review/cloud-foundation-verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())

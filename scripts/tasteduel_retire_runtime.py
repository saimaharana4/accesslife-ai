"""Explicitly authorized legacy runtime retirement, never shared asset deletion.

Default is a local allowlist preview. --execute performs only the eight named
retirements, requires preserved metadata and reviewed source removed blocks.
No secret payload reads, state writes, task purges or provider calls.
"""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import time

import google.auth
from google.auth.transport.requests import AuthorizedSession

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / '.data/tasteduel-cloud-review'
PROJECT = 'project-bb13ecd8-9d67-408d-9a7'
PARENT = f'projects/{PROJECT}/locations/asia-south1'
TARGETS = (
    ('run', 'services', 'accesslife-web'),
    ('run', 'services', 'accesslife-api'),
    ('run', 'services', 'accesslife-worker'),
    ('scheduler', 'jobs', 'accesslife-reconcile'),
    ('run', 'jobs', 'accesslife-reconcile'),
    ('run', 'jobs', 'accesslife-ingest'),
    ('run', 'jobs', 'accesslife-migrate'),
    ('tasks', 'queues', 'accesslife-planning'),
)
HOSTS = {'run': 'https://run.googleapis.com/v2', 'scheduler': 'https://cloudscheduler.googleapis.com/v1', 'tasks': 'https://cloudtasks.googleapis.com/v2'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'mode': 'preview-no-cloud-calls', 'targets': TARGETS}))
        return
    inventory = json.loads((ARTIFACTS / 'inventory.json').read_text())
    drain = json.loads((ARTIFACTS / 'retirement-drain-metadata.json').read_text())
    assert not drain['errors'] and all(not j['unfinished_or_running'] and not j['incomplete_listing'] for j in drain['jobs'].values())
    source = (ROOT / 'infra/terraform/accesslife-retirement.tf').read_text()
    assert 'destroy = false' in source and 'google_cloud_run_v2_service' in source
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    http = AuthorizedSession(credentials)
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'scope': 'explicit-user-authorized-runtime-only', 'operations': [], 'shared_resources_mutated': False, 'secret_payload_reads': 0, 'terraform_state_mutated': False}

    def save():
        (ARTIFACTS / 'retirement-execution.json').write_text(json.dumps(report, indent=2))

    def get(url, params=None):
        response = http.get(url, params=params, timeout=25)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RuntimeError(f'metadata GET failed HTTP {response.status_code}')
        return response.json()

    # Fail closed on drift, queued tasks or resumed dispatch before any delete.
    expected = {s['name'].split('/')[-1]: s for s in inventory['services']}
    metadata = {}
    for kind, collection, name in TARGETS:
        url = f'{HOSTS[kind]}/{PARENT}/{collection}/{name}'
        value = get(url)
        metadata[(kind, name)] = value
        if value is None:
            continue
        if collection == 'services':
            assert value['name'] == f'{PARENT}/{collection}/{name}'
            assert value.get('latestReadyRevision') == expected[name].get('latestReadyRevision'), 'Revision drift; review before retirement'
            images = [c.get('image') for c in value.get('template', {}).get('containers', [])]
            assert images == [c['image'] for c in expected[name]['containers']], 'Image drift'
        if kind in ('tasks', 'scheduler'):
            assert value.get('state') == 'PAUSED', 'Dispatch must remain paused'
        if kind == 'tasks':
            tasks = get(url + '/tasks', {'pageSize': 1, 'fields': 'tasks(name),nextPageToken'})
            assert tasks is not None and not tasks.get('tasks') and not tasks.get('nextPageToken'), 'Queue must be empty; never purge'
    save()
    for kind, collection, name in TARGETS:
        url = f'{HOSTS[kind]}/{PARENT}/{collection}/{name}'
        value = metadata[(kind, name)]
        item = {'kind': kind, 'collection': collection, 'name': name}
        if value is None:
            item['status'] = 'already-absent'
        else:
            response = http.delete(url, params={'etag': value['etag']} if kind == 'run' and value.get('etag') else None, timeout=30)
            item['delete_http_status'] = response.status_code
            if response.status_code not in (200, 204, 404):
                report['operations'].append(item)
                save()
                raise RuntimeError(f'{name}: delete failed HTTP {response.status_code}; no body printed')
            if kind == 'run' and response.status_code == 200:
                operation = response.json()
                operation_name = operation.get('name', '')
                assert operation_name.startswith(PARENT + '/operations/'), 'Unexpected operation scope'
                for _ in range(60):
                    status = get(f'{HOSTS[kind]}/{operation_name}')
                    if status and status.get('done'):
                        if status.get('error'):
                            raise RuntimeError(f'{name}: operation error code {status["error"].get("code")}')
                        break
                    time.sleep(2)
                else:
                    raise RuntimeError(f'{name}: operation pending; inspect exact operation before retry')
            if get(url) is not None:
                raise RuntimeError(f'{name}: absence verification failed')
            item['status'] = 'deleted-verified-404'
        item['verified_at'] = datetime.now(timezone.utc).isoformat()
        report['operations'].append(item)
        save()
        print(f'{name}: {item["status"]}', flush=True)
    report['completed_at'] = datetime.now(timezone.utc).isoformat()
    save()


if __name__ == '__main__':
    main()

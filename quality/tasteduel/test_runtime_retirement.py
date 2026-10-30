from pathlib import Path
import importlib.util
import json

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location('retirement', ROOT / 'scripts/tasteduel_retire_runtime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_runtime_allowlist_excludes_preserved_assets():
    module = load()
    assert len(module.TARGETS) == 8
    assert {x[2] for x in module.TARGETS if x[1] == 'services'} == {'accesslife-web', 'accesslife-api', 'accesslife-worker'}
    assert all(x[0] in ('run', 'scheduler', 'tasks') for x in module.TARGETS)


@pytest.mark.parametrize('problem', [None, 'revision', 'tasks', 'resumed'])
def test_deletes_only_allowlist_and_aborts_before_mutation_on_drift(tmp_path, monkeypatch, problem):
    module = load()
    module.ARTIFACTS = tmp_path
    module.ROOT = tmp_path
    source = tmp_path / 'infra/terraform/accesslife-retirement.tf'
    source.parent.mkdir(parents=True)
    source.write_text('removed { from = google_cloud_run_v2_service.web lifecycle { destroy = false } }')
    services = [{'name': f'{module.PARENT}/services/{name}', 'latestReadyRevision': 'fixture-revision', 'containers': [{'image': 'fixture-digest'}]} for name in ('accesslife-web', 'accesslife-api', 'accesslife-worker')]
    (tmp_path / 'inventory.json').write_text(json.dumps({'services': services}))
    (tmp_path / 'retirement-drain-metadata.json').write_text(json.dumps({'errors': [], 'jobs': {'fixture': {'unfinished_or_running': 0, 'incomplete_listing': False}}}))

    class Response:
        def __init__(self, value=None, status=200):
            self.status_code = status
            self.value = value

        def json(self):
            return self.value

    class Http:
        def __init__(self):
            self.deleted = set()

        def get(self, url, **kwargs):
            if url in self.deleted:
                return Response(status=404)
            name = url.split('/')[-1]
            if name == 'tasks':
                return Response({'tasks': [{'name': 'fixture'}]} if problem == 'tasks' else {})
            return Response({'name': '/'.join(url.split('/')[4:]), 'state': 'RUNNING' if problem == 'resumed' else 'PAUSED', 'latestReadyRevision': 'drift' if problem == 'revision' else 'fixture-revision', 'template': {'containers': [{'image': 'fixture-digest'}]}})

        def delete(self, url, **kwargs):
            self.deleted.add(url)
            return Response(status=204)

    http = Http()
    monkeypatch.setattr(module.google.auth, 'default', lambda **_: (None, None))
    monkeypatch.setattr(module, 'AuthorizedSession', lambda _: http)
    monkeypatch.setattr('sys.argv', ['retirement', '--execute'])
    if problem:
        with pytest.raises(AssertionError):
            module.main()
        assert not http.deleted
    else:
        module.main()
        assert http.deleted == {f'{module.HOSTS[k]}/{module.PARENT}/{c}/{n}' for k, c, n in module.TARGETS}
        report = json.loads((tmp_path / 'retirement-execution.json').read_text())
        assert len(report['operations']) == 8
        assert report['shared_resources_mutated'] is False

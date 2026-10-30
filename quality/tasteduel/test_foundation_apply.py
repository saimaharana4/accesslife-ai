import importlib.util
import hashlib
from pathlib import Path

import pytest


def test_saved_plan_gate_rejects_changes_and_prior_attempt(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts'))
    spec = importlib.util.spec_from_file_location('foundation_apply', Path(__file__).resolve().parents[2] / 'scripts/tasteduel_foundation_apply.py')
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    source = tmp_path / 'infra/terraform'
    source.mkdir(parents=True)
    (source / '.terraform.lock.hcl').write_text('synthetic-lock')
    (source / 'main.tf').write_text('synthetic-source')
    (source / 'foundation.tfplan').write_bytes(b'synthetic-saved-plan')
    monkeypatch.setattr(app.planner, 'ROOT', tmp_path)
    monkeypatch.setattr(app.planner, 'approved_variables', lambda _: {'reviewed_total_usd': 82.84})
    review = {'status': 'REVIEWABLE', 'source_sha256': app.source_hash(source), 'plan_sha256': hashlib.sha256(b'synthetic-saved-plan').hexdigest(), 'reviewed_total_usd': 82.84}
    approval = {**review, 'independent_review': 'PASS'}
    assert app.verify(source, review, approval, {})['reviewed_total_usd'] == 82.84
    (source / 'main.tf').write_text('changed-after-review')
    with pytest.raises(app.planner.PlanBlocked, match='SOURCE_CHANGED'):
        app.verify(source, review, approval, {})
    (source / 'main.tf').write_text('synthetic-source')
    (source / 'foundation.tfplan').write_bytes(b'changed-plan')
    with pytest.raises(app.planner.PlanBlocked, match='SAVED_PLAN_CHANGED'):
        app.verify(source, review, approval, {})
    (source / 'foundation.tfplan').write_bytes(b'synthetic-saved-plan')
    (source / 'apply-journal.json').write_text('{}')
    with pytest.raises(app.planner.PlanBlocked, match='PRIOR_ATTEMPT'):
        app.verify(source, review, approval, {})

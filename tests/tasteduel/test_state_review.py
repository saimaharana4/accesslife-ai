"""Synthetic state extraction contracts; no ADC or remote object downloads."""

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
LEGACY_SOURCE_BASELINE = "ef5c27c6b1aff925dd504b371dff99e128a2f77b"


def script(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_state_projection_never_serializes_credentials_or_provider_payloads():
    module = script("tasteduel_state_review")
    forbidden = "SYNTHETIC_PRIVATE_STATE_MUST_NOT_ESCAPE"
    state = {"resources": [{
        "mode": "managed", "type": "google_sql_user", "name": "app",
        "instances": [{"attributes": {"id": "accesslife//accesslife-db", "name": "accesslife", "password": forbidden, "password_wo": forbidden, "secret_data": forbidden}}],
    }, {
        "mode": "managed", "type": "google_cloud_run_v2_service", "name": "backend",
        "instances": [{"index_key": "api", "attributes": {
            "name": "accesslife-api", "id": "owned-service",
            "template": [{"containers": [{"image": "synthetic-index-digest", "env": [{"value": forbidden}]}]}],
        }}],
    }]}
    result = module.ownership(state)
    assert result[1]["address"] == 'google_cloud_run_v2_service.backend["api"]'
    assert result[1]["images"] == ["synthetic-index-digest"]
    assert forbidden not in json.dumps(result)
    assert "password" not in json.dumps(result)


def test_iam_projection_excludes_nonowned_members_and_user_identity():
    module = script("tasteduel_cloud_policy_review")
    owned = f"serviceAccount:accesslife-web@{module.PROJECT}.iam.gserviceaccount.com"
    result = module.selected_policy({"bindings": [{
        "role": "roles/run.invoker", "members": [owned, "allUsers", "user:synthetic-private@example.invalid", "serviceAccount:other-app@other.iam.gserviceaccount.com"],
        "unrestricted_payload": "SYNTHETIC_PRIVATE",
    }]})
    assert result == [{"role": "roles/run.invoker", "members": [owned, "allUsers"]}]


def test_unknown_state_type_cannot_leak_sensitive_id_or_index():
    module = script("tasteduel_state_review")
    marker = "SYNTHETIC_PRIVATE_UNKNOWN_RESOURCE_ID"
    result = module.ownership({"resources": [{
        "mode": "managed", "type": "random_password", "name": "new_login",
        "instances": [{"index_key": marker, "attributes": {"id": marker, "result": marker}}],
    }]})
    assert marker not in json.dumps(result)
    assert result[0]["review_status"] == "unsupported_type_attributes_omitted"


def test_iam_conditions_remain_explicit_without_unrestricted_metadata():
    module = script("tasteduel_cloud_policy_review")
    result = module.selected_policy({"bindings": [{
        "role": "roles/run.invoker", "members": ["allUsers"],
        "condition": {"title": "synthetic time guard", "expression": "request.time < timestamp('2026-11-07T04:45:00Z')", "description": "SYNTHETIC_PRIVATE_NOTE"},
    }]})
    assert result[0]["conditional"] is True
    assert "request.time" in result[0]["condition"]["expression"]
    assert "SYNTHETIC_PRIVATE_NOTE" not in json.dumps(result)


def test_current_source_preserves_shared_addresses_and_explicit_runtime_retirement():
    # Exact authorized runtime scope, not permission for arbitrary source removal.
    retired = {
        "main.tf": {
            ("google_cloud_run_v2_service", "backend"),
            ("google_cloud_run_v2_service", "worker"),
            ("google_cloud_run_v2_service", "web"),
            ("google_cloud_tasks_queue", "planning"),
            ("google_cloud_run_v2_service_iam_member", "api"),
            ("google_cloud_run_v2_service_iam_member", "worker"),
            ("google_cloud_run_v2_service_iam_member", "public_web"),
        },
        "operations.tf": {
            ("google_cloud_run_v2_job", "maintenance"),
            ("google_cloud_scheduler_job", "reconcile"),
            ("google_cloud_run_v2_job_iam_member", "scheduler"),
            ("google_cloud_run_v2_service_iam_member", "deploy_run"),
            ("google_cloud_run_v2_job_iam_member", "deploy_jobs"),
        },
    }
    for file in ("main.tf", "operations.tf"):
        name = "infra/terraform/" + file
        baseline = subprocess.check_output(["git", "show", LEGACY_SOURCE_BASELINE + ":" + name], cwd=ROOT, text=True)
        current = (ROOT / name).read_text(encoding="utf-8")
        declarations = r'resource\s+"([^"]+)"\s+"([^"]+)"'
        before, after = set(re.findall(declarations, baseline)), set(re.findall(declarations, current))
        assert before - after == retired[file], "Only exact runtime retirement addresses may be removed."
        assert after - before <= {("google_billing_budget", "tasteduel_migration")}
    removal_source = (ROOT / "infra/terraform/accesslife-retirement.tf").read_text(encoding="utf-8")
    removed = re.findall(
        r"removed\s*\{\s*from\s*=\s*([\w]+)\.([\w]+)\s*"
        r"lifecycle\s*\{\s*destroy\s*=\s*false\s*\}\s*\}", removal_source,
    )
    allowed = retired["main.tf"] | retired["operations.tf"]
    assert set(removed) == allowed
    assert len(removed) == len(allowed), "No duplicate or unreviewed forget-only declarations."
    source = (ROOT / "infra/terraform/main.tf").read_text(encoding="utf-8")
    for resource, name in (("google_sql_database_instance", "accesslife-db"), ("google_sql_database", "accesslife"), ("google_sql_user", "accesslife")):
        block = source.split(f'resource "{resource}" "' + ("db" if resource.endswith("instance") else "app") + '"', 1)[1].split('\nresource "', 1)[0]
        assert re.search(r'name\s*=\s*"' + name + '"', block)
        assert "prevent_destroy = true" in block
    assert 'default = "asia-south1"' in (ROOT / "infra/terraform/variables.tf").read_text()

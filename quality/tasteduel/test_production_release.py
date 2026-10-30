"""Synthetic manifests and actual Terraform-plan policy, never cloud operations."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest

import test_release_plan as fixtures

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("production_release", ROOT / "scripts/tasteduel_production_release.py")
production = importlib.util.module_from_spec(spec)
spec.loader.exec_module(production)


def manifest():
    images = fixtures.IMAGES
    baseline = {"api_revision": "tasteduel-api-existing", "web_revision": "tasteduel-web-existing",
                "api_image": images["api"], "web_image": images["web"], "source_sha": images["source_sha"],
                "vertex_limit": 10, "qloo_limit": 12}
    return {"version": 1, "project": production.PROJECT, "region": production.REGION, "origin": production.ORIGIN,
        "images": {"source_sha": images["source_sha"], "ci": {"head_sha": images["source_sha"], "status": "completed", "conclusion": "success", "id": 123},
            "images": {actor: {"reference": images[actor], "digest": "sha256:" + ("a" if actor == "api" else "b") * 64} for actor in ("api", "web")}},
        "baseline": baseline, "candidate": {"api_revision": "tasteduel-api-candidate", "web_revision": "tasteduel-web-candidate",
            "tag": "review", "origin": "https://review---tasteduel-web-verified.a.run.app", "api_url": "https://review---tasteduel-api-verified.a.run.app"},
        "release": {"api_revision": "tasteduel-api-sealed", "web_revision": "tasteduel-web-sealed"},
        "rollback": {**baseline, "api_revision": "tasteduel-api-rollback", "web_revision": "tasteduel-web-rollback", "vertex_limit": 50, "qloo_limit": 100},
        "schema": {"from": "td0010", "to": "td0011", "backward_compatible": True},
        "cost_sha256": "d" * 64, "preview_guard": "iam-private-initial", "reviewed_through_utc": "2026-11-07T04:45:00Z"}


def service(actor, phase, record):
    value = fixtures.service(actor)
    origin = production.ORIGIN
    values = production.phase_variables(record, phase)
    value["labels"] = {"app": "tasteduel", "source_ref": fixtures.IMAGES["source_sha"][:12]}
    value["uri"] = "https://tasteduel-" + actor + "-verified.a.run.app"
    value["template"][0]["revision"] = values[f"tasteduel_{actor}_candidate_revision"]
    value["traffic"] = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION", "percent": 100,
                         "revision": values[f"tasteduel_{actor}_traffic_revision"]}]
    if phase == "production-candidate":
        value["traffic"].append({"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION", "percent": 0,
                                "revision": values[f"tasteduel_{actor}_candidate_revision"], "tag": "review"})
    for env in value["template"][0]["containers"][0]["env"]:
        name = env["name"]
        if name == "TASTEDUEL_VERTEX_REQUESTS_PER_DAY":
            env["value"] = str(values["tasteduel_vertex_requests_per_day"])
        elif name == "TASTEDUEL_QLOO_REQUESTS_PER_DAY":
            env["value"] = str(values["tasteduel_qloo_requests_per_day"])
        elif name == "TASTEDUEL_ALLOWED_ORIGINS":
            env["value"] = json.dumps([origin] + ([record["candidate"]["origin"]] if phase == "production-candidate" else []), separators=(",", ":"))
        elif name == "TASTEDUEL_WEB_ORIGINS":
            env["value"] = origin + ("," + record["candidate"]["origin"] if phase == "production-candidate" else "")
        elif name == "TASTEDUEL_CANONICAL_ORIGIN":
            env["value"] = origin
        elif name in {"TASTEDUEL_API_URL", "TASTEDUEL_API_AUDIENCE"}:
            env["value"] = (record["candidate"]["api_url"] if phase == "production-candidate" and name == "TASTEDUEL_API_URL"
                            else "https://tasteduel-api-verified.a.run.app")
    return value


def plan(phase, record=None):
    record = record or manifest()
    prior = ("production-pin" if phase in {"production-pin", "production-candidate"} else
             "production-seal" if phase == "production-rollback" else
             "production-rollback" if phase == "production-rollforward" else "production-candidate")
    changes = []
    for actor in ("api", "web"):
        after, before = service(actor, phase, record), service(actor, prior, record)
        if phase == "production-pin":
            before["traffic"] = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST", "percent": 100}]
        changes.append({"address": fixtures.release.ADDRESSES[actor], "change": {
            "before": before, "after": after, "actions": ["no-op"] if phase in {"production-promote", "production-prepare"} else ["update"]}})
    if phase == "production-promote":
        changes.append({"address": "google_cloud_run_v2_service_iam_member.tasteduel_web_public[0]", "change": {"actions": ["create"], "after": {
            "project": production.PROJECT, "location": production.REGION, "name": "tasteduel-web", "role": "roles/run.invoker", "member": "allUsers"}}})
    return {"resource_changes": changes}


def test_manifest_is_allowlisted_and_never_treats_preview_tag_as_public_security():
    assert production.validate_manifest(manifest())["preview_guard"] == "iam-private-initial"
    for key, value in [("project", "unrelated"), ("region", "europe-west1"), ("origin", "https://made-up-domain.example"),
                       ("preview_guard", "zero-percent-is-private"), ("command", "terraform destroy")]:
        changed = manifest()
        changed[key] = value
        with pytest.raises(fixtures.release.PlanBlocked):
            production.validate_manifest(changed)


@pytest.mark.parametrize("field,value", [("vertex_limit", 8), ("vertex_limit", 10), ("qloo_limit", 12),
    ("api_image", "gcr.io/arbitrary:latest"), ("api_revision", "accesslife-api-old")])
def test_rollback_must_preserve_public_limits_and_taste_duel_digest_boundary(field, value):
    changed = manifest()
    changed["rollback"][field] = value
    with pytest.raises(fixtures.release.PlanBlocked):
        production.validate_manifest(changed)


@pytest.mark.parametrize("phase", [phase for phase in production.PHASES if phase != "production-observability"])
def test_declared_finite_production_phases_are_reviewable_not_automatically_applied(phase):
    result = production.audit_production(plan(phase), manifest(), phase)
    assert result["status"] == "REVIEWABLE"
    assert result["requires_independent_review"] is True
    assert result["public_access"] == (phase in {"production-promote", "production-rollback", "production-rollforward"})


def test_rollback_pair_is_prepared_privately_before_reused_for_public_traffic():
    record = manifest()
    ready = production.phase_variables(record, "production-rollback-ready")
    assert ready["tasteduel_public_enabled"] is False
    assert ready["tasteduel_candidate_tag"] is None
    assert ready["tasteduel_api_candidate_revision"] == record["rollback"]["api_revision"]
    assert ready["tasteduel_api_traffic_revision"] == record["rollback"]["api_revision"]
    rollback = production.phase_variables(record, "production-rollback")
    assert rollback["tasteduel_api_candidate_revision"] == record["release"]["api_revision"]
    assert rollback["tasteduel_api_traffic_revision"] == record["rollback"]["api_revision"]
    assert rollback["tasteduel_observability_enabled"] is True
    assert rollback["tasteduel_vertex_requests_per_day"] == 50
    assert rollback["tasteduel_qloo_requests_per_day"] == 100


@pytest.mark.parametrize("phase", ["production-rollback", "production-rollforward"])
def test_live_revision_rehearsal_preserves_public_access_monitoring_and_configuration(phase):
    record = manifest()
    variables = production.phase_variables(record, phase)
    assert variables["tasteduel_public_enabled"] is True
    assert variables["tasteduel_observability_enabled"] is True
    assert variables["tasteduel_api_candidate_revision"] == record["release"]["api_revision"]
    target = record["rollback" if phase == "production-rollback" else "release"]
    assert variables["tasteduel_api_traffic_revision"] == target["api_revision"]
    assert variables["tasteduel_web_traffic_revision"] == target["web_revision"]
    declared = plan(phase, record)
    assert production.audit_production(declared, record, phase)["status"] == "REVIEWABLE"
    # A traffic-only rehearsal cannot silently add a temporary origin or change quota.
    environment = declared["resource_changes"][0]["change"]["before"]["template"][0]["containers"][0]["env"]
    next(item for item in environment if item["name"] == "TASTEDUEL_VERTEX_REQUESTS_PER_DAY")["value"] = "10"
    assert production.audit_production(declared, record, phase)["status"] == "BLOCKED"
    declared = plan(phase, record)
    declared["resource_changes"][0]["change"]["before"]["template"][0]["revision"] = "tasteduel-api-unreviewed"
    assert production.audit_production(declared, record, phase)["status"] == "BLOCKED"
    declared = plan(phase, record)
    declared["resource_changes"].append({"address": "google_cloud_run_v2_service_iam_member.tasteduel_web_public[0]",
        "change": {"actions": ["create"], "after": {"project": production.PROJECT, "location": production.REGION,
            "name": "tasteduel-web", "member": "allUsers", "role": "roles/run.invoker"}}})
    assert production.audit_production(declared, record, phase)["status"] == "BLOCKED"


@pytest.mark.parametrize("phase", ["production-candidate", "production-seal", "production-pin"])
@pytest.mark.parametrize("field", ["command", "traffic", "identity", "quota", "cookie", "secret", "max_instances"])
def test_production_plan_rejects_hidden_entrypoints_policy_or_random_traffic(phase, field):
    value = plan(phase)
    api = value["resource_changes"][0]["change"]["after"]
    container = api["template"][0]["containers"][0]
    if field == "command":
        container["command"] = ["sh", "-c", "exfiltrate"]
    elif field == "traffic":
        api["traffic"][0]["percent"] = 50
    elif field == "identity":
        api["template"][0]["service_account"] = fixtures.release.SA["deploy"]
    elif field == "max_instances":
        api["template"][0]["scaling"][0]["max_instance_count"] = 10
    else:
        names = {"quota": ("TASTEDUEL_VERTEX_REQUESTS_PER_DAY", "500"), "cookie": ("TASTEDUEL_COOKIE_SECURE", "false"),
                 "secret": ("TASTEDUEL_QLOO_SECRET_VERSION", "versions/latest")}
        key, new = names[field]
        next(env for env in container["env"] if env["name"] == key)["value"] = new
    assert production.audit_production(value, manifest(), phase)["status"] == "BLOCKED"


@pytest.mark.parametrize("address", ["google_sql_database.app", "google_project_iam_member.admin",
    "google_cloud_run_v2_service_iam_member.tasteduel_api_web[0]", "google_secret_manager_secret_version.qloo"])
def test_production_scope_never_mutates_database_api_invocation_or_secret(address):
    value = plan("production-candidate")
    value["resource_changes"].append({"address": address, "change": {"actions": ["update"], "after": {}}})
    assert production.audit_production(value, manifest(), "production-candidate")["status"] == "BLOCKED"


def test_public_grant_is_web_only_and_promotion_cannot_change_a_template():
    value = plan("production-promote")
    value["resource_changes"][-1]["change"]["after"]["name"] = "tasteduel-api"
    assert production.audit_production(value, manifest(), "production-promote")["status"] == "BLOCKED"
    value = plan("production-promote")
    value["resource_changes"][0]["change"]["actions"] = ["update"]
    assert production.audit_production(value, manifest(), "production-promote")["status"] == "BLOCKED"


@pytest.mark.parametrize("name,value", [("TASTEDUEL_API_URL", "https://tasteduel-api-verified.a.run.app"),
    ("TASTEDUEL_API_URL", "https://untrusted.example"),
    ("TASTEDUEL_API_AUDIENCE", "https://review---tasteduel-api-verified.a.run.app")])
def test_candidate_web_reaches_exact_tagged_api_but_audience_remains_canonical(name, value):
    record = manifest()
    declared = plan("production-candidate", record)
    assert production.audit_production(declared, record, "production-candidate")["status"] == "REVIEWABLE"
    web = declared["resource_changes"][1]["change"]["after"]
    next(env for env in web["template"][0]["containers"][0]["env"] if env["name"] == name)["value"] = value
    assert production.audit_production(declared, record, "production-candidate")["status"] == "BLOCKED"


def test_public_services_cannot_keep_a_candidate_tag_even_with_zero_allocation():
    declared = plan("production-promote")
    declared["resource_changes"][1]["change"]["after"]["traffic"].append({
        "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION", "revision": "tasteduel-web-candidate", "percent": 0, "tag": "review"})
    assert production.audit_production(declared, manifest(), "production-promote")["status"] == "BLOCKED"


def evidence(record):
    return {"kind": "sealed-smoke", "status": "PASS", "manifest_sha256": production.digest(record),
        "source_sha": record["images"]["source_sha"], **record["release"],
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {"gameplay": True, "fixed_replay": True, "private_api": True, "secrecy": True,
                   "axe": True, "keyboard": True, "reduced_motion": True}}


@pytest.mark.parametrize("field,value", [("status", "PARTIAL"), ("manifest_sha256", "0" * 64),
    ("api_revision", "tasteduel-api-future"), ("source_sha", "0" * 40),
    ("checked_at_utc", (datetime.now(timezone.utc) - timedelta(days=2)).isoformat())])
def test_smoke_acceptance_is_fresh_and_bound_to_exact_manifest_configuration(field, value):
    record = manifest()
    item = evidence(record)
    production.check_evidence(item, record, kind="sealed-smoke")
    item[field] = value
    with pytest.raises(fixtures.release.PlanBlocked):
        production.check_evidence(item, record, kind="sealed-smoke")


def test_smoke_contract_never_accepts_numeric_true_or_implicit_version_true():
    record = manifest()
    item = evidence(record)
    item["checks"]["gameplay"] = 1
    with pytest.raises(fixtures.release.PlanBlocked):
        production.check_evidence(item, record, kind="sealed-smoke")
    record["version"] = True
    with pytest.raises(fixtures.release.PlanBlocked):
        production.validate_manifest(record)


def test_pre_migration_api_image_is_not_a_public_rollback_even_with_same_schema_tables():
    record = manifest()
    record["rollback"]["api_image"] = fixtures.publisher.immutable_reference("tasteduel-api", "sha256:" + "e" * 64)
    with pytest.raises(fixtures.release.PlanBlocked, match="SCHEMA_COMPATIBLE"):
        production.validate_manifest(record)


def test_fixed_operations_command_requires_reviewed_flags_without_payload_or_arbitrary_arguments():
    record = manifest()
    command = production.operations_command("migrate", record, execute=True)
    assert command[:6] == ["gcloud", "run", "jobs", "execute", "tasteduel-migrate", "--project"]
    assert "--args=migrate,--execute-reviewed-operation,--cost-review-sha256," + record["cost_sha256"] in command
    assert "--wait" in command and not any("secret" in arg for arg in command)
    with pytest.raises(fixtures.release.PlanBlocked):
        production.operations_command("migrate", record, execute=False)
    with pytest.raises(fixtures.release.PlanBlocked):
        production.operations_command("destroy", record, execute=True)
    with pytest.raises(fixtures.release.PlanBlocked):
        production.operations_command("promote-public-budget", record, execute=True)
    inspected = production.operations_command("promote-public-budget", record, execute=False)
    assert "--args=promote-public-budget" in inspected
    changed = production.operations_command("promote-public-budget", record, execute=True, snapshot="a" * 64)
    assert "--expected-snapshot-sha256," + "a" * 64 in " ".join(changed)


def test_prepare_updates_only_exact_new_migration_job_and_preserves_service_pins():
    record = manifest()
    declared = plan("production-prepare", record)
    before = fixtures.job()
    before["labels"] = {"app": "tasteduel", "source_ref": record["baseline"]["source_sha"][:12]}
    after = fixtures.job()
    after["labels"] = {"app": "tasteduel", "source_ref": record["images"]["source_sha"][:12]}
    container = after["template"][0]["template"][0]["containers"][0]
    container["command"], container["args"] = ["python", "-m", "tasteduel.operations"], ["migrate"]
    container["env"] += [{"name": "TASTEDUEL_OPS_COST_REVIEW_HASH", "value": record["cost_sha256"]},
                         {"name": "TASTEDUEL_OPS_REVIEWED_THROUGH_UTC", "value": record["reviewed_through_utc"]}]
    declared["resource_changes"].append({"address": fixtures.release.ADDRESSES["migrate"], "change": {
        "before": before, "after": after, "actions": ["update"]}})
    assert production.audit_production(declared, record, "production-prepare")["status"] == "REVIEWABLE"
    container["env"][-2]["value"] = "0" * 64
    assert production.audit_production(declared, record, "production-prepare")["status"] == "BLOCKED"


def test_candidate_and_sealed_revisions_must_not_reuse_immutable_names():
    record = manifest()
    record["release"] = {key: value for key, value in record["candidate"].items() if key.endswith("_revision")}
    with pytest.raises(fixtures.release.PlanBlocked):
        production.validate_manifest(record)


def test_workflow_has_no_legacy_job_or_arbitrary_deploy_and_keeps_numeric_wif():
    source = (ROOT / ".github/workflows/cloud-release.yml").read_text()
    assert "1431472864" in source and "60200140" in source
    assert "foundation-review" in source and "refs/heads/main" in source
    assert "tasteduel_production_release.py" in source
    for prohibited in ("accesslife-ingest", "accesslife-reconcile", "roles/run.admin", "secrets versions access", "terraform apply"):
        assert prohibited not in source

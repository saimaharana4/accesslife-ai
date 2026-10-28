"""Synthetic release controls; no Docker builds, credentials or cloud calls."""

import importlib.util
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


release = module("tasteduel_release_plan")
publisher = module("tasteduel_release_images")
applier = module("tasteduel_release_apply")
IMAGES = {"api": publisher.immutable_reference("tasteduel-api", "sha256:" + "a" * 64),
          "web": publisher.immutable_reference("tasteduel-web", "sha256:" + "b" * 64), "source_sha": "c" * 40}
ORIGIN = "https://tasteduel-web-123456789012.asia-south1.run.app"
TESTER = "user:synthetic-reviewer@example.invalid"


def resources(actor):
    return [{"limits": {"cpu": "1", "memory": "1Gi" if actor == "api" else "512Mi"},
             "cpu_idle": True, "startup_cpu_boost": False}]


def mount():
    return [{"name": "cloudsql", "mount_path": "/cloudsql"}]


def volumes():
    return [{"name": "cloudsql", "cloud_sql_instance": [{"instances": [release.CONNECTION]}]}]


def environment(values):
    return [{"name": key, "value": value} for key, value in values.items()]


def job():
    return {"name": "tasteduel-migrate", "project": release.PROJECT, "location": release.REGION,
            "deletion_protection": True, "template": [{"task_count": 1, "parallelism": 1, "template": [{
                "service_account": release.SA["migrate"], "timeout": "300s", "max_retries": 0, "volumes": volumes(),
                "containers": [{"image": IMAGES["api"], "command": ["alembic"],
                    "args": ["-c", "apps/api/tasteduel-alembic.ini", "upgrade", "head"], "resources": resources("migrate"),
                    "volume_mounts": mount(), "env": environment({"TASTEDUEL_DATABASE_MODE": "cloud_sql",
                        "TASTEDUEL_CLOUD_SQL_CONNECTION_NAME": release.CONNECTION,
                        "TASTEDUEL_MIGRATION_DATABASE_SECRET_VERSION": release.secret_reference("migrate"),
                        "TASTEDUEL_QLOO_ENABLED": "false", "TASTEDUEL_GENERATION_ENABLED": "false"})}],
            }]}]}


def service(actor):
    values = {"TASTEDUEL_API_URL": None, "TASTEDUEL_API_AUDIENCE": None, "TASTEDUEL_API_IAM": "true",
              "TASTEDUEL_WEB_ORIGINS": ORIGIN, "TASTEDUEL_CANONICAL_ORIGIN": ORIGIN, "TASTEDUEL_ALLOW_LOCAL_HTTP": "false"}
    if actor == "api":
        values = {"TASTEDUEL_DATABASE_MODE": "cloud_sql", "TASTEDUEL_CLOUD_SQL_CONNECTION_NAME": release.CONNECTION,
                  "TASTEDUEL_DATABASE_SECRET_VERSION": release.secret_reference("api"), "TASTEDUEL_COOKIE_SECURE": "true",
                  "TASTEDUEL_ALLOWED_ORIGINS": json.dumps([ORIGIN], separators=(",", ":")), "TASTEDUEL_QLOO_ENABLED": "true",
                  "TASTEDUEL_QLOO_TRANSPORT": "http_ranked", "TASTEDUEL_QLOO_HTTP_TYPED_SEARCH": "true",
                  "TASTEDUEL_QLOO_SECRET_VERSION": f"projects/{release.PROJECT}/secrets/accesslife-qloo-api-key/versions/1",
                  "TASTEDUEL_GENERATION_ENABLED": "true", "TASTEDUEL_VERTEX_PROJECT": release.PROJECT,
                  "TASTEDUEL_VERTEX_REQUESTS_PER_DAY": "10", "TASTEDUEL_VERTEX_TOKENS_PER_DAY": "500000",
                  "TASTEDUEL_QLOO_REQUESTS_PER_DAY": "12", "TASTEDUEL_QLOO_REQUESTS_PER_MINUTE": "12"}
    return {"name": "tasteduel-" + actor, "project": release.PROJECT, "location": release.REGION,
            "deletion_protection": True, "ingress": "INGRESS_TRAFFIC_ALL",
            "traffic": [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST", "percent": 100}],
            "template": [{"service_account": release.SA[actor], "timeout": "60s",
                "max_instance_request_concurrency": 8 if actor == "api" else 20,
                "scaling": [{"min_instance_count": 0, "max_instance_count": 1}],
                "volumes": volumes() if actor == "api" else [],
                "containers": [{"image": IMAGES[actor], "ports": [{"container_port": 8000 if actor == "api" else 3000}],
                    "resources": resources(actor), "volume_mounts": mount() if actor == "api" else [],
                    "env": environment(values)}]}]}


def change(key, after, actions=None):
    result = {"address": release.ADDRESSES.get(key, key), "change": {"actions": actions or ["create"], "after": after}}
    if key == "web":
        env = after["template"][0]["containers"][0]["env"]
        result["change"]["after_unknown"] = {"template": [{"containers": [{"env": [
            {"value": True} if item["name"] in {"TASTEDUEL_API_URL", "TASTEDUEL_API_AUDIENCE"} else {} for item in env
        ]}]}]}
    return result


def audit(changes, phase="migration"):
    return release.audit_release({"resource_changes": changes}, phase=phase, images=IMAGES,
                                 tester=TESTER, project_number="123456789012")


def test_exact_new_migration_job_is_reviewable_but_never_old_job_or_database_change():
    assert audit([change("migrate", job())])["status"] == "REVIEWABLE"
    for address, actions in (("google_sql_database.app", ["delete"]),
                             ('google_cloud_run_v2_job.maintenance["migrate"]', ["create"]),
                             ("google_sql_user.app", ["update"]),
                             ("google_secret_manager_secret_version.database", ["update"])):
        assert audit([change(address, {}, actions)])["status"] == "BLOCKED"


@pytest.mark.parametrize("field,value", [("max_retries", 1), ("service_account", release.SA["api"]), ("timeout", "3600s")])
def test_job_cannot_widen_runtime_retries_or_identity(field, value):
    after = job()
    after["template"][0]["template"][0][field] = value
    assert audit([change("migrate", after)])["status"] == "BLOCKED"


def test_job_cannot_read_old_database_injected_payload_or_enable_provider():
    for name, value in (("TASTEDUEL_DATABASE_URL", "synthetic-private-payload"), ("TASTEDUEL_QLOO_ENABLED", "true")):
        after = job()
        after["template"][0]["template"][0]["containers"][0]["env"].append({"name": name, "value": value})
        result = audit([change("migrate", after)])
        assert result["status"] == "BLOCKED"
        assert "synthetic-private-payload" not in json.dumps(result)


def test_services_are_forbidden_in_migration_phase_and_supported_in_service_phase():
    for actor in ("api", "web"):
        assert audit([change(actor, service(actor))])["status"] == "BLOCKED"
        assert audit([change(actor, service(actor))], "services")["status"] == "REVIEWABLE"


@pytest.mark.parametrize("actor", ["migrate", "api", "web"])
def test_private_candidate_refresh_allows_only_images_and_source_labels(actor):
    from copy import deepcopy

    after = job() if actor == "migrate" else service(actor)
    after["labels"] = {"app": "tasteduel", "source_ref": IMAGES["source_sha"][:12]}
    before = deepcopy(after)
    before["labels"]["source_ref"] = "d" * 12
    task = before["template"][0]
    if actor == "migrate":
        task = task["template"][0]
    task["containers"][0]["image"] = publisher.immutable_reference(
        "tasteduel-api" if actor == "migrate" else "tasteduel-" + actor, "sha256:" + "d" * 64,
    )
    update = change(actor, after, ["update"])
    update["change"]["before"] = before
    assert audit([update], "refresh")["status"] == "REVIEWABLE"
    after["labels"]["environment"] = "unexpected"
    assert audit([update], "refresh")["status"] == "BLOCKED"
    del after["labels"]["environment"]
    task = after["template"][0]
    if actor == "migrate":
        task = task["template"][0]
    task["service_account"] = release.SA["deploy"]
    assert audit([update], "refresh")["status"] == "BLOCKED"


def test_refresh_never_creates_replaces_changes_iam_or_touches_sql():
    for address, action in [("api", ["create"]), ("api", ["delete", "create"]),
                            ("api_web", ["update"]), ("google_sql_database.app", ["update"])]:
        assert audit([change(address, {}, action)], "refresh")["status"] == "BLOCKED"


def test_explicit_verification_allowance_changes_only_six_to_eight_on_api():
    from copy import deepcopy

    after = service("api")
    for item in after["template"][0]["containers"][0]["env"]:
        if item["name"] == "TASTEDUEL_VERTEX_REQUESTS_PER_DAY":
            item["value"] = "8"
    before = deepcopy(after)
    for item in before["template"][0]["containers"][0]["env"]:
        if item["name"] == "TASTEDUEL_VERTEX_REQUESTS_PER_DAY":
            item["value"] = "6"
    update = change("api", after, ["update"])
    update["change"]["before"] = before
    assert audit([update], "verification-budget")["status"] == "REVIEWABLE"
    after["template"][0]["timeout"] = "90s"
    assert audit([update], "verification-budget")["status"] == "BLOCKED"
    assert audit([change("web", service("web"), ["update"])], "verification-budget")["status"] == "BLOCKED"


def closure_allowance_update():
    from copy import deepcopy

    after = service("api")
    before = deepcopy(after)
    for item in before["template"][0]["containers"][0]["env"]:
        if item["name"] == "TASTEDUEL_VERTEX_REQUESTS_PER_DAY":
            item["value"] = "8"
    update = change("api", after, ["update"])
    update["change"]["before"] = before
    return update


def test_candidate_closure_allowance_is_a_distinct_private_eight_to_ten_update():
    update = closure_allowance_update()
    result = audit([update], "candidate-closure-budget")
    assert result["status"] == "REVIEWABLE"
    assert result["public_access"] is False
    assert result["requires_independent_review"] is True
    assert audit([update], "verification-budget")["status"] == "BLOCKED"
    assert audit([update], "refresh")["status"] == "BLOCKED"


@pytest.mark.parametrize("side,limit", [("before", "6"), ("before", "9"), ("before", "10"),
                                       ("after", "8"), ("after", "11"), ("after", "50")])
def test_closure_allowance_rejects_wrong_baseline_or_unapproved_limit(side, limit):
    update = closure_allowance_update()
    for item in update["change"][side]["template"][0]["containers"][0]["env"]:
        if item["name"] == "TASTEDUEL_VERTEX_REQUESTS_PER_DAY":
            item["value"] = limit
    assert audit([update], "candidate-closure-budget")["status"] == "BLOCKED"


@pytest.mark.parametrize("name,value", [("TASTEDUEL_QLOO_REQUESTS_PER_DAY", "16"),
    ("TASTEDUEL_VERTEX_TOKENS_PER_DAY", "600000"), ("TASTEDUEL_COOKIE_SECURE", "false"),
    ("TASTEDUEL_QLOO_SECRET_VERSION", "versions/latest"), ("TASTEDUEL_RESET_USAGE", "true"),
    ("TASTEDUEL_USAGE_WINDOW", "new-window"), ("TASTEDUEL_USAGE_EXPIRES_AT", "2099-01-01")])
def test_closure_allowance_never_resets_usage_or_changes_other_environment(name, value):
    update = closure_allowance_update()
    environment = update["change"]["after"]["template"][0]["containers"][0]["env"]
    for item in environment:
        if item["name"] == name:
            item["value"] = value
            break
    else:
        environment.append({"name": name, "value": value})
    assert audit([update], "candidate-closure-budget")["status"] == "BLOCKED"


@pytest.mark.parametrize("field", ["image", "identity", "timeout", "traffic", "labels", "scaling", "usage"])
def test_closure_allowance_cannot_bundle_configuration_or_private_counter_changes(field):
    update = closure_allowance_update()
    after = update["change"]["after"]
    template = after["template"][0]
    if field == "image":
        template["containers"][0]["image"] = publisher.immutable_reference("tasteduel-api", "sha256:" + "d" * 64)
    elif field == "identity":
        template["service_account"] = release.SA["deploy"]
    elif field == "timeout":
        template["timeout"] = "90s"
    elif field == "traffic":
        after["traffic"][0]["percent"] = 50
    elif field == "labels":
        after["labels"] = {"source_ref": "d" * 12}
    elif field == "scaling":
        template["scaling"][0]["max_instance_count"] = 2
    else:
        after["usage_counter"] = {"used": 0, "window": "replacement", "expiry": "extended"}
    assert audit([update], "candidate-closure-budget")["status"] == "BLOCKED"


@pytest.mark.parametrize("address", ["web", "api_web", "google_sql_database.app",
    "postgresql_query.reset_usage", "google_secret_manager_secret_version.database"])
def test_closure_allowance_cannot_mutate_any_other_resource_or_reset_database_usage(address):
    reset = change(release.ADDRESSES.get(address, address),
                   {"used": 0, "window": "replacement", "expiry": "extended"}, ["update"])
    assert audit([closure_allowance_update(), reset], "candidate-closure-budget")["status"] == "BLOCKED"


@pytest.mark.parametrize("actions", [["create"], ["delete"], ["delete", "create"]])
def test_closure_allowance_cannot_replace_or_recreate_the_service(actions):
    update = closure_allowance_update()
    update["change"]["actions"] = actions
    assert audit([update], "candidate-closure-budget")["status"] == "BLOCKED"


def test_unknown_release_phase_is_never_reviewable_even_without_changes():
    assert audit([], "unapproved-budget")["status"] == "BLOCKED"


def test_candidates_are_reported_as_real_100_percent_iam_restricted_not_zero_traffic():
    result = audit([change("api", service("api"))], "services")
    assert result["initial_service_allocation_percent"] == 100
    assert result["public_access"] is False
    assert result["requires_independent_review"] is True


def test_web_must_use_actual_api_uri_or_plan_unknown_not_arbitrary_destination():
    after = service("web")
    for item in after["template"][0]["containers"][0]["env"]:
        if item["name"] in {"TASTEDUEL_API_URL", "TASTEDUEL_API_AUDIENCE"}:
            item["value"] = "https://unrelated.example.invalid"
    assert audit([change("web", after)], "services")["status"] == "BLOCKED"


@pytest.mark.parametrize("name,value", [("TASTEDUEL_QLOO_REQUESTS_PER_DAY", "300"),
    ("TASTEDUEL_VERTEX_REQUESTS_PER_DAY", "50"), ("TASTEDUEL_QLOO_TRANSPORT", "mcp"),
    ("TASTEDUEL_COOKIE_SECURE", "false"), ("TASTEDUEL_QLOO_SECRET_VERSION", "versions/latest")])
def test_api_cannot_widen_live_budget_or_claim_wrong_transport(name, value):
    after = service("api")
    for item in after["template"][0]["containers"][0]["env"]:
        if item["name"] == name:
            item["value"] = value
    assert audit([change("api", after)], "services")["status"] == "BLOCKED"


def test_private_api_grant_rejects_public_or_unrelated_invoker():
    after = {"name": "tasteduel-api", "role": "roles/run.invoker", "member": "serviceAccount:" + release.SA["web"],
             "project": release.PROJECT, "location": release.REGION}
    assert audit([change("api_web", after)], "services")["status"] == "REVIEWABLE"
    for member in ("allUsers", "allAuthenticatedUsers", TESTER):
        assert audit([change("api_web", {**after, "member": member})], "services")["status"] == "BLOCKED"


def test_reviewer_is_exact_principal_and_deploy_role_is_resource_scoped():
    after = {"name": "tasteduel-web", "role": "roles/run.invoker", "member": TESTER,
             "project": release.PROJECT, "location": release.REGION}
    assert audit([change("web_tester", after)], "services")["status"] == "REVIEWABLE"
    assert audit([change("web_tester", {**after, "member": "domain:example.invalid"})], "services")["status"] == "BLOCKED"
    assert audit([change("google_project_iam_member.run_admin", {"role": "roles/run.admin"})], "services")["status"] == "BLOCKED"


def test_ci_requires_successful_main_push_for_exact_archive_sha():
    run = {"head_sha": "c" * 40, "head_branch": "main", "status": "completed", "conclusion": "success",
           "event": "push", "path": ".github/workflows/ci.yml", "repository": {"full_name": publisher.REPOSITORY},
           "id": 123, "html_url": "https://example.invalid/synthetic-ci"}
    assert publisher.verified_ci(run, "c" * 40)["head_sha"] == "c" * 40
    for patch in ({"head_sha": "d" * 40}, {"event": "pull_request"}, {"conclusion": "failure"}, {"path": "auth-only.yml"}):
        with pytest.raises(release.PlanBlocked):
            publisher.verified_ci({**run, **patch}, "c" * 40)


@pytest.mark.parametrize("package,digest", [("accesslife-api", "sha256:" + "a" * 64), ("tasteduel-api", "latest"),
                                           ("tasteduel-web", "sha256:" + "A" * 64)])
def test_no_dummy_or_mutable_image_references(package, digest):
    with pytest.raises(release.PlanBlocked):
        publisher.immutable_reference(package, digest)


def test_release_record_requires_matching_completed_ci_and_exact_digest_provenance():
    record = {"source_sha": IMAGES["source_sha"], "ci": {"head_sha": IMAGES["source_sha"],
              "conclusion": "success", "status": "completed"}, "images": {
        "api": {"reference": IMAGES["api"], "digest": "sha256:" + "a" * 64},
        "web": {"reference": IMAGES["web"], "digest": "sha256:" + "b" * 64},
    }}
    assert release.images_input(record) == IMAGES
    record["ci"]["head_sha"] = "d" * 40
    with pytest.raises(release.PlanBlocked):
        release.images_input(record)


@pytest.fixture
def saved_release(tmp_path, monkeypatch):
    monkeypatch.setattr(applier.foundation, "ROOT", tmp_path)
    current = tmp_path / "infra/terraform"
    directory = tmp_path / ".data/tasteduel-cloud-review/synthetic-release-plan"
    for target in (current, directory):
        target.mkdir(parents=True)
        (target / "main.tf").write_text('terraform {}\n', encoding="utf-8")
        (target / ".terraform.lock.hcl").write_text('', encoding="utf-8")
    (directory / "release.tfplan").write_bytes(b"SYNTHETIC_PLAN_NOT_A_REAL_APPLY_PLAN")
    now = datetime.now(timezone.utc)
    cost = {"cost_gate_status": "PASS", "billing_reconciled": True, "cost_review_passed": True,
            "reviewed_total_usd": 84.03, "reviewed_through_utc": max(now + timedelta(days=15), applier.foundation.MINIMUM_HORIZON).isoformat(),
            "billing_account": "AAAAAA-BBBBBB-CCCCCC", "budget_currency": "INR", "budget_alert_units": 6507,
            "migration_alert_units": 6972, "accrued_cost_evidence": "synthetic-only-review",
            "approved_at_utc": now.isoformat()}
    review = {"status": "REVIEWABLE", "phase": "migration", "image_source_sha": IMAGES["source_sha"],
              "source_sha256": applier.source_hash(current), "reviewed_total_usd": 84.03,
              "plan_sha256": hashlib.sha256((directory / "release.tfplan").read_bytes()).hexdigest()}
    approval = {**{key: review[key] for key in ("phase", "image_source_sha", "source_sha256", "plan_sha256")},
                "independent_review": "PASS"}
    return directory, current, review, approval, cost


def test_exact_saved_hashes_and_independent_approval_are_required(saved_release):
    directory, current, review, approval, cost = saved_release
    assert applier.verify(directory, review, approval, cost)["budget_usd"] == 90
    with pytest.raises(release.PlanBlocked):
        applier.verify(directory, review, {**approval, "independent_review": "PENDING"}, cost)
    with pytest.raises(release.PlanBlocked):
        applier.verify(directory, review, {**approval, "phase": "services"}, cost)
    (current / "main.tf").write_text('terraform {}\n# changed-after-review\n', encoding="utf-8")
    with pytest.raises(release.PlanBlocked):
        applier.verify(directory, review, approval, cost)


def test_closure_saved_plan_requires_matching_independent_phase_approval(saved_release):
    directory, _, review, approval, cost = saved_release
    review = {**review, "phase": "candidate-closure-budget"}
    approval = {**approval, "phase": "candidate-closure-budget"}
    assert applier.verify(directory, review, approval, cost)["budget_usd"] == 90
    with pytest.raises(release.PlanBlocked, match="PHASE_MISMATCH"):
        applier.verify(directory, review, {**approval, "phase": "verification-budget"}, cost)


def test_saved_plan_tamper_or_prior_attempt_blocks_automatic_retry(saved_release):
    directory, _, review, approval, cost = saved_release
    original = (directory / "release.tfplan").read_bytes()
    (directory / "release.tfplan").write_bytes(original + b"tampered")
    with pytest.raises(release.PlanBlocked):
        applier.verify(directory, review, approval, cost)
    (directory / "release.tfplan").write_bytes(original)
    (directory / "apply-journal.json").write_text('{"status":"STARTED"}', encoding="utf-8")
    with pytest.raises(release.PlanBlocked):
        applier.verify(directory, review, approval, cost)
    assert json.loads((directory / "apply-journal.json").read_text())["status"] == "STARTED"


def test_apply_inputs_cannot_change_approved_images_source_tester_or_phase():
    expected = {"tasteduel_release_migration_enabled": True, "tasteduel_release_services_enabled": False,
                "tasteduel_release_api_image": IMAGES["api"], "tasteduel_release_web_image": IMAGES["web"],
                "tasteduel_release_source_sha": IMAGES["source_sha"], "tasteduel_candidate_tester": TESTER}
    plan = {"variables": {key: {"value": value} for key, value in expected.items()}}
    review = {"phase": "migration", "image_source_sha": IMAGES["source_sha"]}
    assert applier.plan_inputs(plan, review, IMAGES, TESTER) == expected
    with pytest.raises(release.PlanBlocked):
        applier.plan_inputs(plan, review, IMAGES, "user:other@example.invalid")
    with pytest.raises(release.PlanBlocked):
        applier.plan_inputs(plan, {**review, "phase": "services"}, IMAGES, TESTER)


@pytest.mark.parametrize("actual,expected,valid", [
    ("true", True, True), ("false", False, True), ("84.03", 84.03, True),
    ("90", 90, True), ("TRUE", True, False), (1, True, False),
    ("1", True, False), (True, 1, False), ("false", True, False),
    ("01", 1, False), ("https://fixed.run.app", "https://fixed.run.app", True),
])
def test_saved_environment_scalar_validation_is_typed_and_fail_closed(actual, expected, valid):
    assert applier.saved_input_matches(actual, expected) is valid


def test_image_tools_resolve_platform_executables_without_shell_or_credentials(monkeypatch):
    from types import SimpleNamespace

    captured = []
    monkeypatch.setattr(publisher.shutil, "which", lambda name: "/reviewed/bin/" + name)

    def run(arguments, **kwargs):
        captured.append((arguments, kwargs))
        return SimpleNamespace(returncode=0, stdout="safe-result")

    monkeypatch.setattr(publisher.subprocess, "run", run)
    assert publisher.process(["gcloud", "auth", "configure-docker", "--quiet"]) == "safe-result"
    assert captured[0][0][0] == "/reviewed/bin/gcloud"
    assert captured[0][1].get("shell") is not True
    monkeypatch.setattr(publisher.shutil, "which", lambda name: None)
    with pytest.raises(release.PlanBlocked, match="IMAGE_TOOL_UNAVAILABLE"):
        publisher.process(["gcloud"])
    assert len(captured) == 1


def test_apply_command_is_saved_plan_only_with_environment_names_and_read_only_adc(tmp_path):
    marker = "SYNTHETIC_PRIVATE_CREDENTIAL_NOT_ARGV"
    command = applier.apply_command(tmp_path, tmp_path / "adc.json", {"TF_VAR_database_password": marker})
    assert command[-5:] == ["apply", "-json", "-input=false", "-lock-timeout=60s", "release.tfplan"]
    assert marker not in json.dumps(command)
    assert not any(value.startswith(("-target", "-replace", "-destroy", "-auto-approve")) for value in command)
    assert "readonly" in " ".join(command)

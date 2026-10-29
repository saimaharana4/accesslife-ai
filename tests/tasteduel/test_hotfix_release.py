"""Synthetic full-root hotfix plans; no credentials, provider or cloud calls."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import test_production_release as original
import test_release_plan as fixtures

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import tasteduel_hotfix_release as hotfix


def cost():
    return {
        "reviewed_total_usd": 88.15,
        "reviewed_through_utc": "2026-11-07T04:45:00Z",
        "cost_gate_status": "PASS",
    }


def previous():
    value = original.manifest()
    value["cost_sha256"] = hotfix.digest(cost())
    return value


@pytest.fixture(autouse=True)
def synthetic_baseline(monkeypatch):
    monkeypatch.setattr(hotfix, "baseline_reference", previous)


def manifest():
    old = previous()
    images = deepcopy(old["images"])
    images["source_sha"] = images["ci"]["head_sha"] = "f" * 40
    for actor, token in (("api", "d"), ("web", "e")):
        images["images"][actor] = {
            "digest": "sha256:" + token * 64,
            "reference": fixtures.publisher.immutable_reference("tasteduel-" + actor, "sha256:" + token * 64),
        }
    old_images = hotfix.images_input(old["images"])
    return {
        "version": 1,
        "kind": "compatible-public-hotfix",
        "project": hotfix.PROJECT,
        "region": hotfix.REGION,
        "origin": hotfix.ORIGIN,
        "images": images,
        "baseline_manifest_sha256": hotfix.digest(old),
        "baseline": {
            **old["release"],
            "api_image": old_images["api"],
            "web_image": old_images["web"],
            "source_sha": old_images["source_sha"],
        },
        "candidate": {
            "api_revision": "tasteduel-api-hotfix-candidate",
            "web_revision": "tasteduel-web-hotfix-candidate",
            "tag": "hotfix",
            "origin": "https://hotfix---tasteduel-web-dfthmgvvaa-el.a.run.app",
            "api_url": "https://hotfix---tasteduel-api-dfthmgvvaa-el.a.run.app",
        },
        "release": {
            "api_revision": "tasteduel-api-hotfix-sealed",
            "web_revision": "tasteduel-web-hotfix-sealed",
        },
        "schema": {"from": "td0011", "to": "td0011", "backward_compatible": True},
        "cost_sha256": old["cost_sha256"],
        "reviewed_through_utc": old["reviewed_through_utc"],
        "preview_exposure": "public-tag-intentionally-reachable",
    }


def service(actor, phase):
    record = manifest()
    value = fixtures.service(actor)
    baseline = phase == "baseline"
    images = hotfix.images_input(previous()["images"] if baseline else record["images"])
    selected = (
        record["baseline"]
        if baseline
        else record["candidate"]
        if phase == "hotfix-candidate"
        else record["release"]
    )
    value["uri"] = hotfix.API_URI if actor == "api" else "https://tasteduel-web-dfthmgvvaa-el.a.run.app"
    value["labels"] = {"app": "tasteduel", "source_ref": images["source_sha"][:12]}
    value["template"][0]["revision"] = selected[actor + "_revision"]
    container = value["template"][0]["containers"][0]
    container["image"] = images[actor]
    value["traffic"] = (
        [
            {
                "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                "percent": 100,
                "revision": selected[actor + "_revision"],
            }
        ]
        if baseline
        else hotfix.routes(record, phase, actor)
    )
    for env in container["env"]:
        if env["name"] == "TASTEDUEL_VERTEX_REQUESTS_PER_DAY":
            env["value"] = "50"
        elif env["name"] == "TASTEDUEL_QLOO_REQUESTS_PER_DAY":
            env["value"] = "100"
        elif env["name"] == "TASTEDUEL_ALLOWED_ORIGINS":
            env["value"] = json.dumps(
                [hotfix.ORIGIN] + ([record["candidate"]["origin"]] if phase == "hotfix-candidate" else []),
                separators=(",", ":"),
            )
        elif env["name"] == "TASTEDUEL_WEB_ORIGINS":
            env["value"] = hotfix.ORIGIN + (
                "," + record["candidate"]["origin"] if phase == "hotfix-candidate" else ""
            )
        elif env["name"] == "TASTEDUEL_CANONICAL_ORIGIN":
            env["value"] = hotfix.ORIGIN
        elif env["name"] == "TASTEDUEL_API_AUDIENCE":
            env["value"] = hotfix.API_URI
        elif env["name"] == "TASTEDUEL_API_URL":
            env["value"] = record["candidate"]["api_url"] if phase == "hotfix-candidate" else hotfix.API_URI
    return value


def plan(phase="hotfix-candidate"):
    prior = {
        "hotfix-candidate": "baseline",
        "hotfix-seal": "hotfix-candidate",
        "hotfix-promote": "hotfix-seal",
        "hotfix-rollback": "hotfix-promote",
        "hotfix-rollforward": "hotfix-rollback",
    }[phase]
    entries = [
        {
            "address": hotfix.ADDRESSES[actor],
            "change": {
                "actions": ["update"],
                "before": service(actor, prior),
                "after": service(actor, phase),
            },
        }
        for actor in ("api", "web")
    ]
    job = fixtures.job()
    container = job["template"][0]["template"][0]["containers"][0]
    container["command"], container["args"] = ["python", "-m", "tasteduel.operations"], ["migrate"]
    container["env"] += fixtures.environment(
        {
            "TASTEDUEL_OPS_COST_REVIEW_HASH": previous()["cost_sha256"],
            "TASTEDUEL_OPS_REVIEWED_THROUGH_UTC": previous()["reviewed_through_utc"],
        }
    )
    protected = {
        hotfix.ADDRESSES["migrate"]: job,
        hotfix.PUBLIC_WEB: {
            "project": hotfix.PROJECT,
            "location": hotfix.REGION,
            "name": "tasteduel-web",
            "member": "allUsers",
            "role": "roles/run.invoker",
        },
        hotfix.ADDRESSES["api_web"]: {
            "project": hotfix.PROJECT,
            "location": hotfix.REGION,
            "name": "tasteduel-api",
            "member": "serviceAccount:" + hotfix.SA["web"],
            "role": "roles/run.invoker",
        },
        **{key: {"id": "synthetic-protected-" + str(index)} for index, key in enumerate(hotfix.MONITORS)},
    }
    for address, payload in protected.items():
        entries.append(
            {
                "address": address,
                "change": {"actions": ["no-op"], "before": deepcopy(payload), "after": deepcopy(payload)},
            }
        )
    return {"resource_changes": entries}


def change(value, address):
    return next(
        item["change"]
        for item in value["resource_changes"]
        if item["address"] == hotfix.ADDRESSES.get(address, address)
    )


@pytest.mark.parametrize("phase", hotfix.PHASES)
def test_exact_finite_two_service_phases_preserve_public_state_and_do_not_apply(phase):
    proposed = plan(phase)
    before = deepcopy(proposed)
    result = hotfix.audit_plan(proposed, manifest(), phase)
    assert result["status"] == "REVIEWABLE" and result["requires_independent_review"]
    assert len(result["actions"]) == 2 and result["public_access"] is True
    assert proposed == before
    values = hotfix.phase_variables(manifest(), phase)
    assert (
        values["tasteduel_vertex_requests_per_day"] == 50 and values["tasteduel_qloo_requests_per_day"] == 100
    )
    assert values["tasteduel_release_migration_image"] == previous()["images"]["images"]["api"]["reference"]


@pytest.mark.parametrize(
    "attack",
    ["project", "region", "origin", "schema", "baseline", "cost", "tag", "image", "same_source", "extra"],
)
def test_manifest_rejects_unreviewed_scope_names_images_or_brand_claims(attack):
    value = manifest()
    if attack in {"project", "region", "origin"}:
        value[attack] = "unreviewed"
    elif attack == "schema":
        value["schema"]["to"] = "td0012"
    elif attack == "baseline":
        value["baseline"]["api_image"] = value["images"]["images"]["api"]["reference"]
    elif attack == "cost":
        value["cost_sha256"] = "0" * 64
    elif attack == "tag":
        value["candidate"]["api_url"] = "https://external.invalid"
    elif attack == "image":
        value["images"]["images"]["api"]["reference"] = "api:latest"
    elif attack == "same_source":
        value["images"] = previous()["images"]
    else:
        value["raw_payload"] = "synthetic-untrusted"
    with pytest.raises(hotfix.PlanBlocked):
        hotfix.validate_manifest(value)


@pytest.mark.parametrize("phase", hotfix.PHASES)
@pytest.mark.parametrize(
    "attack",
    [
        "quota",
        "secret",
        "audience",
        "cookie",
        "command",
        "traffic",
        "prior_traffic",
        "prior_origin",
        "extra_env",
    ],
)
def test_service_policy_rejects_hidden_mutations_and_wrong_start_state(phase, attack):
    value = plan(phase)
    api, web = change(value, "api"), change(value, "web")
    container = api["after"]["template"][0]["containers"][0]
    env = {item["name"]: item for item in container["env"]}
    if attack == "quota":
        env["TASTEDUEL_QLOO_REQUESTS_PER_DAY"]["value"] = "1000"
    elif attack == "secret":
        env["TASTEDUEL_QLOO_SECRET_VERSION"]["value"] = "synthetic-private-value"
    elif attack == "cookie":
        env["TASTEDUEL_COOKIE_SECURE"]["value"] = "false"
    elif attack == "audience":
        next(
            item
            for item in web["after"]["template"][0]["containers"][0]["env"]
            if item["name"] == "TASTEDUEL_API_AUDIENCE"
        )["value"] = manifest()["candidate"]["api_url"]
    elif attack == "command":
        container["command"] = ["sh", "-c", "synthetic-untrusted"]
    elif attack == "traffic":
        api["after"]["traffic"][0]["percent"] = 50
    elif attack == "prior_traffic":
        api["before"]["traffic"][0]["revision"] = "tasteduel-api-unreviewed"
    elif attack == "prior_origin":
        next(
            item
            for item in api["before"]["template"][0]["containers"][0]["env"]
            if item["name"] == "TASTEDUEL_ALLOWED_ORIGINS"
        )["value"] = '["https://unreviewed.invalid"]'
    else:
        container["env"].append({"name": "ANSWER_KEY", "value": "synthetic-answer"})
    result = hotfix.audit_plan(value, manifest(), phase)
    assert result["status"] == "BLOCKED"
    assert "synthetic-private-value" not in json.dumps(result)


@pytest.mark.parametrize("operation", [["create"], ["delete"], ["update"], ["delete", "create"]])
def test_no_sql_iam_job_monitoring_or_extra_resource_mutation(operation):
    for address in (
        hotfix.ADDRESSES["migrate"],
        hotfix.PUBLIC_WEB,
        next(iter(hotfix.MONITORS)),
        "google_sql_database.unrelated",
    ):
        value = plan()
        if address == "google_sql_database.unrelated":
            value["resource_changes"].append(
                {"address": address, "change": {"actions": operation, "before": {}, "after": {}}}
            )
        else:
            change(value, address)["actions"] = operation
        assert hotfix.audit_plan(value, manifest(), "hotfix-candidate")["status"] == "BLOCKED"


def test_noop_label_cannot_hide_changed_protected_resources_or_public_api_binding():
    value = plan()
    change(value, hotfix.PUBLIC_WEB)["after"]["member"] = "allAuthenticatedUsers"
    assert hotfix.audit_plan(value, manifest(), "hotfix-candidate")["status"] == "BLOCKED"
    value = plan()
    change(value, hotfix.ADDRESSES["api_web"])["after"]["member"] = "allUsers"
    assert hotfix.audit_plan(value, manifest(), "hotfix-candidate")["status"] == "BLOCKED"
    value = plan()
    resource = {
        "project": hotfix.PROJECT,
        "location": hotfix.REGION,
        "name": "tasteduel-api",
        "role": "roles/run.invoker",
        "member": "allUsers",
    }
    value["resource_changes"].append(
        {
            "address": "synthetic_public_api",
            "change": {"actions": ["no-op"], "before": resource, "after": resource},
        }
    )
    assert hotfix.audit_plan(value, manifest(), "hotfix-candidate")["status"] == "BLOCKED"


def evidence():
    record = manifest()
    return {
        "kind": "hotfix-candidate-smoke",
        "status": "PASS",
        "manifest_sha256": hotfix.digest(record),
        "source_sha": record["images"]["source_sha"],
        "api_revision": record["candidate"]["api_revision"],
        "web_revision": record["candidate"]["web_revision"],
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "verification": {
            "original_incident_cause": "unconfirmed",
            "error_scenarios": "synthetic-contracts",
            "live_generation": "genuine-agent",
        },
        "checks": {
            key: True
            for key in (
                "synthetic_error_contracts",
                "retry_identity",
                "private_api",
                "secrecy",
                "keyboard",
                "mobile",
                "candidate_config",
            )
        },
    }


@pytest.mark.parametrize(
    "attack",
    [
        "synthetic_live",
        "unknown_root_cause_claim",
        "false",
        "string_true",
        "stale",
        "future",
        "wrong_revision",
        "extra",
    ],
)
def test_smoke_cannot_conflate_synthetic_contracts_with_live_or_claim_incident_root_cause(attack):
    value = evidence()
    if attack == "synthetic_live":
        value["verification"]["live_generation"] = "not-rechecked"
    elif attack == "unknown_root_cause_claim":
        value["verification"]["original_incident_cause"] = "proven-fixed"
    elif attack == "false":
        value["checks"]["private_api"] = False
    elif attack == "string_true":
        value["checks"]["private_api"] = "true"
    elif attack == "stale":
        value["checked_at_utc"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    elif attack == "future":
        value["checked_at_utc"] = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    elif attack == "wrong_revision":
        value["web_revision"] = manifest()["baseline"]["web_revision"]
    else:
        value["raw_payload"] = "synthetic-private"
    with pytest.raises(hotfix.PlanBlocked):
        hotfix.check_evidence(value, manifest())


@pytest.mark.parametrize("mode", ["genuine-agent", "deterministic-qloo"])
def test_truthful_live_mode_is_kept_distinct_from_synthetic_error_checks(mode):
    value = evidence()
    value["verification"]["live_generation"] = mode
    assert hotfix.check_evidence(value, manifest()) is None


def saved(tmp_path, monkeypatch):
    monkeypatch.setattr(hotfix, "ROOT", tmp_path)
    source = tmp_path / "infra/terraform"
    source.mkdir(parents=True)
    (source / "main.tf").write_text("# synthetic source\n")
    (source / ".terraform.lock.hcl").write_text("# synthetic lock\n")
    directory = tmp_path / ".data/tasteduel-cloud-review/release-hotfix-candidate-plan-synthetic"
    directory.mkdir(parents=True)
    for name in ("main.tf", ".terraform.lock.hcl"):
        (directory / name).write_bytes((source / name).read_bytes())
    (directory / "release.tfplan").write_bytes(b"synthetic-private-plan")
    review = {
        "status": "REVIEWABLE",
        "phase": "hotfix-candidate",
        "source_sha256": hotfix.source_hash(source),
        "plan_sha256": hashlib.sha256((directory / "release.tfplan").read_bytes()).hexdigest(),
        "image_source_sha": manifest()["images"]["source_sha"],
        "manifest_sha256": hotfix.digest(manifest()),
        "reviewed_total_usd": 88.15,
    }
    approval = {**review, "independent_review": "PASS"}
    monkeypatch.setattr(
        hotfix.foundation,
        "approved_variables",
        lambda _: {"project_id": hotfix.PROJECT, "reviewed_total_usd": 88.15},
    )
    return directory, review, approval


@pytest.mark.parametrize(
    "attack",
    ["approval", "binary", "current_source", "copied_source", "journal", "manifest", "cost", "images"],
)
def test_saved_apply_guards_reject_changed_review_inputs_before_any_credentials(
    tmp_path, monkeypatch, attack
):
    directory, review, approval = saved(tmp_path, monkeypatch)
    record, prices, images = manifest(), cost(), manifest()["images"]
    if attack == "approval":
        approval["plan_sha256"] = "0" * 64
    elif attack == "binary":
        (directory / "release.tfplan").write_bytes(b"changed")
    elif attack == "current_source":
        (tmp_path / "infra/terraform/main.tf").write_text("# changed")
    elif attack == "copied_source":
        (directory / "main.tf").write_text("# changed")
    elif attack == "journal":
        (directory / "apply-journal.json").write_text("{}")
    elif attack == "manifest":
        record["preview_exposure"] = "zero-percent-is-private"
    elif attack == "cost":
        prices["reviewed_total_usd"] = 89
    else:
        images["source_sha"] = images["ci"]["head_sha"] = "1" * 40
    with pytest.raises(hotfix.PlanBlocked):
        hotfix.verify_saved(directory, review, approval, prices, record, images, fixtures.TESTER)


def test_saved_valid_review_is_local_and_does_not_create_apply_journal(tmp_path, monkeypatch):
    directory, review, approval = saved(tmp_path, monkeypatch)
    variables = hotfix.verify_saved(
        directory, review, approval, cost(), manifest(), manifest()["images"], fixtures.TESTER
    )
    assert variables["tasteduel_public_enabled"] and variables["tasteduel_observability_enabled"]
    assert not (directory / "apply-journal.json").exists()
    with pytest.raises(hotfix.PlanBlocked):
        hotfix.verify_plan_inputs({"variables": {}}, variables)


def test_apply_cli_reaudits_exact_binary_and_failed_apply_is_one_shot_with_sanitized_output(
    tmp_path, monkeypatch, capsys
):
    directory, review, approval = saved(tmp_path, monkeypatch)
    inputs = hotfix.reviewed_inputs(
        cost(), manifest(), manifest()["images"], "hotfix-candidate", fixtures.TESTER
    )
    proposed = plan()
    proposed["variables"] = {key: {"value": value} for key, value in inputs.items()}
    for name, value in (
        ("review.json", review),
        ("independent-approval.json", approval),
        ("hotfix-manifest.json", manifest()),
        ("cost.json", cost()),
        ("images.json", manifest()["images"]),
    ):
        (directory / name).write_text(json.dumps(value))
    calls = []
    monkeypatch.setattr(hotfix.foundation, "adc_path", lambda: Path("synthetic-adc"))
    monkeypatch.setattr(hotfix.foundation, "terraform", lambda *args: json.dumps(proposed))
    monkeypatch.setattr(hotfix, "credential_environment", lambda _: {"TF_VAR_SYNTHETIC": "PRIVATE_TEST_ONLY"})

    def run(command, **kwargs):
        calls.append(command)
        assert command[-1] == "release.tfplan" and "apply" in command
        assert not any(item.startswith(("-target", "-destroy", "-replace")) for item in command)
        return SimpleNamespace(returncode=1, stdout="PRIVATE_PROVIDER_DIAGNOSTIC", stderr="PRIVATE_TEST_ONLY")

    monkeypatch.setattr(hotfix.subprocess, "run", run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hotfix",
            "apply",
            "--directory",
            str(directory),
            "--review",
            str(directory / "cost.json"),
            "--images",
            str(directory / "images.json"),
            "--manifest",
            str(directory / "hotfix-manifest.json"),
            "--tester",
            fixtures.TESTER,
        ],
    )
    assert hotfix.main() == 2
    journal = json.loads((directory / "apply-journal.json").read_text())
    assert journal["status"] == "FAILED_REQUIRES_RECOVERY" and journal["automatic_retry"] is False
    assert hotfix.main() == 2 and len(calls) == 1
    assert "PRIVATE_" not in capsys.readouterr().out


def test_project_wide_public_run_invocation_is_not_a_private_api_boundary():
    proposed = plan()
    payload = {"project": hotfix.PROJECT, "role": "roles/run.invoker", "member": "allUsers"}
    proposed["resource_changes"].append(
        {
            "address": "google_project_iam_member.synthetic_public_run",
            "change": {"actions": ["no-op"], "before": payload, "after": payload},
        }
    )
    assert hotfix.audit_plan(proposed, manifest(), "hotfix-candidate")["status"] == "BLOCKED"


def test_nullable_saved_input_must_be_present_not_silently_missing():
    with pytest.raises(hotfix.PlanBlocked):
        hotfix.verify_plan_inputs({"variables": {}}, {"tasteduel_candidate_tag": None})
    hotfix.verify_plan_inputs(
        {"variables": {"tasteduel_candidate_tag": {"value": None}}}, {"tasteduel_candidate_tag": None}
    )


def test_plan_cli_saves_only_reviewed_metadata_without_running_apply(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(hotfix, "ROOT", tmp_path)
    monkeypatch.setattr(
        hotfix.foundation,
        "approved_variables",
        lambda _: {"project_id": hotfix.PROJECT, "reviewed_total_usd": 88.15},
    )
    inputs = hotfix.reviewed_inputs(
        cost(), manifest(), manifest()["images"], "hotfix-candidate", fixtures.TESTER
    )
    proposed = plan()
    proposed["variables"] = {key: {"value": value} for key, value in inputs.items()}
    for name, payload in (
        ("cost.json", cost()),
        ("images.json", manifest()["images"]),
        ("manifest.json", manifest()),
    ):
        (tmp_path / name).write_text(json.dumps(payload))
    stages = []

    def snapshot(directory):
        assert directory.parent == tmp_path / ".data/tasteduel-cloud-review"
        directory.mkdir(parents=True, exist_ok=False)
        return "0" * 64

    def terraform(directory, adc, env, *arguments):
        stages.append(arguments[0])
        assert arguments[0] in {"init", "plan", "show"}
        assert not any(value.startswith(("-target", "-destroy", "-replace")) for value in arguments)
        if arguments[0] == "plan":
            (directory / "release.tfplan").write_bytes(b"synthetic-plan")
        return json.dumps(proposed) if arguments[0] == "show" else ""

    monkeypatch.setattr(hotfix.foundation, "source_snapshot", snapshot)
    monkeypatch.setattr(hotfix.foundation, "adc_path", lambda: Path("synthetic-adc"))
    monkeypatch.setattr(hotfix.foundation, "terraform", terraform)
    monkeypatch.setattr(hotfix, "credential_environment", lambda _: {"TF_VAR_SYNTHETIC": "PRIVATE_TEST_ONLY"})
    monkeypatch.setattr(
        hotfix.subprocess, "run", lambda *args, **kwargs: pytest.fail("No actual subprocess is permitted")
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hotfix",
            "plan",
            "--phase",
            "hotfix-candidate",
            "--review",
            str(tmp_path / "cost.json"),
            "--images",
            str(tmp_path / "images.json"),
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--tester",
            fixtures.TESTER,
        ],
    )
    assert hotfix.main() == 0 and stages == ["init", "plan", "show"]
    result = json.loads(capsys.readouterr().out)
    review_path = Path(result["review"])
    assert json.loads(review_path.read_text())["status"] == "REVIEWABLE" and result["applied"] is False
    assert not (review_path.parent / "apply-journal.json").exists()
    assert all("PRIVATE_TEST_ONLY" not in item.read_text() for item in review_path.parent.glob("*.json"))

"""Synthetic-only foundation planning security contracts; no cloud credentials."""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("foundation_plan", ROOT / "scripts/tasteduel_foundation_plan.py")
planner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planner)


def review():
    now = datetime.now(timezone.utc)
    return {"cost_gate_status": "PASS", "billing_reconciled": True, "cost_review_passed": True,
            "reviewed_total_usd": 70, "reviewed_through_utc": max(now + timedelta(days=15), planner.MINIMUM_HORIZON).isoformat(),
            "billing_account": "AAAAAA-BBBBBB-CCCCCC", "budget_currency": "INR", "budget_alert_units": 6000,
            "migration_alert_units": 6000, "accrued_cost_evidence": "synthetic-review-only",
            "approved_at_utc": now.isoformat()}


@pytest.mark.parametrize("patch", [
    {"cost_gate_status": "BLOCKED"}, {"billing_reconciled": False}, {"cost_review_passed": False},
    {"reviewed_total_usd": 91}, {"reviewed_total_usd": float("nan")}, {"reviewed_total_usd": True},
    {"accrued_cost_evidence": ""}, {"budget_currency": "USD"}, {"budget_alert_units": 0},
    {"reviewed_through_utc": "2026-11-06T04:45:00Z"}, {"approved_at_utc": "2026-01-01T00:00:00Z"},
    {"database_password": "not-an-approved-review-field"},
])
def test_review_fails_closed_before_any_secret_or_cloud_access(patch):
    with pytest.raises(planner.PlanBlocked):
        planner.approved_variables({**review(), **patch})


@pytest.mark.parametrize("total", [82.84, 90])
def test_explicitly_authorized_ceiling_accepts_reviewed_total_without_changing_backup_policy(total):
    variables = planner.approved_variables({**review(), "reviewed_total_usd": total})
    assert variables["budget_usd"] == 90
    assert variables["reviewed_total_usd"] == total
    assert "backup_retention_settings" not in variables


def change(address, actions, before=None, after=None):
    return {"address": address, "change": {"actions": actions, "before": before or {}, "after": after or {}}}


@pytest.mark.parametrize("address,actions", [
    ("google_sql_database.app", ["delete"]), ("google_sql_user.app", ["update"]),
    ("google_secret_manager_secret_version.database", ["update"]),
    ("google_sql_database_instance.db", ["delete", "create"]),
    ("google_cloud_run_v2_service.web", ["create"]),
    ("module.tasteduel_foundation[0].google_service_account.unreviewed_admin", ["create"]),
    ("google_project_iam_member.unreviewed_owner", ["create"]),
    ("google_billing_budget.accesslife", ["update"]),
])
def test_unapproved_mutation_or_runtime_recreation_is_blocked(address, actions):
    result = planner.audit_plan({"resource_changes": [change(address, actions)]})
    assert result["status"] == "BLOCKED"


def test_exact_foundation_create_and_retired_forget_only_are_reviewable():
    changes = [change(address, ["create"], after={"role": planner.EXPECTED_IAM_ROLES[address]}
                      if address in planner.EXPECTED_IAM_ROLES else {}) for address in planner.FOUNDATION_ADDRESSES]
    for resource in changes:
        if resource["address"].endswith("google_project_iam_custom_role.vertex_predict"):
            resource["change"]["after"] = {"role_id": "tasteduelVertexPredictor", "project": planner.PROJECT,
                                           "permissions": ["aiplatform.endpoints.predict", "serviceusage.services.use"]}
    changes += [change(address, ["forget"]) for address in planner.FORGET]
    result = planner.audit_plan({"resource_changes": changes})
    assert result["status"] == "REVIEWABLE"
    assert result["requires_independent_review"] is True


def test_known_iam_address_cannot_grant_owner_and_wif_cannot_trust_whole_owner():
    address = next(iter(planner.EXPECTED_IAM_ROLES))
    assert planner.audit_plan({"resource_changes": [change(address, ["create"], after={"role": "roles/owner"})]})["status"] == "BLOCKED"
    address = "google_iam_workload_identity_pool_provider.github"
    unsafe = {"attribute_condition": "assertion.repository_owner_id == '60200140'"}
    assert planner.audit_plan({"resource_changes": [change(address, ["update"], after=unsafe)]})["status"] == "BLOCKED"


def test_custom_vertex_role_cannot_grow_permissions():
    address = planner.FOUNDATION + "google_project_iam_custom_role.vertex_predict"
    after = {"role_id": "tasteduelVertexPredictor", "project": planner.PROJECT,
             "permissions": ["aiplatform.endpoints.predict", "serviceusage.services.use", "aiplatform.models.delete"]}
    assert planner.audit_plan({"resource_changes": [change(address, ["create"], after=after)]})["status"] == "BLOCKED"


def test_unknown_vertex_role_is_accepted_only_for_exact_custom_role_reference():
    resource = change(planner.FOUNDATION + "google_project_iam_member.vertex", ["create"])
    resource["change"]["after_unknown"] = {"role": True}
    plan = {"resource_changes": [resource], "configuration": {"root_module": {"module_calls": {
        "tasteduel_foundation": {"module": {"resources": [{"address": "google_project_iam_member.vertex",
            "expressions": {"role": {"references": ["google_project_iam_custom_role.vertex_predict.name", "google_project_iam_custom_role.vertex_predict"]}}}]}}
    }}}}
    assert planner.audit_plan(plan)["status"] == "REVIEWABLE"
    plan["configuration"]["root_module"]["module_calls"]["tasteduel_foundation"]["module"]["resources"][0]["expressions"]["role"]["references"].append("google_project_iam_custom_role.admin.name")
    assert planner.audit_plan(plan)["status"] == "BLOCKED"


def test_sql_labels_can_update_but_tier_or_backup_drift_is_blocked():
    before = {"settings": [{"tier": "db-custom-1-3840", "user_labels": {"app": "accesslife"}}]}
    after = {"settings": [{"tier": "db-custom-1-3840", "user_labels": {"app": "accesslife", "cost_scope": "qloo-hackathon"}}]}
    assert planner.audit_plan({"resource_changes": [change("google_sql_database_instance.db", ["update"], before, after)]})["status"] == "REVIEWABLE"
    after["settings"][0]["tier"] = "db-custom-8-32768"
    assert planner.audit_plan({"resource_changes": [change("google_sql_database_instance.db", ["update"], before, after)]})["status"] == "BLOCKED"


def test_legacy_alert_window_can_extend_without_changing_historical_amount_or_scope():
    before = {"budget_filter": [{"labels": {"app": "accesslife"}, "custom_period": [{
        "start_date": [{"year": 2026, "month": 10, "day": 24}],
        "end_date": [{"year": 2026, "month": 10, "day": 31}],
    }]}], "amount": [{"specified_amount": [{"currency_code": "INR", "units": "6507", "nanos": 0}]}]}
    after = json.loads(json.dumps(before))
    after["budget_filter"][0]["custom_period"][0]["end_date"] = [{"year": 2026, "month": 11, "day": 8}]
    address = "google_billing_budget.accesslife"
    assert planner.audit_plan({"resource_changes": [change(address, ["update"], before, after)]})["status"] == "REVIEWABLE"
    after["amount"][0]["specified_amount"][0]["units"] = "6972"
    assert planner.audit_plan({"resource_changes": [change(address, ["update"], before, after)]})["status"] == "BLOCKED"
    after = json.loads(json.dumps(before))
    after["budget_filter"][0]["custom_period"][0]["end_date"] = [{"year": 2026, "month": 11, "day": 8}]
    after["budget_filter"][0]["labels"] = {"app": "unrelated"}
    assert planner.audit_plan({"resource_changes": [change(address, ["update"], before, after)]})["status"] == "BLOCKED"


def test_legacy_secret_label_update_does_not_allow_payload_or_replication_change():
    address = "google_secret_manager_secret.database"
    before = {"labels": {"app": "accesslife"}, "replication": [{"auto": [{}]}]}
    after = {**before, "labels": {"app": "accesslife", "cost_scope": "qloo-hackathon"}}
    assert planner.audit_plan({"resource_changes": [change(address, ["update"], before, after)]})["status"] == "REVIEWABLE"
    after["replication"] = [{"user_managed": []}]
    assert planner.audit_plan({"resource_changes": [change(address, ["update"], before, after)]})["status"] == "BLOCKED"


def test_new_alert_display_can_match_approved_ceiling_without_changing_amount_or_scope():
    address = "google_billing_budget.tasteduel_migration"
    before = {"display_name": "Qloo migration cumulative USD80 alerts",
              "amount": [{"specified_amount": [{"currency_code": "INR", "units": "6972"}]}],
              "budget_filter": [{"labels": {"cost_scope": "qloo-hackathon"}}]}
    after = {**before, "display_name": "Qloo migration cumulative USD90 alerts"}
    assert planner.audit_plan({"resource_changes": [change(address, ["update"], before, after)]})["status"] == "REVIEWABLE"
    after = {**after, "amount": [{"specified_amount": [{"currency_code": "INR", "units": "9000"}]}]}
    assert planner.audit_plan({"resource_changes": [change(address, ["update"], before, after)]})["status"] == "BLOCKED"
    after = {**before, "display_name": "Qloo migration cumulative USD900 alerts"}
    assert planner.audit_plan({"resource_changes": [change(address, ["update"], before, after)]})["status"] == "BLOCKED"


def test_private_values_never_reach_redacted_review():
    marker = "SYNTHETIC_PRIVATE_ATTRIBUTE"
    result = planner.audit_plan({"resource_changes": [change(
        "google_secret_manager_secret_version.database", ["update"], {"secret_data": marker}, {"secret_data": marker + "changed"},
    )]})
    assert marker not in json.dumps(result)
    assert "secret_data" not in json.dumps(result)


def test_sensitive_environment_uses_distinct_generated_values_and_keeps_legacy_unchanged():
    environment = planner.ephemeral_environment(planner.approved_variables(review()), "synthetic-existing-credential")
    assert environment["TF_VAR_database_password"] == "synthetic-existing-credential"
    assert len(environment["TF_VAR_tasteduel_runtime_password"]) >= 32
    assert environment["TF_VAR_tasteduel_runtime_password"] != environment["TF_VAR_tasteduel_migration_password"]


def test_container_receives_environment_names_not_payloads(monkeypatch, tmp_path):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(planner.subprocess, "run", run)
    marker = "SYNTHETIC_DO_NOT_PUT_IN_ARGV"
    planner.terraform(tmp_path, tmp_path / "adc.json", {"TF_VAR_database_password": marker}, "show", "-json", "foundation.tfplan")
    command, options = calls[0]
    assert marker not in json.dumps(command)
    assert options["env"]["TF_VAR_database_password"] == marker
    assert "readonly" in " ".join(command)
    assert options["capture_output"] is True


@pytest.mark.parametrize("args", [("apply",), ("destroy",), ("plan", "-target=x"), ("plan", "-destroy"), ("plan", "-replace=x")])
def test_executor_cannot_apply_or_hide_scope(monkeypatch, tmp_path, args):
    def fail(*unused, **kwargs):
        pytest.fail("must reject before process invocation")
    monkeypatch.setattr(planner.subprocess, "run", fail)
    with pytest.raises(planner.PlanBlocked):
        planner.terraform(tmp_path, tmp_path / "adc.json", {}, *args)

"""Create and audit a full-root foundation plan; never apply infrastructure.

The caller supplies a nonsecret approved cost record. ADC and the retained legacy
password are used only on explicit execution; payloads remain in memory. Terraform
receives ephemeral values by environment names, not arguments or payload files.
The private binary plan is sensitive state, not a publishable artifact.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "project-bb13ecd8-9d67-408d-9a7"
REGION = "asia-south1"
IMAGE = "hashicorp/terraform:1.13.3"
BACKEND_BUCKET = "accesslife-tfstate-" + PROJECT
BACKEND_PREFIX = "accesslife/state"
FOUNDATION = "module.tasteduel_foundation[0]."
LEGACY_PASSWORD = f"projects/{PROJECT}/secrets/accesslife-db-password/versions/1"
MINIMUM_HORIZON = datetime(2026, 11, 7, 4, 45, tzinfo=timezone.utc)

FORGET = frozenset({
    'google_cloud_run_v2_service.backend["api"]',
    "google_cloud_run_v2_service.worker", "google_cloud_run_v2_service.web",
    "google_cloud_tasks_queue.planning", "google_cloud_scheduler_job.reconcile",
    *[f'google_cloud_run_v2_job.maintenance["{name}"]' for name in ("migrate", "ingest", "reconcile")],
    *[f"google_cloud_run_v2_service_iam_member.{name}" for name in ("api", "worker", "public_web")],
    "google_cloud_run_v2_job_iam_member.scheduler",
    *[f'google_cloud_run_v2_service_iam_member.deploy_run["{name}"]' for name in ("api", "worker", "web")],
    *[f'google_cloud_run_v2_job_iam_member.deploy_jobs["{name}"]' for name in ("migrate", "ingest", "reconcile")],
})
FOUNDATION_ADDRESSES = frozenset(FOUNDATION + suffix for suffix in {
    *[f'google_service_account.app["{actor}"]' for actor in ("web", "api", "migrate", "deploy")],
    "google_sql_database.app",
    *[f'google_sql_user.app["{actor}"]' for actor in ("runtime", "migrate")],
    *[f'google_secret_manager_secret.database["{actor}"]' for actor in ("runtime", "migrate")],
    *[f'google_secret_manager_secret_version.database["{actor}"]' for actor in ("runtime", "migrate")],
    *[f'google_secret_manager_secret_iam_member.database["{actor}"]' for actor in ("runtime", "migrate")],
    "google_secret_manager_secret_iam_member.qloo",
    *[f'google_project_iam_member.sql["{actor}"]' for actor in ("api", "migrate")],
    "google_project_iam_member.vertex", "google_artifact_registry_repository_iam_member.deploy",
    "google_project_iam_custom_role.vertex_predict",
    *[f'google_service_account_iam_member.deploy_act_as["{actor}"]' for actor in ("web", "api", "migrate")],
})
LABEL_FIELDS = frozenset({"labels", "terraform_labels", "effective_labels"})
UPDATES = {
    "google_artifact_registry_repository.images": LABEL_FIELDS,
    'google_storage_bucket.private["docs"]': LABEL_FIELDS,
    'google_storage_bucket.private["backups"]': LABEL_FIELDS,
    "google_secret_manager_secret.database": LABEL_FIELDS,
    "google_billing_budget.accesslife": frozenset({"budget_filter"}),
    "google_billing_budget.tasteduel_migration": frozenset({"display_name"}),
    "google_sql_database_instance.db": frozenset({"settings"}),
    "google_iam_workload_identity_pool_provider.github": frozenset({"attribute_mapping", "attribute_condition"}),
}
REVIEW_KEYS = frozenset({
    "cost_gate_status", "billing_reconciled", "cost_review_passed", "reviewed_total_usd",
    "reviewed_through_utc", "billing_account", "budget_currency", "budget_alert_units",
    "migration_alert_units", "accrued_cost_evidence", "approved_at_utc",
})
EXPECTED_IAM_ROLES = {
    **{FOUNDATION + f'google_secret_manager_secret_iam_member.database["{actor}"]': "roles/secretmanager.secretAccessor"
       for actor in ("runtime", "migrate")},
    FOUNDATION + "google_secret_manager_secret_iam_member.qloo": "roles/secretmanager.secretAccessor",
    **{FOUNDATION + f'google_project_iam_member.sql["{actor}"]': "roles/cloudsql.client" for actor in ("api", "migrate")},
    FOUNDATION + "google_project_iam_member.vertex": f"projects/{PROJECT}/roles/tasteduelVertexPredictor",
    FOUNDATION + "google_artifact_registry_repository_iam_member.deploy": "roles/artifactregistry.writer",
    **{FOUNDATION + f'google_service_account_iam_member.deploy_act_as["{actor}"]': "roles/iam.serviceAccountUser"
       for actor in ("web", "api", "migrate")},
    "google_service_account_iam_member.tasteduel_github[0]": "roles/iam.workloadIdentityUser",
}
EXPECTED_WIF_CONDITION = (
    "assertion.repository_id == '1431472864' && assertion.repository_owner_id == '60200140' "
    "&& assertion.ref == 'refs/heads/main' && assertion.environment == 'foundation-review'"
)


class PlanBlocked(Exception):
    """Only static reason codes are allowed in operator-visible errors."""


def approved_variables(review: dict) -> dict:
    if set(review) not in (REVIEW_KEYS, REVIEW_KEYS | {"approved_budget_usd"}):
        raise PlanBlocked("COST_REVIEW_FIELDS_INVALID")
    ceiling = review.get("approved_budget_usd", 90)
    if type(ceiling) is not int or ceiling not in {90, 100}:
        raise PlanBlocked("APPROVED_COST_CEILING_INVALID")
    if (review["cost_gate_status"] != "PASS" or review["billing_reconciled"] is not True
            or review["cost_review_passed"] is not True):
        raise PlanBlocked("CUMULATIVE_COST_GATE_NOT_PASSED")
    total = review["reviewed_total_usd"]
    if isinstance(total, bool) or not isinstance(total, (float, int)) or not 0 <= total <= ceiling:
        raise PlanBlocked("CUMULATIVE_TOTAL_INVALID")
    try:
        horizon = datetime.fromisoformat(review["reviewed_through_utc"].replace("Z", "+00:00"))
        approved = datetime.fromisoformat(review["approved_at_utc"].replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        raise PlanBlocked("COST_REVIEW_TIMESTAMPS_INVALID") from None
    now = datetime.now(timezone.utc)
    if horizon.tzinfo is None or horizon < MINIMUM_HORIZON or horizon <= now:
        raise PlanBlocked("COST_HORIZON_INVALID")
    # Release work can span two calendar days while immutable images, a live
    # candidate and saved plans are independently checked. The reviewed cost
    # horizon and absolute ceiling still fail closed independently.
    if approved.tzinfo is None or approved > now or (now - approved).total_seconds() > 172800:
        raise PlanBlocked("COST_APPROVAL_STALE")
    if not isinstance(review["accrued_cost_evidence"], str) or not review["accrued_cost_evidence"].strip():
        raise PlanBlocked("ACCRUED_COST_EVIDENCE_REQUIRED")
    if not re.fullmatch(r"[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}", review["billing_account"]):
        raise PlanBlocked("BILLING_ACCOUNT_INVALID")
    if review["budget_currency"] != "INR":
        raise PlanBlocked("UNREVIEWED_CURRENCY")
    for field in ("budget_alert_units", "migration_alert_units"):
        if type(review[field]) is not int or review[field] <= 0:
            raise PlanBlocked("ALERT_AMOUNT_INVALID")
    registry = f"{REGION}-docker.pkg.dev/{PROJECT}/accesslife"
    return {
        **{key: review[key] for key in ("billing_reconciled", "cost_review_passed", "reviewed_total_usd",
                                      "reviewed_through_utc", "billing_account", "budget_currency",
                                      "budget_alert_units", "migration_alert_units")},
        "project_id": PROJECT, "region": REGION, "budget_usd": ceiling,
        "tasteduel_foundation_enabled": True, "tasteduel_credential_version": 1,
        # Required historical variables remain real recorded rollback references;
        # retired source contains no runtime resources consuming these values.
        "web_image": registry + "/web@sha256:4fd3995f835d59ed0801d94ae8bdec2707953774f84880754442da2930b10346",
        "api_image": registry + "/api@sha256:fe4be430367838a54b6f397351c3f9381c922a15ec65a8b9b597c381ae533474",
        "public_url": "https://accesslife-web-dfthmgvvaa-el.a.run.app",
    }


def changed_keys(before: dict | None, after: dict | None) -> set[str]:
    before, after = before or {}, after or {}
    return {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}


def exact_vertex_role_reference(plan: dict, change: dict) -> bool:
    if change.get("after_unknown", {}).get("role") is not True:
        return False
    resources = (plan.get("configuration", {}).get("root_module", {}).get("module_calls", {})
                 .get("tasteduel_foundation", {}).get("module", {}).get("resources", []))
    for resource in resources:
        if resource.get("address") == "google_project_iam_member.vertex":
            references = set(resource.get("expressions", {}).get("role", {}).get("references", []))
            return "google_project_iam_custom_role.vertex_predict.name" in references and references <= {
                "google_project_iam_custom_role.vertex_predict.name", "google_project_iam_custom_role.vertex_predict",
            }
    return False


def exact_legacy_alert_extension(before: dict, after: dict) -> bool:
    """Only extend the existing alert period; amount/labels/credits stay intact."""
    old_filters, new_filters = before.get("budget_filter", []), after.get("budget_filter", [])
    if len(old_filters) != 1 or len(new_filters) != 1:
        return False
    old_filter, new_filter = old_filters[0], new_filters[0]
    if changed_keys(old_filter, new_filter) - {"custom_period"}:
        return False
    old_periods, new_periods = old_filter.get("custom_period", []), new_filter.get("custom_period", [])
    if len(old_periods) != 1 or len(new_periods) != 1:
        return False
    if changed_keys(old_periods[0], new_periods[0]) - {"end_date"}:
        return False
    if new_periods[0].get("end_date") != [{"year": 2026, "month": 11, "day": 8}]:
        return False
    amount = after.get("amount", [])
    if len(amount) != 1:
        return False
    specified = amount[0].get("specified_amount", [])
    return (len(specified) == 1 and str(specified[0].get("units")) == "6507"
            and specified[0].get("currency_code") == "INR" and specified[0].get("nanos", 0) == 0)


def audit_plan(plan: dict) -> dict:
    """Inspect captured JSON in memory; return no attributes or provider payloads."""
    failures, actions = [], []
    for resource in plan.get("resource_changes", []):
        address = resource.get("address", "")
        change = resource.get("change", {})
        operation = change.get("actions", [])
        before, after = change.get("before") or {}, change.get("after") or {}
        # Addresses/type names come from reviewed source, never object field text.
        if operation in (["no-op"], ["read"]):
            continue
        permitted = False
        if operation == ["forget"] and address in FORGET:
            permitted = True
        elif operation == ["create"]:
            permitted = address in FOUNDATION_ADDRESSES
            permitted |= address == "google_service_account_iam_member.tasteduel_github[0]"
            permitted |= address == "google_billing_budget.tasteduel_migration"
            permitted |= address == "terraform_data.cost_gate"
            if address in EXPECTED_IAM_ROLES:
                role_matches = after.get("role") == EXPECTED_IAM_ROLES[address]
                if address == FOUNDATION + "google_project_iam_member.vertex":
                    role_matches |= exact_vertex_role_reference(plan, change)
                permitted &= role_matches
            if address == FOUNDATION + "google_project_iam_custom_role.vertex_predict":
                permitted &= (after.get("role_id") == "tasteduelVertexPredictor"
                              and after.get("project") == PROJECT
                              and set(after.get("permissions", [])) == {"aiplatform.endpoints.predict", "serviceusage.services.use"})
        elif operation == ["update"]:
            keys = changed_keys(before, after)
            permitted = address in UPDATES and keys <= UPDATES[address]
            if address == "google_sql_database_instance.db" and permitted:
                old, new = before.get("settings", []), after.get("settings", [])
                permitted = len(old) == len(new) == 1 and changed_keys(old[0], new[0]) <= {"user_labels"}
            if address == "google_billing_budget.accesslife" and permitted:
                permitted = exact_legacy_alert_extension(before, after)
            if address == "google_billing_budget.tasteduel_migration" and permitted:
                permitted = after.get("display_name") == "Qloo migration cumulative USD90 alerts"
            if address == "google_iam_workload_identity_pool_provider.github" and permitted:
                permitted = after.get("attribute_condition") == EXPECTED_WIF_CONDITION
                permitted &= after.get("attribute_mapping", {}).get("attribute.repository_id") == "assertion.repository_id"
                permitted &= after.get("attribute_mapping", {}).get("attribute.repository_owner_id") == "assertion.repository_owner_id"
            # Existing label scope only; no changed tier, disk, network, backups,
            # deletion protection, legacy credentials or privileged memberships.
        if not permitted:
            failures.append("UNAPPROVED_RESOURCE_ACTION")
        if address in FORGET or address in UPDATES or address in FOUNDATION_ADDRESSES or address in {
            "google_service_account_iam_member.tasteduel_github[0]", "google_billing_budget.tasteduel_migration",
            "terraform_data.cost_gate",
        }:
            actions.append({"address": address, "actions": operation, "approved_scope": bool(permitted)})
        elif operation != ["no-op"]:
            actions.append({"address": "outside_reviewed_scope", "actions": operation, "approved_scope": False})
    if plan.get("errored") or plan.get("applyable") is False:
        failures.append("PLAN_NOT_APPLYABLE")
    return {"status": "BLOCKED" if failures else "REVIEWABLE", "failure_codes": sorted(set(failures)),
            "actions": actions, "provider_attributes_exported": False,
            "requires_independent_review": True}


def source_snapshot(destination: Path) -> str:
    source = ROOT / "infra/terraform"
    destination.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256()
    paths = sorted([*source.glob("*.tf"), *source.glob("modules/**/*.tf"), source / ".terraform.lock.hcl"])
    for path in paths:
        relative = path.relative_to(source)
        data = path.read_bytes()
        digest.update(str(relative).replace("\\", "/").encode() + b"\0" + data + b"\0")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return digest.hexdigest()


def ephemeral_environment(variables: dict, legacy_password: str) -> dict:
    if not legacy_password:
        raise PlanBlocked("LEGACY_CREDENTIAL_UNAVAILABLE")
    values = {**variables, "database_password": legacy_password,
              "tasteduel_runtime_password": secrets.token_urlsafe(48),
              "tasteduel_migration_password": secrets.token_urlsafe(48)}
    return {"TF_VAR_" + key: json.dumps(value) if not isinstance(value, str) else value
            for key, value in values.items()}


def adc_path() -> Path:
    configured = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    location = Path(configured) if configured else Path(os.environ.get("APPDATA", "")) / "gcloud/application_default_credentials.json"
    if not location.is_file():
        raise PlanBlocked("ADC_FILE_REQUIRED")
    return location.resolve()


def terraform(directory: Path, adc: Path, environment: dict, *arguments: str) -> str:
    if not arguments or arguments[0] not in {"init", "plan", "show"}:
        raise PlanBlocked("TERRAFORM_OPERATION_NOT_ALLOWED")
    if any(value.startswith(("-target", "-destroy", "-replace")) for value in arguments):
        raise PlanBlocked("PARTIAL_OR_DESTRUCTIVE_PLAN_NOT_ALLOWED")
    command = ["docker", "run", "--rm", "--mount", f"type=bind,source={directory},target=/work",
               "--mount", f"type=bind,source={adc},target=/adc.json,readonly",
               "--workdir", "/work", "--env", "GOOGLE_APPLICATION_CREDENTIALS=/adc.json"]
    for key in environment:
        command += ["--env", key]
    command += [IMAGE, *arguments]
    result = subprocess.run(command, env={**os.environ, **environment}, capture_output=True, text=True)
    # Provider errors can include sensitive attributes. Never stream/log stdout,
    # stderr or subprocess exception text; only a static stage error is returned.
    if result.returncode:
        raise PlanBlocked("TERRAFORM_STAGE_FAILED_" + arguments[0].upper())
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True, help="Approved nonsecret cumulative cost JSON")
    arguments = parser.parse_args()
    try:
        review = json.loads(arguments.review.read_text(encoding="utf-8"))
        variables = approved_variables(review)
        adc = adc_path()
        directory = ROOT / ".data/tasteduel-cloud-review" / ("foundation-plan-" + secrets.token_hex(8))
        source_hash = source_snapshot(directory)
        # Explicit invocation only. No key/list/history access, no credential file.
        from google.cloud import secretmanager
        response = secretmanager.SecretManagerServiceClient().access_secret_version(request={"name": LEGACY_PASSWORD})
        environment = ephemeral_environment(variables, response.payload.data.decode("utf-8"))
        del response
        terraform(directory, adc, environment, "init", "-input=false", "-lockfile=readonly",
                  "-backend-config=bucket=" + BACKEND_BUCKET, "-backend-config=prefix=" + BACKEND_PREFIX)
        terraform(directory, adc, environment, "plan", "-input=false", "-no-color", "-lock-timeout=60s", "-out=foundation.tfplan")
        result = audit_plan(json.loads(terraform(directory, adc, environment, "show", "-json", "foundation.tfplan")))
        result.update({"source_sha256": source_hash, "plan_sha256": hashlib.sha256((directory / "foundation.tfplan").read_bytes()).hexdigest(),
                       "backend_bucket": BACKEND_BUCKET, "backend_prefix": BACKEND_PREFIX,
                       "cost_gate_status": review["cost_gate_status"], "reviewed_total_usd": review["reviewed_total_usd"],
                       "created_at_utc": datetime.now(timezone.utc).isoformat(), "applied": False,
                       "ephemeral_inputs_persisted": False})
        (directory / "review.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "review": str(directory / "review.json"), "applied": False}))
        return 0 if result["status"] == "REVIEWABLE" else 2
    except Exception as failure:
        reason = str(failure) if isinstance(failure, PlanBlocked) else "FOUNDATION_PLAN_FAILED_" + type(failure).__name__
        print(json.dumps({"status": "BLOCKED", "reason_code": reason, "applied": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

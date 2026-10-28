"""Plan-only full-root migration/candidate release with strict action scope.

All credentials are resolved from exact Secret Manager versions into memory on
explicit execution. No apply, job execution, public IAM, state edit or targeting.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets

from tasteduel_foundation_plan import (
    BACKEND_BUCKET, BACKEND_PREFIX, LEGACY_PASSWORD, PROJECT, REGION, ROOT,
    PlanBlocked, adc_path, approved_variables, source_snapshot, terraform,
)
from tasteduel_release_images import immutable_reference

CONNECTION = f"{PROJECT}:{REGION}:accesslife-db"
SA = {actor: f"tasteduel-{actor}@{PROJECT}.iam.gserviceaccount.com" for actor in ("api", "web", "migrate", "deploy")}
ADDRESSES = {
    "gate": "terraform_data.tasteduel_release_gate[0]",
    "migrate": "google_cloud_run_v2_job.tasteduel_migrate[0]",
    "job_deploy": "google_cloud_run_v2_job_iam_member.tasteduel_deploy[0]",
    "api": "google_cloud_run_v2_service.tasteduel_api[0]",
    "web": "google_cloud_run_v2_service.tasteduel_web[0]",
    "api_web": "google_cloud_run_v2_service_iam_member.tasteduel_api_web[0]",
    "web_tester": "google_cloud_run_v2_service_iam_member.tasteduel_web_tester[0]",
    "deploy_api": 'google_cloud_run_v2_service_iam_member.tasteduel_deploy["api"]',
    "deploy_web": 'google_cloud_run_v2_service_iam_member.tasteduel_deploy["web"]',
}
VERIFICATION_ALLOWANCES = {
    "verification-budget": ("6", "8"),  # Historical reviewed allowance only.
    "candidate-closure-budget": ("8", "10"),
}
PHASES = ("migration", "services", "refresh", *VERIFICATION_ALLOWANCES)
PRODUCTION_PHASES = ("production-pin", "production-prepare", "production-candidate", "production-rollback-ready", "production-seal",
                     "production-promote", "production-rollback", "production-observability")


def images_input(record: dict) -> dict:
    source = record.get("source_sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise PlanBlocked("RELEASE_SOURCE_REQUIRED")
    ci = record.get("ci", {})
    if ci.get("head_sha") != source or ci.get("conclusion") != "success" or ci.get("status") != "completed":
        raise PlanBlocked("PUBLISHED_IMAGE_CI_PROVENANCE_REQUIRED")
    result = {}
    for actor in ("api", "web"):
        image = record.get("images", {}).get(actor, {})
        expected = immutable_reference("tasteduel-" + actor, image.get("digest", ""))
        if image.get("reference") != expected:
            raise PlanBlocked("IMMUTABLE_IMAGE_RECORD_INVALID")
        result[actor] = expected
    return {**result, "source_sha": source}


def env_values(container: dict) -> dict | None:
    result = {}
    for item in container.get("env", []):
        if item.get("name") in result or item.get("value_source"):
            return None
        result[item.get("name")] = item.get("value")
    return result


def secret_reference(actor: str) -> str:
    role = "runtime" if actor == "api" else "migrate"
    return f"projects/{PROJECT}/secrets/tasteduel-{role}-database-url/versions/1"


def socket_mount(container: dict, task: dict) -> bool:
    volumes, mounts = task.get("volumes", []), container.get("volume_mounts", [])
    return (len(volumes) == 1 and volumes[0].get("name") == "cloudsql"
            and volumes[0].get("cloud_sql_instance") == [{"instances": [CONNECTION]}]
            and len(mounts) == 1 and mounts[0].get("name") == "cloudsql"
            and mounts[0].get("mount_path") == "/cloudsql")


def safe_job(after: dict, images: dict, *, ops_cost_hash: str | None = None, ops_through: str | None = None) -> bool:
    try:
        task = after["template"][0]["template"][0]
        container = task["containers"][0]
        return (after["name"] == "tasteduel-migrate" and after["project"] == PROJECT and after["location"] == REGION
                and after["deletion_protection"] is True and after["template"][0]["task_count"] == 1
                and after["template"][0]["parallelism"] == 1 and task["service_account"] == SA["migrate"]
                and task["timeout"] == "300s" and task["max_retries"] == 0 and len(task["containers"]) == 1
                and container["image"] == images["api"]
                and container["command"] == (["alembic"] if ops_cost_hash is None else ["python", "-m", "tasteduel.operations"])
                and container["args"] == (["-c", "apps/api/tasteduel-alembic.ini", "upgrade", "head"] if ops_cost_hash is None else ["migrate"])
                and socket_mount(container, task)
                and container["resources"][0]["limits"] == {"cpu": "1", "memory": "512Mi"}
                and env_values(container) == {"TASTEDUEL_DATABASE_MODE": "cloud_sql",
                    "TASTEDUEL_CLOUD_SQL_CONNECTION_NAME": CONNECTION,
                    "TASTEDUEL_MIGRATION_DATABASE_SECRET_VERSION": secret_reference("migrate"),
                    "TASTEDUEL_QLOO_ENABLED": "false", "TASTEDUEL_GENERATION_ENABLED": "false",
                    **({"TASTEDUEL_OPS_COST_REVIEW_HASH": ops_cost_hash,
                        "TASTEDUEL_OPS_REVIEWED_THROUGH_UTC": ops_through} if ops_cost_hash else {})})
    except (KeyError, IndexError, TypeError):
        return False


def safe_service(after: dict, actor: str, images: dict, origin: str, *, api_uri: str | None = None,
                 unknown: dict | None = None, vertex_limit: str = "10", qloo_limit: str = "12") -> bool:
    try:
        template = after["template"][0]
        container = template["containers"][0]
        limits = {"cpu": "1", "memory": "1Gi" if actor == "api" else "512Mi"}
        traffic = after["traffic"]
        if not (after["name"] == "tasteduel-" + actor and after["project"] == PROJECT and after["location"] == REGION
                and after["deletion_protection"] is True and after["ingress"] == "INGRESS_TRAFFIC_ALL"
                and template["service_account"] == SA[actor] and template["timeout"] == "60s"
                and template["scaling"][0]["max_instance_count"] == 1 and template["scaling"][0]["min_instance_count"] == 0
                and template["max_instance_request_concurrency"] == (8 if actor == "api" else 20)
                and container["image"] == images[actor] and len(template["containers"]) == 1
                and container["ports"][0]["container_port"] == (8000 if actor == "api" else 3000)
                and container["resources"][0]["limits"] == limits
                and container["resources"][0]["cpu_idle"] is True
                and container["resources"][0]["startup_cpu_boost"] is False
                and len(traffic) == 1 and traffic[0]["percent"] == 100
                and traffic[0]["type"] == "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"):
            return False
        environment = env_values(container)
        if environment is None:
            return False
        if actor == "api":
            return socket_mount(container, template) and environment == {
                "TASTEDUEL_DATABASE_MODE": "cloud_sql", "TASTEDUEL_CLOUD_SQL_CONNECTION_NAME": CONNECTION,
                "TASTEDUEL_DATABASE_SECRET_VERSION": secret_reference("api"), "TASTEDUEL_COOKIE_SECURE": "true",
                "TASTEDUEL_ALLOWED_ORIGINS": json.dumps([origin], separators=(",", ":")),
                "TASTEDUEL_QLOO_ENABLED": "true", "TASTEDUEL_QLOO_TRANSPORT": "http_ranked",
                "TASTEDUEL_QLOO_HTTP_TYPED_SEARCH": "true",
                "TASTEDUEL_QLOO_SECRET_VERSION": f"projects/{PROJECT}/secrets/accesslife-qloo-api-key/versions/1",
                "TASTEDUEL_GENERATION_ENABLED": "true", "TASTEDUEL_VERTEX_PROJECT": PROJECT,
                "TASTEDUEL_VERTEX_REQUESTS_PER_DAY": vertex_limit, "TASTEDUEL_VERTEX_TOKENS_PER_DAY": "500000",
                "TASTEDUEL_QLOO_REQUESTS_PER_DAY": qloo_limit, "TASTEDUEL_QLOO_REQUESTS_PER_MINUTE": "12",
            }
        expected_keys = {"TASTEDUEL_API_URL", "TASTEDUEL_API_AUDIENCE", "TASTEDUEL_API_IAM", "TASTEDUEL_WEB_ORIGINS",
                         "TASTEDUEL_CANONICAL_ORIGIN", "TASTEDUEL_ALLOW_LOCAL_HTTP"}
        if set(environment) != expected_keys:
            return False
        if api_uri:
            targets_match = environment["TASTEDUEL_API_URL"] == environment["TASTEDUEL_API_AUDIENCE"] == api_uri
        else:
            unknown_env = (unknown or {}).get("template", [{}])[0].get("containers", [{}])[0].get("env", [])
            targets_match = len(unknown_env) == len(container.get("env", []))
            for index, item in enumerate(container.get("env", [])):
                if item.get("name") in {"TASTEDUEL_API_URL", "TASTEDUEL_API_AUDIENCE"}:
                    targets_match &= item.get("value") is None and index < len(unknown_env) and unknown_env[index].get("value") is True
        return (targets_match and environment["TASTEDUEL_API_IAM"] == "true"
                and environment["TASTEDUEL_ALLOW_LOCAL_HTTP"] == "false"
                and environment["TASTEDUEL_WEB_ORIGINS"] == environment["TASTEDUEL_CANONICAL_ORIGIN"] == origin)
    except (KeyError, IndexError, TypeError):
        return False


def image_only_update(before: dict, after: dict, *, actor: str) -> bool:
    """Permit reviewed candidate digest/source labels only, never policy drift."""
    old, new = deepcopy(before), deepcopy(after)
    # Provider-computed output metadata changes as a revision reconciles.
    computed = {"uid", "etag", "create_time", "update_time", "delete_time", "expire_time",
                "creator", "last_modifier", "generation", "observed_generation", "reconciling",
                "terminal_condition", "conditions", "latest_created_revision", "latest_ready_revision",
                "traffic_statuses", "urls"}
    try:
        for value in (old, new):
            for key in computed:
                value.pop(key, None)
            for key in ("labels", "terraform_labels", "effective_labels"):
                labels = value.get(key)
                if labels is not None:
                    labels.pop("source_ref", None)
            template = value["template"][0]
            if actor == "migrate":
                template = template["template"][0]
            else:
                template.pop("revision", None)  # generated revision identifier
            for container in template.get("containers", []):
                if env_values(container) is not None:
                    container["env"] = sorted(container.get("env", []), key=lambda item: item["name"])
            image = template["containers"][0].pop("image")
            if not re.fullmatch(
                rf"{REGION}-docker\.pkg\.dev/{PROJECT}/accesslife/tasteduel-{'api' if actor == 'migrate' else actor}@sha256:[0-9a-f]{{64}}",
                image,
            ):
                return False
        return old == new
    except (KeyError, IndexError, TypeError, AttributeError):
        return False


def audit_release(plan: dict, *, phase: str, images: dict, tester: str, project_number: str) -> dict:
    origin = f"https://tasteduel-web-{project_number}.{REGION}.run.app"
    keys = (("gate", "migrate", "job_deploy") if phase == "migration" else
            ("migrate", "api", "web") if phase == "refresh" else
            ("api",) if phase in VERIFICATION_ALLOWANCES else ADDRESSES)
    allowed = {ADDRESSES[key] for key in keys}
    actions, blocked = [], phase not in PHASES
    api_uri = next(((resource.get("change", {}).get("after") or {}).get("uri") for resource in plan.get("resource_changes", [])
                    if resource.get("address") == ADDRESSES["api"]), None)
    for resource in plan.get("resource_changes", []):
        address, change = resource.get("address", ""), resource.get("change", {})
        operation = change.get("actions", [])
        if operation in (["no-op"], ["read"]):
            continue
        after = change.get("after") or {}
        safe = address in allowed and operation == (["update"] if phase == "refresh" or phase in VERIFICATION_ALLOWANCES else ["create"])
        if safe and address == ADDRESSES["migrate"]:
            safe = safe_job(after, images)
        elif safe and address in (ADDRESSES["api"], ADDRESSES["web"]):
            safe = safe_service(after, "api" if address == ADDRESSES["api"] else "web", images, origin,
                                api_uri=api_uri, unknown=change.get("after_unknown"),
                                vertex_limit=VERIFICATION_ALLOWANCES.get(phase, (None, "10"))[1])
        elif safe and "_iam_member." in address:
            expected = {
                ADDRESSES["job_deploy"]: ("tasteduel-migrate", "roles/run.developer", "serviceAccount:" + SA["deploy"]),
                ADDRESSES["api_web"]: ("tasteduel-api", "roles/run.invoker", "serviceAccount:" + SA["web"]),
                ADDRESSES["web_tester"]: ("tasteduel-web", "roles/run.invoker", tester),
                ADDRESSES["deploy_api"]: ("tasteduel-api", "roles/run.developer", "serviceAccount:" + SA["deploy"]),
                ADDRESSES["deploy_web"]: ("tasteduel-web", "roles/run.developer", "serviceAccount:" + SA["deploy"]),
            }[address]
            safe = ((after.get("name"), after.get("role"), after.get("member")) == expected
                    and after.get("project") == PROJECT and after.get("location") == REGION)
        if safe and phase == "refresh":
            actor = "migrate" if address == ADDRESSES["migrate"] else "api" if address == ADDRESSES["api"] else "web"
            safe = (after.get("labels", {}).get("source_ref") == images["source_sha"][:12]
                    and image_only_update(change.get("before") or {}, after, actor=actor))
        if safe and phase in VERIFICATION_ALLOWANCES:
            before = deepcopy(change.get("before") or {})
            try:
                old_limit, new_limit = VERIFICATION_ALLOWANCES[phase]
                old_container = before["template"][0]["containers"][0]
                new_container = after["template"][0]["containers"][0]
                old_env = env_values(old_container)
                safe = (old_env.get("TASTEDUEL_VERTEX_REQUESTS_PER_DAY") == old_limit
                        and old_container["image"] == new_container["image"]
                        and all(before.get(key) == after.get(key) for key in ("labels", "terraform_labels", "effective_labels")))
                for item in old_container["env"]:
                    if item["name"] == "TASTEDUEL_VERTEX_REQUESTS_PER_DAY":
                        item["value"] = new_limit
                safe = safe and image_only_update(before, after, actor="api")
            except (KeyError, IndexError, TypeError, AttributeError):
                safe = False
        blocked |= not safe
        actions.append({"address": address if address in ADDRESSES.values() else "outside_release_scope",
                        "actions": operation, "approved_scope": bool(safe)})
    return {"status": "BLOCKED" if blocked or plan.get("errored") else "REVIEWABLE", "phase": phase,
            "actions": actions, "public_access": False, "initial_service_allocation_percent": 100 if phase != "migration" else None,
            "requires_independent_review": True, "provider_attributes_exported": False}


def credential_environment(variables: dict) -> dict:
    from google.cloud import secretmanager
    from sqlalchemy.engine import make_url

    client = secretmanager.SecretManagerServiceClient()

    def read(reference):
        return client.access_secret_version(request={"name": reference}).payload.data.decode("utf-8")

    values = {**variables, "database_password": read(LEGACY_PASSWORD)}
    for actor, variable, username in (("api", "tasteduel_runtime_password", "tasteduel_runtime"),
                                      ("migrate", "tasteduel_migration_password", "tasteduel_migrator")):
        url = make_url(read(secret_reference(actor)))
        if (url.drivername != "postgresql+psycopg" or url.username != username or url.database != "tasteduel"
                or url.query.get("host") != "/cloudsql/" + CONNECTION or not url.password):
            raise PlanBlocked("ESTABLISHED_DATABASE_CREDENTIAL_REFERENCE_INVALID")
        values[variable] = url.password
    return {"TF_VAR_" + key: json.dumps(value) if not isinstance(value, str) else value for key, value in values.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--phase", choices=(*PHASES, *PRODUCTION_PHASES), required=True)
    parser.add_argument("--production-manifest", type=Path)
    parser.add_argument("--smoke-evidence", type=Path)
    parser.add_argument("--tester", required=True, help="One reviewed user:email IAM principal; no public/group grants")
    parser.add_argument("--project-number", required=True)
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"user:[^\s@]+@[^\s@]+", args.tester) or not re.fullmatch(r"[0-9]{6,20}", args.project_number):
            raise PlanBlocked("REVIEWED_TESTER_AND_PROJECT_NUMBER_REQUIRED")
        review = json.loads(args.review.read_text(encoding="utf-8"))
        variables = approved_variables(review)
        images = images_input(json.loads(args.images.read_text(encoding="utf-8")))
        variables.update({"tasteduel_release_migration_enabled": True, "tasteduel_release_services_enabled": args.phase != "migration",
                          "tasteduel_release_api_image": images["api"], "tasteduel_release_web_image": images["web"],
                          "tasteduel_release_source_sha": images["source_sha"], "tasteduel_candidate_tester": args.tester})
        manifest = None
        if args.phase in PRODUCTION_PHASES:
            from tasteduel_production_release import check_evidence, digest, phase_images, phase_variables, validate_manifest

            if args.production_manifest is None:
                raise PlanBlocked("PRODUCTION_MANIFEST_REQUIRED")
            manifest = validate_manifest(json.loads(args.production_manifest.read_text(encoding="utf-8")))
            if images_input(manifest["images"]) != images:
                raise PlanBlocked("PRODUCTION_PUBLISHED_IMAGE_RECORD_MISMATCH")
            if digest(review) != manifest["cost_sha256"]:
                raise PlanBlocked("PRODUCTION_COST_REVIEW_CHANGED")
            if review["reviewed_through_utc"] != manifest["reviewed_through_utc"]:
                raise PlanBlocked("PRODUCTION_OPERATIONS_HORIZON_MISMATCH")
            if args.phase == "production-promote":
                if args.smoke_evidence is None:
                    raise PlanBlocked("SEALED_SMOKE_REQUIRED_BEFORE_PUBLIC_GRANT")
                check_evidence(json.loads(args.smoke_evidence.read_text(encoding="utf-8")), manifest, kind="sealed-smoke")
            variables.update(phase_variables(manifest, args.phase))
            images = phase_images(manifest, args.phase)
        directory = ROOT / ".data/tasteduel-cloud-review" / ("release-" + args.phase + "-plan-" + secrets.token_hex(8))
        source_hash = source_snapshot(directory)
        adc, environment = adc_path(), credential_environment(variables)
        terraform(directory, adc, environment, "init", "-input=false", "-lockfile=readonly",
                  "-backend-config=bucket=" + BACKEND_BUCKET, "-backend-config=prefix=" + BACKEND_PREFIX)
        terraform(directory, adc, environment, "plan", "-input=false", "-no-color", "-lock-timeout=60s", "-out=release.tfplan")
        plan = json.loads(terraform(directory, adc, environment, "show", "-json", "release.tfplan"))
        if manifest:
            from tasteduel_production_release import audit_production

            if args.phase == "production-observability":
                from tasteduel_observability_plan import audit_observability

                result = audit_observability(plan, manifest)
            else:
                result = audit_production(plan, manifest, args.phase)
            (directory / "production-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            if args.smoke_evidence:
                (directory / "smoke-evidence.json").write_text(args.smoke_evidence.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            result = audit_release(plan, phase=args.phase, images=images, tester=args.tester, project_number=args.project_number)
        result.update({"source_sha256": source_hash, "plan_sha256": hashlib.sha256((directory / "release.tfplan").read_bytes()).hexdigest(),
                       "image_source_sha": images["source_sha"], "reviewed_total_usd": review["reviewed_total_usd"],
                       "created_at_utc": datetime.now(timezone.utc).isoformat(), "applied": False})
        output = directory / "review.json"
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "review": str(output), "applied": False}))
        return 0 if result["status"] == "REVIEWABLE" else 2
    except Exception as failure:
        reason = str(failure) if isinstance(failure, PlanBlocked) else "RELEASE_PLAN_FAILED_" + type(failure).__name__
        print(json.dumps({"status": "BLOCKED", "reason_code": reason, "applied": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

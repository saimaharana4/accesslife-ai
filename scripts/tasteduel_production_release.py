"""Finite production-release policy and explicit root-ADC Terraform handoffs.

No public IAM, Terraform apply, arbitrary shell or provider inference is run by
this CLI. WIF can verify provenance and invoke only the existing migration job.
Reviewed root-ADC plans own service configuration, routing and public web IAM.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from tasteduel_foundation_plan import PROJECT, REGION, PlanBlocked, approved_variables
from tasteduel_release_images import REPOSITORY, immutable_reference, process, verified_ci

PHASES = ("production-pin", "production-prepare", "production-candidate", "production-rollback-ready", "production-seal",
          "production-promote", "production-rollback", "production-observability")
ORIGIN = "https://tasteduel-web-902056825143.asia-south1.run.app"
MODEL_LIMIT, QLOO_LIMIT = 50, 100


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def revision(value: str, actor: str) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(rf"tasteduel-{actor}-[a-z0-9-]{{1,45}}", value))


def validate_manifest(value: dict) -> dict:
    from tasteduel_release_plan import images_input

    required = {"version", "project", "region", "origin", "images", "baseline", "candidate", "release", "rollback",
                "cost_sha256", "schema", "preview_guard", "reviewed_through_utc"}
    if (set(value) != required or type(value["version"]) is not int or value["version"] != 1 or value["project"] != PROJECT
            or value["region"] != REGION or value["origin"] != ORIGIN
            or value["preview_guard"] != "iam-private-initial"
            or not re.fullmatch(r"[0-9a-f]{64}", value["cost_sha256"])):
        raise PlanBlocked("PRODUCTION_MANIFEST_BOUNDARY_INVALID")
    images_input(value["images"])
    try:
        horizon = datetime.fromisoformat(value["reviewed_through_utc"].replace("Z", "+00:00"))
        if horizon.tzinfo is None or horizon > datetime(2026, 11, 7, 4, 45, tzinfo=timezone.utc):
            raise ValueError("outside operational horizon")
    except (TypeError, ValueError):
        raise PlanBlocked("REVIEWED_OPERATIONS_HORIZON_REQUIRED") from None
    for name in ("baseline", "rollback"):
        item = value[name]
        if set(item) != {"api_revision", "web_revision", "api_image", "web_image", "source_sha", "vertex_limit", "qloo_limit"}:
            raise PlanBlocked("COMPATIBLE_BASELINE_FIELDS_REQUIRED")
        for actor in ("api", "web"):
            if not revision(item[actor + "_revision"], actor):
                raise PlanBlocked("KNOWN_BASELINE_REVISION_REQUIRED")
            image = item[actor + "_image"]
            if not isinstance(image, str) or image != immutable_reference("tasteduel-" + actor, image.rsplit("@", 1)[-1]):
                raise PlanBlocked("KNOWN_BASELINE_DIGEST_REQUIRED")
        if not re.fullmatch(r"[0-9a-f]{40}", item["source_sha"]):
            raise PlanBlocked("KNOWN_BASELINE_SOURCE_REQUIRED")
        if (item["vertex_limit"], item["qloo_limit"]) != ((10, 12) if name == "baseline" else (MODEL_LIMIT, QLOO_LIMIT)):
            raise PlanBlocked("ROLLBACK_ADMISSION_POLICY_INCOMPATIBLE")
    current_images = images_input(value["images"])
    if any(value["rollback"][key] != expected for key, expected in {
            "api_image": current_images["api"], "web_image": current_images["web"], "source_sha": current_images["source_sha"]}.items()):
        raise PlanBlocked("INITIAL_ROLLBACK_MUST_USE_NEW_SCHEMA_COMPATIBLE_CODE")
    for name in ("candidate", "release"):
        item = value[name]
        required_keys = {"api_revision", "web_revision"} | ({"tag", "origin", "api_url"} if name == "candidate" else set())
        if set(item) != required_keys or any(not revision(item[actor + "_revision"], actor) for actor in ("api", "web")):
            raise PlanBlocked("EXPLICIT_REVIEWED_REVISION_NAMES_REQUIRED")
    candidate = value["candidate"]
    if (not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", candidate["tag"])
            or not re.fullmatch(r"https://" + re.escape(candidate["tag"]) + r"---tasteduel-web-[a-z0-9-]+\.a\.run\.app", candidate["origin"])):
        raise PlanBlocked("VERIFIED_PRIVATE_TAG_ORIGIN_REQUIRED")
    if not re.fullmatch(r"https://" + re.escape(candidate["tag"]) + r"---tasteduel-api-[a-z0-9-]+\.a\.run\.app", candidate["api_url"]):
        raise PlanBlocked("VERIFIED_PRIVATE_API_TAG_URL_REQUIRED")
    for actor in ("api", "web"):
        if len({value[key][actor + "_revision"] for key in ("baseline", "candidate", "release", "rollback")}) != 4:
            raise PlanBlocked("IMMUTABLE_CANDIDATE_AND_SEALED_REVISIONS_MUST_DIFFER")
    if (set(value["schema"]) != {"from", "to", "backward_compatible"}
            or value["schema"]["backward_compatible"] is not True
            or any(not re.fullmatch(r"td[0-9]{4}", value["schema"][key]) for key in ("from", "to"))):
        raise PlanBlocked("REVIEWED_BACKWARD_COMPATIBLE_SCHEMA_REQUIRED")
    return deepcopy(value)


def phase_images(manifest: dict, phase: str) -> dict:
    from tasteduel_release_plan import images_input

    if phase not in PHASES:
        raise PlanBlocked("PRODUCTION_PHASE_INVALID")
    if phase in {"production-pin", "production-prepare", "production-rollback"}:
        item = manifest["baseline" if phase != "production-rollback" else "rollback"]
        return {"api": item["api_image"], "web": item["web_image"], "source_sha": item["source_sha"]}
    return images_input(manifest["images"])


def phase_variables(manifest: dict, phase: str) -> dict:
    images = phase_images(manifest, phase)
    target = manifest["baseline" if phase in {"production-pin", "production-prepare", "production-candidate"} else
                      "rollback" if phase in {"production-rollback", "production-rollback-ready"} else "release"]
    candidate = manifest["candidate"] if phase == "production-candidate" else None
    template = manifest["candidate" if candidate else "release"] if phase not in {"production-pin", "production-prepare", "production-rollback"} else None
    if phase == "production-rollback-ready":
        template = manifest["rollback"]
    elif phase == "production-rollback":
        template = manifest["release"]  # Roll traffic back without creating/replacing a template.
    return {
        "tasteduel_release_api_image": images["api"], "tasteduel_release_web_image": images["web"],
        "tasteduel_release_source_sha": images["source_sha"],
        "tasteduel_public_enabled": phase in {"production-promote", "production-rollback", "production-observability"},
        "tasteduel_observability_enabled": phase in {"production-observability", "production-rollback"},
        "tasteduel_api_traffic_revision": target["api_revision"], "tasteduel_web_traffic_revision": target["web_revision"],
        "tasteduel_api_candidate_revision": template["api_revision"] if template else None,
        "tasteduel_web_candidate_revision": template["web_revision"] if template else None,
        "tasteduel_candidate_tag": candidate["tag"] if candidate else None,
        "tasteduel_candidate_origin": candidate["origin"] if candidate else None,
        "tasteduel_candidate_api_url": candidate["api_url"] if candidate else None,
        "tasteduel_vertex_requests_per_day": 10 if phase in {"production-pin", "production-prepare"} else MODEL_LIMIT,
        "tasteduel_qloo_requests_per_day": 12 if phase in {"production-pin", "production-prepare"} else QLOO_LIMIT,
        "tasteduel_release_migration_image": manifest["images"]["images"]["api"]["reference"] if phase != "production-pin" else None,
        "tasteduel_release_migration_source_sha": manifest["images"]["source_sha"] if phase != "production-pin" else None,
        "tasteduel_ops_cost_review_hash": manifest["cost_sha256"] if phase != "production-pin" else None,
    }


def check_evidence(evidence: dict, manifest: dict, *, kind: str, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    expected = {"kind", "status", "manifest_sha256", "source_sha", "api_revision", "web_revision",
                "checked_at_utc", "checks"}
    target = manifest["release"] if kind in {"sealed-smoke", "post-release"} else manifest["candidate"]
    try:
        timestamp = datetime.fromisoformat(evidence["checked_at_utc"].replace("Z", "+00:00"))
        valid = (set(evidence) == expected and evidence["kind"] == kind and evidence["status"] == "PASS"
                 and evidence["manifest_sha256"] == digest(manifest)
                 and evidence["source_sha"] == manifest["images"]["source_sha"]
                 and all(evidence[actor + "_revision"] == target[actor + "_revision"] for actor in ("api", "web"))
                 and 0 <= (now - timestamp).total_seconds() <= 86400
                 and set(evidence["checks"]) == {"gameplay", "fixed_replay", "private_api", "secrecy", "axe", "keyboard", "reduced_motion"}
                 and all(type(item) is bool and item is True for item in evidence["checks"].values()))
    except (ValueError, TypeError, KeyError):
        valid = False
    if not valid:
        raise PlanBlocked("CURRENT_EXACT_CONFIGURATION_SMOKE_REQUIRED")


def audit_production(plan: dict, manifest: dict, phase: str) -> dict:
    """Allow only exact declared service/job/routing changes, never SQL or API IAM."""
    from tasteduel_release_plan import ADDRESSES, image_only_update, safe_job, safe_service

    validate_manifest(manifest)
    variables, images = phase_variables(manifest, phase), phase_images(manifest, phase)
    public_address = "google_cloud_run_v2_service_iam_member.tasteduel_web_public[0]"
    actions, blocked, services_seen = [], bool(plan.get("errored")) or phase == "production-observability", set()
    api_uri = next(((item.get("change", {}).get("after") or {}).get("uri") for item in plan.get("resource_changes", [])
                    if item.get("address") == ADDRESSES["api"]), None)
    for item in plan.get("resource_changes", []):
        address, change = item.get("address"), item.get("change", {})
        operation, after, before = change.get("actions"), change.get("after") or {}, change.get("before") or {}
        if address in {ADDRESSES["api"], ADDRESSES["web"]}:
            services_seen.add(address)
        if (after.get("name") == "tasteduel-api" and after.get("role") == "roles/run.invoker"
                and after.get("member") in {"allUsers", "allAuthenticatedUsers"}):
            blocked = True
        if operation in (["no-op"], ["read"]):
            if phase == "production-promote" and address in {ADDRESSES["api"], ADDRESSES["web"]}:
                actor = "api" if address == ADDRESSES["api"] else "web"
                target = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION", "revision": manifest["release"][actor + "_revision"], "percent": 100}]
                actual = [{key: value for key, value in route.items() if value not in (None, "")} for route in after.get("traffic", [])]
                container = after.get("template", [{}])[0].get("containers", [{}])[0]
                revised = deepcopy(after)
                revised["traffic"] = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST", "percent": 100}]
                blocked |= (actual != target or container.get("image") != images[actor]
                    or not safe_service(revised, actor, images, ORIGIN, api_uri=api_uri,
                                        vertex_limit=str(MODEL_LIMIT), qloo_limit=str(QLOO_LIMIT))
                    or container.get("command") not in (None, []) or container.get("args") not in (None, []))
            continue
        safe = False
        if address in {ADDRESSES["api"], ADDRESSES["web"]} and operation == ["update"] and phase not in {"production-promote", "production-prepare"}:
            actor = "api" if address == ADDRESSES["api"] else "web"
            revised = deepcopy(after)
            expected_traffic = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION", "revision": variables[f"tasteduel_{actor}_traffic_revision"], "percent": 100}]
            if phase == "production-candidate":
                expected_traffic.append({"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION", "revision": variables[f"tasteduel_{actor}_candidate_revision"], "percent": 0, "tag": manifest["candidate"]["tag"]})
            actual_traffic = [{key: value for key, value in target.items() if value not in (None, "")} for target in after.get("traffic", [])]
            routing_match = sorted(actual_traffic, key=lambda target: target["percent"], reverse=True) == expected_traffic
            revised["traffic"] = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST", "percent": 100}]
            candidate_origin = manifest["candidate"]["origin"] if phase == "production-candidate" else None
            for env in revised.get("template", [{}])[0].get("containers", [{}])[0].get("env", []):
                if candidate_origin and env.get("name") == "TASTEDUEL_ALLOWED_ORIGINS":
                    if env.get("value") == json.dumps([ORIGIN, candidate_origin], separators=(",", ":")):
                        env["value"] = json.dumps([ORIGIN], separators=(",", ":"))
                elif candidate_origin and env.get("name") == "TASTEDUEL_WEB_ORIGINS":
                    if env.get("value") == ORIGIN + "," + candidate_origin:
                        env["value"] = ORIGIN
                elif candidate_origin and env.get("name") == "TASTEDUEL_API_URL":
                    if env.get("value") == manifest["candidate"]["api_url"]:
                        env["value"] = api_uri
            template_name = after.get("template", [{}])[0].get("revision")
            safe = (routing_match and safe_service(revised, actor, images, ORIGIN, api_uri=api_uri,
                    unknown=change.get("after_unknown"), vertex_limit=str(variables["tasteduel_vertex_requests_per_day"]),
                    qloo_limit=str(variables["tasteduel_qloo_requests_per_day"]))
                    and after.get("labels", {}).get("source_ref") == images["source_sha"][:12]
                    and (phase == "production-pin" or template_name == variables[f"tasteduel_{actor}_candidate_revision"]))
            if safe:
                expected_before = deepcopy(before)
                expected_before["traffic"] = deepcopy(after["traffic"])
                if phase != "production-pin":
                    environment = {env["name"]: env for env in expected_before["template"][0]["containers"][0]["env"]}
                    replacements = ({"TASTEDUEL_VERTEX_REQUESTS_PER_DAY": str(MODEL_LIMIT),
                        "TASTEDUEL_QLOO_REQUESTS_PER_DAY": str(QLOO_LIMIT),
                        "TASTEDUEL_ALLOWED_ORIGINS": json.dumps([ORIGIN] + ([candidate_origin] if candidate_origin else []), separators=(",", ":"))}
                        if actor == "api" else {"TASTEDUEL_WEB_ORIGINS": ORIGIN + ("," + candidate_origin if candidate_origin else ""),
                            "TASTEDUEL_API_URL": manifest["candidate"]["api_url"] if candidate_origin else api_uri})
                    for name, value in replacements.items():
                        environment[name]["value"] = value
                safe = image_only_update(expected_before, after, actor=actor)
        elif address == ADDRESSES["migrate"] and phase in {"production-prepare", "production-candidate", "production-rollback-ready", "production-seal", "production-rollback"} and operation == ["update"]:
            expected_before = deepcopy(before)
            container = expected_before.get("template", [{}])[0].get("template", [{}])[0].get("containers", [{}])[0]
            container["command"], container["args"] = ["python", "-m", "tasteduel.operations"], ["migrate"]
            environment = {env["name"]: env for env in container["env"]}
            for name, value in {"TASTEDUEL_OPS_COST_REVIEW_HASH": manifest["cost_sha256"],
                                "TASTEDUEL_OPS_REVIEWED_THROUGH_UTC": manifest["reviewed_through_utc"]}.items():
                environment[name] = {"name": name, "value": value}
            container["env"] = list(environment.values())
            job_images = {**images, "api": manifest["images"]["images"]["api"]["reference"]}
            safe = (safe_job(after, job_images, ops_cost_hash=manifest["cost_sha256"], ops_through=manifest["reviewed_through_utc"])
                    and image_only_update(expected_before, after, actor="migrate")
                    and after.get("labels", {}).get("source_ref") == manifest["images"]["source_sha"][:12])
        elif address == public_address and operation == ["create"] and phase == "production-promote":
            safe = (after.get("project") == PROJECT and after.get("location") == REGION
                    and (after.get("name"), after.get("role"), after.get("member")) == ("tasteduel-web", "roles/run.invoker", "allUsers"))
        blocked |= not safe
        actions.append({"address": address if address in {*ADDRESSES.values(), public_address} else "outside_production_scope", "actions": operation, "approved_scope": bool(safe)})
    blocked |= services_seen != {ADDRESSES["api"], ADDRESSES["web"]}
    return {"status": "BLOCKED" if blocked else "REVIEWABLE", "phase": phase, "actions": actions,
            "manifest_sha256": digest(manifest), "public_access": phase in {"production-promote", "production-rollback"},
            "requires_independent_review": True, "provider_attributes_exported": False}


def operations_command(operation: str, manifest: dict, *, execute: bool, snapshot: str | None = None) -> list[str]:
    if operation not in {"migrate", "purge-expired", "promote-public-budget"}:
        raise PlanBlocked("OPERATIONS_COMMAND_NOT_ALLOWLISTED")
    arguments = [operation]
    if execute:
        arguments += ["--execute-reviewed-operation", "--cost-review-sha256", manifest["cost_sha256"]]
        if operation == "promote-public-budget":
            if not isinstance(snapshot, str) or not re.fullmatch(r"[0-9a-f]{64}", snapshot):
                raise PlanBlocked("EXACT_EXISTING_ADMISSION_SNAPSHOT_REQUIRED")
            arguments += ["--expected-snapshot-sha256", snapshot]
    elif operation == "migrate":
        raise PlanBlocked("EXPLICIT_MIGRATION_EXECUTION_REQUIRED")
    return ["gcloud", "run", "jobs", "execute", "tasteduel-migrate", "--project", PROJECT, "--region", REGION,
            "--args=" + ",".join(arguments), "--wait", "--quiet"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cost", type=Path, required=True)
    parser.add_argument("--stage", choices=("verify", "migrate", "purge-expired", "promote-public-budget", "candidate-smoke", "sealed-smoke", "post-release"), required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-sha")
    parser.add_argument("--ci-run-id", type=int)
    parser.add_argument("--expected-snapshot-sha256")
    args = parser.parse_args()
    try:
        manifest = validate_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
        cost = json.loads(args.cost.read_text(encoding="utf-8"))
        approved_variables(cost)
        if digest(cost) != manifest["cost_sha256"]:
            raise PlanBlocked("PRODUCTION_COST_REVIEW_CHANGED")
        if cost["reviewed_through_utc"] != manifest["reviewed_through_utc"]:
            raise PlanBlocked("PRODUCTION_OPERATIONS_HORIZON_MISMATCH")
        if args.stage == "verify":
            ci = manifest["images"]["ci"]
            if args.source_sha != manifest["images"]["source_sha"] or args.ci_run_id != ci["id"]:
                raise PlanBlocked("WORKFLOW_SOURCE_AND_MANIFEST_MISMATCH")
            request = Request(f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{int(ci['id'])}", headers={"User-Agent": "TasteDuel-release"})
            with urlopen(request, timeout=15) as response:
                verified_ci(json.load(response), manifest["images"]["source_sha"])
        elif args.stage in {"migrate", "purge-expired", "promote-public-budget"}:
            command = operations_command(args.stage, manifest, execute=args.execute, snapshot=args.expected_snapshot_sha256)
            metadata = json.loads(process(["gcloud", "run", "jobs", "describe", "tasteduel-migrate", "--project", PROJECT, "--region", REGION, "--format=json"]))
            job_template = metadata.get("spec", {}).get("template", {}).get("spec", {}).get("template", {}).get("spec", {})
            expected_image = manifest["images"]["images"]["api"]["reference"]
            container = job_template.get("containers", [{}])[0]
            if (container.get("image") != expected_image or container.get("command") != ["python", "-m", "tasteduel.operations"]
                    or container.get("args") != ["migrate"]
                    or job_template.get("serviceAccountName") != f"tasteduel-migrate@{PROJECT}.iam.gserviceaccount.com"):
                raise PlanBlocked("REVIEWED_MIGRATION_JOB_CONFIGURATION_REQUIRED")
            environment = {item["name"]: item.get("value") for item in container.get("env", [])}
            if (environment.get("TASTEDUEL_OPS_COST_REVIEW_HASH") != manifest["cost_sha256"]
                    or environment.get("TASTEDUEL_OPS_REVIEWED_THROUGH_UTC") != manifest["reviewed_through_utc"]):
                raise PlanBlocked("REVIEWED_OPERATIONS_COST_ENVIRONMENT_REQUIRED")
            process(command)
        else:
            if args.evidence is None:
                raise PlanBlocked("EXTERNAL_BROWSER_EVIDENCE_REQUIRED")
            check_evidence(json.loads(args.evidence.read_text(encoding="utf-8")), manifest, kind=args.stage)
        print(json.dumps({"status": "PASS", "stage": args.stage, "manifest_sha256": digest(manifest), "public_promotion": False}))
        return 0
    except Exception as failure:
        reason = str(failure) if isinstance(failure, PlanBlocked) else "PRODUCTION_STAGE_FAILED_" + type(failure).__name__
        print(json.dumps({"status": "BLOCKED", "reason_code": reason, "public_promotion": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

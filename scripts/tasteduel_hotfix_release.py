"""Compatible hotfix planning and explicitly reviewed one-shot saved-plan apply.

The existing public service remains public. A temporary zero-percent web tag
is intentionally reachable and is not an access-control boundary. No SQL,
migration job, secret, IAM, monitoring or admission-limit change is allowed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

import tasteduel_foundation_plan as foundation
from tasteduel_foundation_apply import source_hash
from tasteduel_foundation_plan import PROJECT, REGION, ROOT, PlanBlocked
from tasteduel_production_release import ORIGIN, digest, revision
from tasteduel_release_apply import apply_command, saved_input_matches
from tasteduel_release_plan import (
    ADDRESSES,
    SA,
    credential_environment,
    images_input,
    image_only_update,
    safe_job,
    safe_service,
)
from tasteduel_observability_plan import MONITORS, PUBLIC_WEB

PHASES = ("hotfix-candidate", "hotfix-seal", "hotfix-promote", "hotfix-rollback", "hotfix-rollforward")
API_URI = "https://tasteduel-api-dfthmgvvaa-el.a.run.app"


def baseline_reference() -> dict:
    return json.loads((ROOT / "infra/releases/production-2026-10-28.json").read_text(encoding="utf-8"))


def validate_manifest(value: dict) -> dict:
    expected = {
        "version",
        "kind",
        "project",
        "region",
        "origin",
        "images",
        "baseline_manifest_sha256",
        "baseline",
        "candidate",
        "release",
        "schema",
        "cost_sha256",
        "reviewed_through_utc",
        "preview_exposure",
    }
    if (
        set(value) != expected
        or value.get("version") != 1
        or type(value["version"]) is not int
        or value.get("kind") != "compatible-public-hotfix"
        or value.get("project") != PROJECT
        or value.get("region") != REGION
        or value.get("origin") != ORIGIN
        or value.get("preview_exposure") != "public-tag-intentionally-reachable"
        or value.get("schema") != {"from": "td0011", "to": "td0011", "backward_compatible": True}
    ):
        raise PlanBlocked("HOTFIX_MANIFEST_BOUNDARY_INVALID")
    previous = baseline_reference()
    old = images_input(previous["images"])
    current = images_input(value["images"])
    baseline = {
        **previous["release"],
        "api_image": old["api"],
        "web_image": old["web"],
        "source_sha": old["source_sha"],
    }
    if (
        value["baseline_manifest_sha256"] != digest(previous)
        or value["baseline"] != baseline
        or value["cost_sha256"] != previous["cost_sha256"]
        or value["reviewed_through_utc"] != previous["reviewed_through_utc"]
        or current["source_sha"] == old["source_sha"]
    ):
        raise PlanBlocked("HOTFIX_REVIEWED_BASELINE_OR_COST_CHANGED")
    candidate, release = value["candidate"], value["release"]
    if set(candidate) != {"api_revision", "web_revision", "tag", "origin", "api_url"} or set(release) != {
        "api_revision",
        "web_revision",
    }:
        raise PlanBlocked("HOTFIX_EXACT_REVISION_FIELDS_REQUIRED")
    for actor in ("api", "web"):
        names = [value[key][actor + "_revision"] for key in ("baseline", "candidate", "release")]
        if len(set(names)) != 3 or not all(revision(name, actor) for name in names):
            raise PlanBlocked("HOTFIX_DISTINCT_IMMUTABLE_REVISIONS_REQUIRED")
    tag = candidate["tag"]
    if (
        not isinstance(tag, str)
        or not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", tag)
        or candidate["origin"] != f"https://{tag}---tasteduel-web-dfthmgvvaa-el.a.run.app"
        or candidate["api_url"] != f"https://{tag}---tasteduel-api-dfthmgvvaa-el.a.run.app"
    ):
        raise PlanBlocked("HOTFIX_EXACT_EXISTING_SERVICE_TAGS_REQUIRED")
    return deepcopy(value)


def phase_variables(manifest: dict, phase: str) -> dict:
    if phase not in PHASES:
        raise PlanBlocked("HOTFIX_PHASE_INVALID")
    images = images_input(manifest["images"])
    old = baseline_reference()
    candidate = manifest["candidate"] if phase == "hotfix-candidate" else None
    template = candidate or manifest["release"]
    target = (
        manifest["baseline"]
        if phase in {"hotfix-candidate", "hotfix-seal", "hotfix-rollback"}
        else manifest["release"]
    )
    return {
        "tasteduel_release_migration_enabled": True,
        "tasteduel_release_services_enabled": True,
        "tasteduel_public_enabled": True,
        "tasteduel_observability_enabled": True,
        "tasteduel_public_hotfix_preview": bool(candidate),
        "tasteduel_release_api_image": images["api"],
        "tasteduel_release_web_image": images["web"],
        "tasteduel_release_source_sha": images["source_sha"],
        "tasteduel_api_traffic_revision": target["api_revision"],
        "tasteduel_web_traffic_revision": target["web_revision"],
        "tasteduel_api_candidate_revision": template["api_revision"],
        "tasteduel_web_candidate_revision": template["web_revision"],
        "tasteduel_candidate_tag": candidate["tag"] if candidate else None,
        "tasteduel_candidate_origin": candidate["origin"] if candidate else None,
        "tasteduel_candidate_api_url": candidate["api_url"] if candidate else None,
        "tasteduel_vertex_requests_per_day": 50,
        "tasteduel_qloo_requests_per_day": 100,
        "tasteduel_release_migration_image": old["images"]["images"]["api"]["reference"],
        "tasteduel_release_migration_source_sha": old["images"]["source_sha"],
        "tasteduel_ops_cost_review_hash": old["cost_sha256"],
    }


def check_evidence(value: dict, manifest: dict, *, now: datetime | None = None) -> None:
    """Small focused hotfix checks, bound to the real candidate and source."""
    expected = {
        "kind",
        "status",
        "manifest_sha256",
        "source_sha",
        "api_revision",
        "web_revision",
        "checked_at_utc",
        "checks",
    }
    expected |= {"verification"}
    checks = {
        "synthetic_error_contracts",
        "retry_identity",
        "private_api",
        "secrecy",
        "keyboard",
        "mobile",
        "candidate_config",
    }
    try:
        timestamp = datetime.fromisoformat(value["checked_at_utc"].replace("Z", "+00:00"))
        valid = (
            set(value) == expected
            and value["kind"] == "hotfix-candidate-smoke"
            and value["status"] == "PASS"
            and value["manifest_sha256"] == digest(manifest)
            and value["source_sha"] == manifest["images"]["source_sha"]
            and all(
                value[actor + "_revision"] == manifest["candidate"][actor + "_revision"]
                for actor in ("api", "web")
            )
            and 0 <= ((now or datetime.now(timezone.utc)) - timestamp).total_seconds() <= 86400
            and value["verification"]
            in (
                {
                    "original_incident_cause": "unconfirmed",
                    "error_scenarios": "synthetic-contracts",
                    "live_generation": "genuine-agent",
                },
                {
                    "original_incident_cause": "unconfirmed",
                    "error_scenarios": "synthetic-contracts",
                    "live_generation": "deterministic-qloo",
                },
            )
            and set(value["checks"]) == checks
            and all(type(item) is bool and item is True for item in value["checks"].values())
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise PlanBlocked("HOTFIX_CURRENT_FOCUSED_CANDIDATE_EVIDENCE_REQUIRED")


def routes(manifest: dict, phase: str, actor: str) -> list[dict]:
    variables = phase_variables(manifest, phase)
    result = [
        {
            "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
            "percent": 100,
            "revision": variables[f"tasteduel_{actor}_traffic_revision"],
        }
    ]
    if phase == "hotfix-candidate":
        result.append(
            {
                "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                "percent": 0,
                "revision": manifest["candidate"][actor + "_revision"],
                "tag": manifest["candidate"]["tag"],
            }
        )
    return result


def audit_plan(plan: dict, manifest: dict, phase: str) -> dict:
    """Full root: exactly two existing services may update; everything else no-op."""
    validate_manifest(manifest)
    variables, images = phase_variables(manifest, phase), images_input(manifest["images"])
    entries = plan.get("resource_changes", [])
    records = {item.get("address"): item for item in entries}
    blocked = bool(plan.get("errored")) or len(records) != len(entries)
    required = {
        ADDRESSES["api"],
        ADDRESSES["web"],
        ADDRESSES["migrate"],
        ADDRESSES["api_web"],
        PUBLIC_WEB,
        *MONITORS,
    }
    blocked |= not required.issubset(records)
    api_uri = (records.get(ADDRESSES["api"], {}).get("change", {}).get("after") or {}).get("uri")
    # The real canonical API URI is known; tagged request targets must never
    # become ID-token audiences or arbitrary externally supplied hosts.
    blocked |= api_uri != API_URI
    actions = []
    for address, item in records.items():
        change = item.get("change", {})
        operation = change.get("actions")
        before, after = change.get("before") or {}, change.get("after") or {}
        if (
            after.get("role") == "roles/run.invoker"
            and after.get("member") in {"allUsers", "allAuthenticatedUsers"}
            and (
                after.get("name")
                in {"tasteduel-api", f"projects/{PROJECT}/locations/{REGION}/services/tasteduel-api"}
                or (after.get("project") == PROJECT and not after.get("name"))
            )
        ):
            blocked = True
        if address not in {ADDRESSES["api"], ADDRESSES["web"]}:
            safe = (operation == ["no-op"] and before == after) or (
                operation == ["read"] and item.get("mode") == "data"
            )
            if address in required:
                safe &= operation == ["no-op"] and before == after
            if address == PUBLIC_WEB:
                safe &= (
                    after.get("member") == "allUsers"
                    and after.get("role") == "roles/run.invoker"
                    and after.get("name")
                    in {"tasteduel-web", f"projects/{PROJECT}/locations/{REGION}/services/tasteduel-web"}
                    and after.get("project") == PROJECT
                    and after.get("location") == REGION
                )
            if address == ADDRESSES["api_web"]:
                safe &= (
                    after.get("member") == "serviceAccount:" + SA["web"]
                    and after.get("role") == "roles/run.invoker"
                    and after.get("name")
                    in {"tasteduel-api", f"projects/{PROJECT}/locations/{REGION}/services/tasteduel-api"}
                    and after.get("project") == PROJECT
                    and after.get("location") == REGION
                )
            if address == ADDRESSES["migrate"]:
                old = baseline_reference()
                safe &= safe_job(
                    after,
                    images_input(old["images"]),
                    ops_cost_hash=old["cost_sha256"],
                    ops_through=old["reviewed_through_utc"],
                )
            blocked |= not safe
            if operation != ["no-op"] and not safe:
                actions.append(
                    {"address": "outside_hotfix_scope", "actions": operation, "approved_scope": False}
                )
            continue
        actor = "api" if address == ADDRESSES["api"] else "web"
        normalized = deepcopy(after)
        normalized["traffic"] = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST", "percent": 100}]
        candidate = manifest["candidate"] if phase == "hotfix-candidate" else None
        env = normalized.get("template", [{}])[0].get("containers", [{}])[0].get("env", [])
        expected_before = deepcopy(before)
        expected_before["traffic"] = deepcopy(after.get("traffic"))
        old_env = {
            item["name"]: item
            for item in expected_before.get("template", [{}])[0].get("containers", [{}])[0].get("env", [])
        }
        overrides = (
            {
                "TASTEDUEL_ALLOWED_ORIGINS": json.dumps(
                    [ORIGIN] + ([candidate["origin"]] if candidate else []), separators=(",", ":")
                )
            }
            if actor == "api"
            else {
                "TASTEDUEL_WEB_ORIGINS": ORIGIN + ("," + candidate["origin"] if candidate else ""),
                "TASTEDUEL_API_URL": candidate["api_url"] if candidate else api_uri,
            }
        )
        try:
            prior_phase = {
                "hotfix-seal": "hotfix-candidate",
                "hotfix-promote": "hotfix-seal",
                "hotfix-rollback": "hotfix-promote",
                "hotfix-rollforward": "hotfix-rollback",
            }.get(phase)
            expected_routes = (
                routes(manifest, prior_phase, actor)
                if prior_phase
                else [
                    {
                        "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                        "percent": 100,
                        "revision": manifest["baseline"][actor + "_revision"],
                    }
                ]
            )
            actual_routes = sorted(
                [
                    {k: v for k, v in route.items() if v not in (None, "")}
                    for route in before.get("traffic", [])
                ],
                key=lambda x: x["percent"],
                reverse=True,
            )
            blocked |= actual_routes != expected_routes
            prior_revision = (
                manifest["baseline"]
                if phase == "hotfix-candidate"
                else manifest["candidate"]
                if phase == "hotfix-seal"
                else manifest["release"]
            )[actor + "_revision"]
            prior_images = (
                {actor: manifest["baseline"][actor + "_image"] for actor in ("api", "web")}
                if phase == "hotfix-candidate"
                else images
            )
            blocked |= (
                before.get("template", [{}])[0].get("revision") != prior_revision
                or before.get("template", [{}])[0].get("containers", [{}])[0].get("image")
                != prior_images[actor]
            )
            prior_candidate = manifest["candidate"] if phase == "hotfix-seal" else None
            prior_overrides = (
                {
                    "TASTEDUEL_ALLOWED_ORIGINS": json.dumps(
                        [ORIGIN] + ([prior_candidate["origin"]] if prior_candidate else []),
                        separators=(",", ":"),
                    )
                }
                if actor == "api"
                else {
                    "TASTEDUEL_WEB_ORIGINS": ORIGIN
                    + ("," + prior_candidate["origin"] if prior_candidate else ""),
                    "TASTEDUEL_API_URL": prior_candidate["api_url"] if prior_candidate else api_uri,
                }
            )
            blocked |= any(
                old_env.get(name, {}).get("value") != expected for name, expected in prior_overrides.items()
            )
            for item in env:
                if item["name"] in overrides:
                    if item.get("value") != overrides[item["name"]]:
                        blocked = True
                    item["value"] = (
                        json.dumps([ORIGIN], separators=(",", ":"))
                        if item["name"] == "TASTEDUEL_ALLOWED_ORIGINS"
                        else ORIGIN
                        if item["name"] == "TASTEDUEL_WEB_ORIGINS"
                        else api_uri
                    )
            if phase in {"hotfix-candidate", "hotfix-seal"}:
                for name, value in overrides.items():
                    old_env[name]["value"] = value
            safe = (
                operation == ["update"]
                and safe_service(
                    normalized,
                    actor,
                    images,
                    ORIGIN,
                    api_uri=api_uri,
                    unknown=change.get("after_unknown"),
                    vertex_limit="50",
                    qloo_limit="100",
                )
                and normalized["template"][0]["containers"][0].get("command") in (None, [])
                and normalized["template"][0]["containers"][0].get("args") in (None, [])
                and after.get("template", [{}])[0].get("revision")
                == variables[f"tasteduel_{actor}_candidate_revision"]
                and after.get("labels", {}).get("source_ref") == images["source_sha"][:12]
                and sorted(
                    [
                        {k: v for k, v in route.items() if v not in (None, "")}
                        for route in after.get("traffic", [])
                    ],
                    key=lambda x: x["percent"],
                    reverse=True,
                )
                == routes(manifest, phase, actor)
                and image_only_update(expected_before, after, actor=actor)
            )
            if phase not in {"hotfix-candidate", "hotfix-seal"}:
                left, right = deepcopy(before), deepcopy(after)
                left.pop("traffic", None)
                right.pop("traffic", None)
                safe &= left == right
        except (KeyError, TypeError, IndexError):
            safe = False
        blocked |= not safe
        if operation != ["no-op"]:
            actions.append({"address": address, "actions": operation, "approved_scope": bool(safe)})
    return {
        "status": "BLOCKED" if blocked else "REVIEWABLE",
        "phase": phase,
        "manifest_sha256": digest(manifest),
        "actions": actions,
        "public_access": True,
        "public_preview": phase == "hotfix-candidate",
        "requires_independent_review": True,
        "provider_attributes_exported": False,
    }


def reviewed_inputs(cost: dict, manifest: dict, images: dict, phase: str, tester: str) -> dict:
    if not re.fullmatch(r"user:[^\s@]+@[^\s@]+", tester):
        raise PlanBlocked("HOTFIX_EXACT_EXISTING_TESTER_REQUIRED")
    validate_manifest(manifest)
    if images_input(images) != images_input(manifest["images"]):
        raise PlanBlocked("HOTFIX_PUBLISHED_IMAGE_RECORD_MISMATCH")
    if (
        digest(cost) != manifest["cost_sha256"]
        or cost["reviewed_through_utc"] != manifest["reviewed_through_utc"]
    ):
        raise PlanBlocked("HOTFIX_COST_REVIEW_CHANGED")
    return {
        **foundation.approved_variables(cost),
        **phase_variables(manifest, phase),
        "tasteduel_candidate_tester": tester,
    }


def verify_saved(
    directory: Path, review: dict, approval: dict, cost: dict, manifest: dict, images: dict, tester: str
) -> dict:
    """Pure local review guard; no credentials, cloud query or apply occurs here."""
    if (
        directory.parent != (ROOT / ".data/tasteduel-cloud-review").resolve()
        or review.get("status") != "REVIEWABLE"
        or review.get("phase") not in PHASES
        or approval.get("independent_review") != "PASS"
    ):
        raise PlanBlocked("HOTFIX_EXACT_INDEPENDENT_SAVED_PLAN_REQUIRED")
    for field in ("source_sha256", "plan_sha256", "image_source_sha", "phase", "manifest_sha256"):
        if approval.get(field) != review.get(field):
            raise PlanBlocked("HOTFIX_APPROVAL_HASH_MISMATCH")
    if (
        source_hash(directory) != review["source_sha256"]
        or source_hash(ROOT / "infra/terraform") != review["source_sha256"]
        or hashlib.sha256((directory / "release.tfplan").read_bytes()).hexdigest() != review["plan_sha256"]
    ):
        raise PlanBlocked("HOTFIX_SOURCE_OR_SAVED_BINARY_CHANGED")
    if (
        digest(manifest) != review["manifest_sha256"]
        or images_input(images)["source_sha"] != review["image_source_sha"]
        or cost["reviewed_total_usd"] != review.get("reviewed_total_usd")
    ):
        raise PlanBlocked("HOTFIX_REVIEWED_ARTIFACT_CHANGED")
    if (directory / "apply-journal.json").exists():
        raise PlanBlocked("HOTFIX_PRIOR_ATTEMPT_REQUIRES_RECOVERY_REVIEW")
    variables = reviewed_inputs(cost, manifest, images, review["phase"], tester)
    if review["phase"] in {"hotfix-seal", "hotfix-promote"}:
        check_evidence(json.loads((directory / "smoke-evidence.json").read_text(encoding="utf-8")), manifest)
    return variables


def verify_plan_inputs(plan: dict, expected: dict) -> None:
    actual = {key: value.get("value") for key, value in plan.get("variables", {}).items()}
    if any(
        key not in actual or not saved_input_matches(actual.get(key), value)
        for key, value in expected.items()
    ):
        raise PlanBlocked("HOTFIX_SAVED_INPUTS_CHANGED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planner = commands.add_parser("plan", help="Create a private full-root saved plan; no apply")
    planner.add_argument("--phase", choices=PHASES, required=True)
    planner.add_argument("--smoke-evidence", type=Path)
    applier = commands.add_parser("apply", help="Apply only an independently reviewed saved binary once")
    applier.add_argument("--directory", type=Path, required=True)
    for command in (planner, applier):
        command.add_argument("--review", type=Path, required=True)
        command.add_argument("--images", type=Path, required=True)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--tester", required=True)
    args = parser.parse_args()
    journal, owned_journal = None, False
    try:
        cost = json.loads(args.review.read_text(encoding="utf-8"))
        images = json.loads(args.images.read_text(encoding="utf-8"))
        manifest = validate_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
        if args.command == "plan":
            variables = reviewed_inputs(cost, manifest, images, args.phase, args.tester)
            evidence = None
            if args.phase in {"hotfix-seal", "hotfix-promote"}:
                if args.smoke_evidence is None:
                    raise PlanBlocked("HOTFIX_CANDIDATE_SMOKE_REQUIRED")
                evidence = json.loads(args.smoke_evidence.read_text(encoding="utf-8"))
                check_evidence(evidence, manifest)
            directory = (
                ROOT
                / ".data/tasteduel-cloud-review"
                / ("release-" + args.phase + "-plan-" + secrets.token_hex(8))
            )
            source = foundation.source_snapshot(directory)
            adc, environment = foundation.adc_path(), credential_environment(variables)
            foundation.terraform(
                directory,
                adc,
                environment,
                "init",
                "-input=false",
                "-lockfile=readonly",
                "-backend-config=bucket=" + foundation.BACKEND_BUCKET,
                "-backend-config=prefix=" + foundation.BACKEND_PREFIX,
            )
            foundation.terraform(
                directory,
                adc,
                environment,
                "plan",
                "-input=false",
                "-no-color",
                "-lock-timeout=60s",
                "-out=release.tfplan",
            )
            plan = json.loads(
                foundation.terraform(directory, adc, environment, "show", "-json", "release.tfplan")
            )
            verify_plan_inputs(plan, variables)
            result = audit_plan(plan, manifest, args.phase)
            result.update(
                source_sha256=source,
                plan_sha256=hashlib.sha256((directory / "release.tfplan").read_bytes()).hexdigest(),
                image_source_sha=images_input(images)["source_sha"],
                reviewed_total_usd=cost["reviewed_total_usd"],
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                applied=False,
            )
            for name, value in (("hotfix-manifest.json", manifest), ("review.json", result)):
                with (directory / name).open("x", encoding="utf-8") as handle:
                    json.dump(value, handle, indent=2)
            if evidence:
                with (directory / "smoke-evidence.json").open("x", encoding="utf-8") as handle:
                    json.dump(evidence, handle, indent=2)
            print(
                json.dumps(
                    {"status": result["status"], "review": str(directory / "review.json"), "applied": False}
                )
            )
            return 0 if result["status"] == "REVIEWABLE" else 2
        directory = args.directory.resolve()
        if directory.parent != (ROOT / ".data/tasteduel-cloud-review").resolve():
            raise PlanBlocked("HOTFIX_PLAN_OUTSIDE_PRIVATE_BOUNDARY")
        review = json.loads((directory / "review.json").read_text(encoding="utf-8"))
        approval = json.loads((directory / "independent-approval.json").read_text(encoding="utf-8"))
        saved_manifest = json.loads((directory / "hotfix-manifest.json").read_text(encoding="utf-8"))
        if saved_manifest != manifest:
            raise PlanBlocked("HOTFIX_MANIFEST_CHANGED_AFTER_PLAN")
        variables = verify_saved(directory, review, approval, cost, manifest, images, args.tester)
        adc = foundation.adc_path()
        plan = json.loads(foundation.terraform(directory, adc, {}, "show", "-json", "release.tfplan"))
        verify_plan_inputs(plan, variables)
        if audit_plan(plan, manifest, review["phase"])["status"] != "REVIEWABLE":
            raise PlanBlocked("HOTFIX_SAVED_PLAN_SCOPE_FAILED")
        # Preserve established pinned credentials only, never rotate or write
        # payloads. The strict plan audit requires every secret/SQL input no-op.
        environment = credential_environment(variables)
        journal = {
            "status": "STARTED",
            "phase": review["phase"],
            "plan_sha256": review["plan_sha256"],
            "source_sha256": review["source_sha256"],
            "manifest_sha256": review["manifest_sha256"],
            "image_source_sha": review["image_source_sha"],
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "credential_payload_files": False,
            "automatic_retry": False,
            "public_product_access": True,
        }
        with (directory / "apply-journal.json").open("x", encoding="utf-8") as handle:
            json.dump(journal, handle, indent=2)
        owned_journal = True
        result = subprocess.run(
            apply_command(directory, adc, environment),
            env={**os.environ, **environment},
            capture_output=True,
            text=True,
        )
        journal.update(
            status="APPLIED" if result.returncode == 0 else "FAILED_REQUIRES_RECOVERY",
            completed_at_utc=datetime.now(timezone.utc).isoformat(),
            exit_code=result.returncode,
        )
        (directory / "apply-journal.json").write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(journal))
        return 0 if result.returncode == 0 else 2
    except Exception as failure:
        if owned_journal:
            journal.update(
                status="FAILED_REQUIRES_RECOVERY", completed_at_utc=datetime.now(timezone.utc).isoformat()
            )
            (directory / "apply-journal.json").write_text(
                json.dumps(journal, indent=2) + "\n", encoding="utf-8"
            )
        reason = (
            str(failure)
            if isinstance(failure, PlanBlocked)
            else "HOTFIX_RELEASE_FAILED_" + type(failure).__name__
        )
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason_code": reason,
                    "automatic_retry": False,
                    "execution_started": owned_journal,
                    "applied": None if owned_journal else False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

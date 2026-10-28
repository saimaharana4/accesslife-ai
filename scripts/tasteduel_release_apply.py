"""Apply exactly one independently approved full-root release saved plan.

No generic apply, targeting, automatic retry, credential files or provider logs.
An interrupted/failed attempt requires a separate recovery review.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

import tasteduel_foundation_plan as foundation
from tasteduel_foundation_apply import source_hash
from tasteduel_release_plan import PHASES, PRODUCTION_PHASES, audit_release, credential_environment, images_input


def verify(directory: Path, review: dict, approval: dict, cost: dict) -> dict:
    if review.get("status") != "REVIEWABLE" or approval.get("independent_review") != "PASS":
        raise foundation.PlanBlocked("INDEPENDENT_RELEASE_REVIEW_REQUIRED")
    for field in ("source_sha256", "plan_sha256", "image_source_sha", "phase"):
        if approval.get(field) != review.get(field):
            raise foundation.PlanBlocked("RELEASE_APPROVAL_HASH_OR_PHASE_MISMATCH")
    if review.get("phase") in PRODUCTION_PHASES and approval.get("manifest_sha256") != review.get("manifest_sha256"):
        raise foundation.PlanBlocked("PRODUCTION_MANIFEST_APPROVAL_MISMATCH")
    if review.get("phase") not in (*PHASES, *PRODUCTION_PHASES):
        raise foundation.PlanBlocked("RELEASE_PHASE_INVALID")
    if source_hash(directory) != review["source_sha256"] or source_hash(foundation.ROOT / "infra/terraform") != review["source_sha256"]:
        raise foundation.PlanBlocked("SOURCE_CHANGED_AFTER_RELEASE_REVIEW")
    if hashlib.sha256((directory / "release.tfplan").read_bytes()).hexdigest() != review["plan_sha256"]:
        raise foundation.PlanBlocked("RELEASE_SAVED_PLAN_CHANGED")
    if (directory / "apply-journal.json").exists():
        raise foundation.PlanBlocked("PRIOR_RELEASE_ATTEMPT_REQUIRES_RECOVERY_REVIEW")
    variables = foundation.approved_variables(cost)
    if variables["reviewed_total_usd"] != review["reviewed_total_usd"]:
        raise foundation.PlanBlocked("COST_CHANGED_AFTER_RELEASE_REVIEW")
    return variables


def saved_input_matches(actual, expected) -> bool:
    # Terraform 1.13's plan JSON can retain TF_VAR scalar input strings before
    # type conversion. Decode only an expected boolean/number, never strings,
    # credential values or provider attributes.
    if type(expected) in (bool, int, float) and isinstance(actual, str):
        try:
            actual = json.loads(actual)
        except (ValueError, TypeError):
            return False
    if type(expected) is bool:
        return type(actual) is bool and actual == expected
    if type(expected) in (int, float):
        return type(actual) in (int, float) and actual == expected
    return type(actual) is type(expected) and actual == expected


def plan_inputs(plan: dict, review: dict, images: dict, tester: str) -> dict:
    actual = {key: item.get("value") for key, item in plan.get("variables", {}).items()}
    expected = {"tasteduel_release_migration_enabled": True,
                "tasteduel_release_services_enabled": review["phase"] != "migration",
                "tasteduel_release_api_image": images["api"], "tasteduel_release_web_image": images["web"],
                "tasteduel_release_source_sha": images["source_sha"], "tasteduel_candidate_tester": tester}
    if images["source_sha"] != review["image_source_sha"] or any(not saved_input_matches(actual.get(key), value) for key, value in expected.items()):
        raise foundation.PlanBlocked("RELEASE_SAVED_INPUTS_MISMATCH")
    return expected


def apply_command(directory: Path, adc: Path, environment: dict) -> list[str]:
    command = ["docker", "run", "--rm", "--mount", f"type=bind,source={directory},target=/work",
               "--mount", f"type=bind,source={adc},target=/adc.json,readonly", "--workdir", "/work",
               "--env", "GOOGLE_APPLICATION_CREDENTIALS=/adc.json"]
    for key in environment:
        command += ["--env", key]
    return command + [foundation.IMAGE, "apply", "-json", "-input=false", "-lock-timeout=60s", "release.tfplan"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--cost", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--tester", required=True)
    parser.add_argument("--project-number", required=True)
    args = parser.parse_args()
    directory, journal, journal_owned = args.directory.resolve(), None, False
    try:
        if directory.parent != (foundation.ROOT / ".data/tasteduel-cloud-review").resolve():
            raise foundation.PlanBlocked("RELEASE_PLAN_OUTSIDE_PRIVATE_BOUNDARY")
        review = json.loads((directory / "review.json").read_text(encoding="utf-8"))
        approval = json.loads((directory / "independent-approval.json").read_text(encoding="utf-8"))
        cost = json.loads(args.cost.read_text(encoding="utf-8"))
        variables = verify(directory, review, approval, cost)
        images = images_input(json.loads(args.images.read_text(encoding="utf-8")))
        manifest = None
        if review["phase"] in PRODUCTION_PHASES:
            from tasteduel_production_release import audit_production, check_evidence, digest, phase_images, phase_variables, validate_manifest

            manifest = validate_manifest(json.loads((directory / "production-manifest.json").read_text(encoding="utf-8")))
            if images_input(manifest["images"]) != images:
                raise foundation.PlanBlocked("PRODUCTION_PUBLISHED_IMAGE_RECORD_MISMATCH")
            if digest(manifest) != review.get("manifest_sha256") or digest(cost) != manifest["cost_sha256"]:
                raise foundation.PlanBlocked("PRODUCTION_MANIFEST_OR_COST_CHANGED_AFTER_REVIEW")
            if review["phase"] == "production-promote":
                check_evidence(json.loads((directory / "smoke-evidence.json").read_text(encoding="utf-8")), manifest, kind="sealed-smoke")
            images = phase_images(manifest, review["phase"])
        adc = foundation.adc_path()
        plan = json.loads(foundation.terraform(directory, adc, {}, "show", "-json", "release.tfplan"))
        saved_variables = {key: item.get("value") for key, item in plan.get("variables", {}).items()}
        if any(not saved_input_matches(saved_variables.get(key), value) for key, value in variables.items()):
            raise foundation.PlanBlocked("COST_OR_FOUNDATION_INPUTS_CHANGED_AFTER_PLAN")
        variables.update(plan_inputs(plan, review, images, args.tester))
        if manifest:
            declared = phase_variables(manifest, review["phase"])
            if any(not saved_input_matches(saved_variables.get(key), value) for key, value in declared.items()):
                raise foundation.PlanBlocked("PRODUCTION_SAVED_INPUTS_MISMATCH")
            variables.update(declared)
            if review["phase"] == "production-observability":
                from tasteduel_observability_plan import audit_observability

                audited = audit_observability(plan, manifest)
            else:
                audited = audit_production(plan, manifest, review["phase"])
        else:
            audited = audit_release(plan, phase=review["phase"], images=images, tester=args.tester, project_number=args.project_number)
        if audited["status"] != "REVIEWABLE":
            raise foundation.PlanBlocked("RELEASE_SAVED_PLAN_SCOPE_FAILED")
        # Preserve actual established SQL passwords from pinned SM URLs. Never
        # regenerate revision-1 credentials for these already-applied resources.
        environment = credential_environment(variables)
        journal = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "status": "STARTED",
                   "phase": review["phase"], "plan_sha256": review["plan_sha256"],
                   "source_sha256": review["source_sha256"], "image_source_sha": review["image_source_sha"],
                   "credential_payload_files": False, "public_product_access": bool(manifest and variables["tasteduel_public_enabled"])}
        # Exclusive creation also prevents two local invocations of this plan.
        with (directory / "apply-journal.json").open("x", encoding="utf-8") as handle:
            json.dump(journal, handle, indent=2)
        journal_owned = True
        result = subprocess.run(apply_command(directory, adc, environment),
                                env={**os.environ, **environment}, capture_output=True, text=True)
        journal.update({"status": "APPLIED" if result.returncode == 0 else "FAILED_REQUIRES_RECOVERY",
                        "completed_at_utc": datetime.now(timezone.utc).isoformat(), "exit_code": result.returncode})
        (directory / "apply-journal.json").write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(journal))
        return 0 if result.returncode == 0 else 2
    except Exception as failure:
        reason = str(failure) if isinstance(failure, foundation.PlanBlocked) else "RELEASE_APPLY_FAILED_" + type(failure).__name__
        if journal_owned and journal is not None and (directory / "apply-journal.json").exists():
            journal.update({"status": "FAILED_REQUIRES_RECOVERY", "completed_at_utc": datetime.now(timezone.utc).isoformat()})
            (directory / "apply-journal.json").write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "BLOCKED", "reason_code": reason, "automatic_retry": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

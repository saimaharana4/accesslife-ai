"""Schema-changing named-duel release: strict full-root, one-shot saved plans.

The bridge is deployed before migration. Cleanup is created paused with the
bridge, so rollback retains the admission/hard-close configuration. No SQL,
secret, existing IAM, provider allowance or unrelated resource may change.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from urllib.request import Request, urlopen

import tasteduel_foundation_plan as foundation
from tasteduel_foundation_apply import source_hash
from tasteduel_foundation_plan import PROJECT, REGION, ROOT, PlanBlocked
from tasteduel_hotfix_release import API_URI, verify_plan_inputs
from tasteduel_observability_plan import DASHBOARD, MONITORS, PUBLIC_WEB, dashboard_document, normalized_dashboard
from tasteduel_production_release import ORIGIN, digest, revision
from tasteduel_release_apply import apply_command
from tasteduel_release_images import REPOSITORY, verified_ci
from tasteduel_release_plan import (
    ADDRESSES, SA, credential_environment, env_values, image_only_update,
    images_input, safe_job, safe_service,
)

PHASES = (
    "bridge-candidate", "bridge-seal", "bridge-promote", "migration-pin",
    "feature-candidate", "feature-seal", "feature-promote", "cleanup-paused",
    "cleanup-resume", "feature-rollback", "feature-rollforward", "final-check",
    "feature-recheck-candidate",
)
PREVIOUS = {
    "bridge-candidate": None, "bridge-seal": "bridge-candidate",
    "bridge-promote": "bridge-seal", "migration-pin": "bridge-promote",
    "feature-candidate": "migration-pin", "feature-seal": "feature-candidate",
    "feature-promote": "feature-seal", "cleanup-paused": "feature-promote",
    "cleanup-resume": "cleanup-paused", "feature-rollback": "cleanup-resume",
    "feature-rollforward": "feature-rollback",
    "final-check": "feature-rollforward",
    "feature-recheck-candidate": "feature-seal",
}
CLEANUP = {
    "sa": "google_service_account.tasteduel_cleanup_invoker[0]",
    "job": "google_cloud_run_v2_job.tasteduel_cleanup[0]",
    "iam": "google_cloud_run_v2_job_iam_member.tasteduel_cleanup_invoker[0]",
    "schedule": "google_cloud_scheduler_job.tasteduel_cleanup[0]",
    "failure": "google_monitoring_alert_policy.tasteduel_cleanup_failure[0]",
    "metric": "google_logging_metric.tasteduel_cleanup_heartbeat[0]",
    "missing": "google_monitoring_alert_policy.tasteduel_cleanup_missing[0]",
}
INVOKER = f"tasteduel-cleanup-invoker@{PROJECT}.iam.gserviceaccount.com"


def baseline_reference():
    return json.loads((ROOT / "infra/releases/production-hotfix-2026-10-29.json").read_text(encoding="utf-8"))


def validate_manifest(value):
    required = {"version", "kind", "project", "region", "origin", "baseline_manifest_sha256",
                "baseline", "bridge", "feature", "schema", "cost_sha256", "reviewed_through_utc",
                "preview_exposure"}
    if (set(value) != required or type(value["version"]) is not int or value["version"] != 1
            or value["kind"] != "named-duels-schema-release" or value["project"] != PROJECT
            or value["region"] != REGION or value["origin"] != ORIGIN
            or value["schema"] != {"from": "td0011", "to": "td0014", "backward_compatible": True}
            or value["preview_exposure"] != "public-tag-intentionally-reachable"
            or not re.fullmatch(r"[a-f0-9]{64}", value["cost_sha256"])):
        raise PlanBlocked("NAMED_MANIFEST_BOUNDARY_INVALID")
    old = baseline_reference()
    expected = {key: old[key] for key in ("source_sha", "api_revision", "web_revision")}
    expected.update({actor + "_image": foundation.REGION + "-docker.pkg.dev/" + PROJECT
                     + "/accesslife/tasteduel-" + actor + "@" + old[actor + "_image_digest"] for actor in ("api", "web")})
    if value["baseline_manifest_sha256"] != digest(old) or value["baseline"] != expected:
        raise PlanBlocked("NAMED_RECORDED_BASELINE_REQUIRED")
    horizon = datetime.fromisoformat(value["reviewed_through_utc"].replace("Z", "+00:00"))
    if horizon != foundation.MINIMUM_HORIZON:
        raise PlanBlocked("NAMED_EXACT_OPERATING_HORIZON_REQUIRED")
    sources = {old["source_sha"]}
    names = {actor: {old[actor + "_revision"]} for actor in ("api", "web")}
    for stage in ("bridge", "feature"):
        item = value[stage]
        if set(item) != {"images", "candidate", "release"}:
            raise PlanBlocked("NAMED_IMAGE_AND_REVISION_FIELDS_REQUIRED")
        images = images_input(item["images"])
        if images["source_sha"] in sources:
            raise PlanBlocked("NAMED_DISTINCT_GREEN_SOURCE_REQUIRED")
        sources.add(images["source_sha"])
        if set(item["candidate"]) != {"api_revision", "web_revision", "tag", "origin", "api_url"} or set(item["release"]) != {"api_revision", "web_revision"}:
            raise PlanBlocked("NAMED_EXACT_REVISIONS_REQUIRED")
        candidate = item["candidate"]
        tag = candidate["tag"]
        if (not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", tag)
                or candidate["origin"] != f"https://{tag}---tasteduel-web-dfthmgvvaa-el.a.run.app"
                or candidate["api_url"] != f"https://{tag}---tasteduel-api-dfthmgvvaa-el.a.run.app"):
            raise PlanBlocked("NAMED_EXACT_SERVICE_TAGS_REQUIRED")
        for actor in ("api", "web"):
            for kind in ("candidate", "release"):
                name = item[kind][actor + "_revision"]
                if not revision(name, actor) or name in names[actor]:
                    raise PlanBlocked("NAMED_DISTINCT_IMMUTABLE_REVISIONS_REQUIRED")
                names[actor].add(name)
    if value["bridge"]["candidate"]["tag"] == value["feature"]["candidate"]["tag"]:
        raise PlanBlocked("NAMED_DISTINCT_TAGS_REQUIRED")
    return deepcopy(value)


def stage_for(phase):
    return "bridge" if phase.startswith("bridge-") or phase == "migration-pin" else "feature"


def phase_variables(manifest, phase):
    if phase not in PHASES:
        raise PlanBlocked("NAMED_PHASE_INVALID")
    stage = stage_for(phase)
    selected = manifest[stage]
    images = images_input(selected["images"])
    candidate = selected["candidate"] if phase.endswith("-candidate") else None
    template = candidate or selected["release"]
    target = (manifest["baseline"] if phase in {"bridge-candidate", "bridge-seal"}
              else manifest["bridge"]["release"] if phase in {"bridge-promote", "migration-pin", "feature-candidate", "feature-recheck-candidate", "feature-seal", "feature-rollback"}
              else manifest["feature"]["release"])
    migration = images_input(manifest["feature"]["images"])
    # Before migration-pin preserve the exact existing migration job image/source.
    old = json.loads((ROOT / "infra/releases/production-2026-10-28.json").read_text(encoding="utf-8"))
    old_images = images_input(old["images"])
    pinned = phase not in {"bridge-candidate", "bridge-seal", "bridge-promote"}
    return {
        "tasteduel_release_migration_enabled": True, "tasteduel_release_services_enabled": True,
        "tasteduel_public_enabled": True, "tasteduel_observability_enabled": True,
        "tasteduel_public_hotfix_preview": bool(candidate),
        "tasteduel_release_api_image": images["api"], "tasteduel_release_web_image": images["web"],
        "tasteduel_release_source_sha": images["source_sha"],
        "tasteduel_api_traffic_revision": target["api_revision"], "tasteduel_web_traffic_revision": target["web_revision"],
        "tasteduel_api_candidate_revision": template["api_revision"], "tasteduel_web_candidate_revision": template["web_revision"],
        "tasteduel_candidate_tag": candidate["tag"] if candidate else None,
        "tasteduel_candidate_origin": candidate["origin"] if candidate else None,
        "tasteduel_candidate_api_url": candidate["api_url"] if candidate else None,
        "tasteduel_vertex_requests_per_day": 50, "tasteduel_qloo_requests_per_day": 100,
        "tasteduel_release_migration_image": migration["api"] if pinned else old_images["api"],
        "tasteduel_release_migration_source_sha": migration["source_sha"] if pinned else old_images["source_sha"],
        "tasteduel_ops_cost_review_hash": manifest["cost_sha256"],
        "tasteduel_cleanup_enabled": True,
        "tasteduel_cleanup_paused": phase not in {"cleanup-resume", "feature-rollback", "feature-rollforward", "final-check"},
    }


def routes(manifest, phase, actor):
    if phase is None:
        target = manifest["baseline"][actor + "_revision"]
        candidate = None
    else:
        values = phase_variables(manifest, phase)
        target = values[f"tasteduel_{actor}_traffic_revision"]
        candidate = manifest[stage_for(phase)]["candidate"] if phase.endswith("-candidate") else None
    result = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION", "percent": 100, "revision": target}]
    if candidate:
        result.append({"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION", "percent": 0,
                       "revision": candidate[actor + "_revision"], "tag": candidate["tag"]})
    return result


def clean_routes(value):
    return sorted([{k: v for k, v in row.items() if v not in (None, "")} for row in value], key=lambda row: -row["percent"])


def expected_cutoffs(manifest):
    end = datetime.fromisoformat(manifest["reviewed_through_utc"].replace("Z", "+00:00"))
    return {"TASTEDUEL_SESSION_ADMISSION_CLOSES_AT": (end - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
            "TASTEDUEL_SESSION_HARD_CLOSES_AT": (end - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")}


def service_safe(after, actor, manifest, phase):
    normalized = deepcopy(after)
    values = phase_variables(manifest, phase)
    selected = manifest[stage_for(phase)]
    images = images_input(selected["images"])
    candidate = selected["candidate"] if phase.endswith("-candidate") else None
    container = normalized["template"][0]["containers"][0]
    actual = env_values(container)
    expected = ({"TASTEDUEL_ALLOWED_ORIGINS": json.dumps([ORIGIN] + ([candidate["origin"]] if candidate else []), separators=(",", ":"))}
                if actor == "api" else {"TASTEDUEL_WEB_ORIGINS": ORIGIN + ("," + candidate["origin"] if candidate else ""),
                                       "TASTEDUEL_API_URL": candidate["api_url"] if candidate else API_URI})
    if actor == "api":
        expected.update(expected_cutoffs(manifest))
    if actual is None or any(actual.get(k) != v for k, v in expected.items()):
        return False
    container["env"] = [row for row in container["env"] if row["name"] not in expected_cutoffs(manifest)]
    for row in container["env"]:
        if row["name"] in expected:
            row["value"] = json.dumps([ORIGIN], separators=(",", ":")) if row["name"] == "TASTEDUEL_ALLOWED_ORIGINS" else API_URI if row["name"] == "TASTEDUEL_API_URL" else ORIGIN
    normalized["traffic"] = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST", "percent": 100}]
    return (after.get("uri") == (API_URI if actor == "api" else "https://tasteduel-web-dfthmgvvaa-el.a.run.app")
            and clean_routes(after.get("traffic", [])) == routes(manifest, phase, actor)
            and after["template"][0].get("revision") == values[f"tasteduel_{actor}_candidate_revision"]
            and after.get("labels", {}).get("source_ref") == images["source_sha"][:12]
            and container.get("command") in (None, []) and container.get("args") in (None, [])
            and safe_service(normalized, actor, images, ORIGIN, api_uri=API_URI, vertex_limit="50", qloo_limit="100"))


def service_change_safe(before, after, actor, manifest, phase):
    if not service_safe(after, actor, manifest, phase):
        return False
    prior = PREVIOUS[phase]
    if clean_routes(before.get("traffic", [])) != routes(manifest, prior, actor):
        return False
    if prior is None:
        if (before["template"][0].get("revision") != manifest["baseline"][actor + "_revision"]
                or before["template"][0]["containers"][0].get("image") != manifest["baseline"][actor + "_image"]):
            return False
    elif not service_safe(before, actor, manifest, prior):
        return False
    left, right = deepcopy(before), deepcopy(after)
    left["traffic"] = deepcopy(right["traffic"])
    # Only these explicitly checked environment changes may accompany images.
    for value in (left, right):
        container = value["template"][0]["containers"][0]
        container["env"] = [row for row in container["env"] if row["name"] not in {
            "TASTEDUEL_ALLOWED_ORIGINS", "TASTEDUEL_WEB_ORIGINS", "TASTEDUEL_API_URL", *expected_cutoffs(manifest)}]
    if phase not in {"bridge-candidate", "bridge-seal", "feature-candidate", "feature-recheck-candidate", "feature-seal"}:
        left.pop("traffic", None)
        right.pop("traffic", None)
        return left == right
    return image_only_update(left, right, actor=actor)


def cleanup_safe(key, after, manifest, phase):
    """Validate fixed unattended resources; no generic IAM/scheduler authority."""
    if after.get("project") != PROJECT:
        return False
    values = phase_variables(manifest, phase)
    if key == "sa":
        return (after.get("account_id") == "tasteduel-cleanup-invoker" and after.get("disabled") in (None, False)
                and (after.get("email") == INVOKER or (phase == "bridge-candidate" and after.get("email") is None)))
    if key == "iam":
        return (after.get("name") in {"tasteduel-cleanup", f"projects/{PROJECT}/locations/{REGION}/jobs/tasteduel-cleanup"}
                and after.get("location") == REGION and after.get("role") == "roles/run.invoker"
                and after.get("member") == "serviceAccount:" + INVOKER and not after.get("condition"))
    if key == "job":
        normalized = deepcopy(after)
        if after.get("name") != "tasteduel-cleanup":
            return False
        task = normalized["template"][0]["template"][0]
        container = task["containers"][0]
        if task.get("timeout") != "180s" or task.get("max_retries") != 1 or container.get("command") != ["python", "-m", "tasteduel.cleanup"] or container.get("args") not in ([], None):
            return False
        task["timeout"], task["max_retries"] = "300s", 0
        container["command"], container["args"] = ["python", "-m", "tasteduel.operations"], ["migrate"]
        normalized["name"] = "tasteduel-migrate"
        return safe_job(normalized, {"api": values["tasteduel_release_migration_image"]}, ops_cost_hash=manifest["cost_sha256"], ops_through=manifest["reviewed_through_utc"])
    if key == "schedule":
        target = after.get("http_target", [])
        retries = after.get("retry_config", [])
        return (after.get("name") == "tasteduel-cleanup" and after.get("region") == REGION
                and after.get("schedule") == "*/10 * * * *" and after.get("time_zone") == "Etc/UTC"
                and after.get("paused") is values["tasteduel_cleanup_paused"] and after.get("attempt_deadline") == "30s"
                and len(target) == 1 and target[0].get("uri") == f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}/jobs/tasteduel-cleanup:run"
                and target[0].get("http_method") == "POST" and target[0].get("body") == "e30="
                and target[0].get("headers") == {"Content-Type": "application/json"}
                and target[0].get("oauth_token") == [{"service_account_email": INVOKER, "scope": "https://www.googleapis.com/auth/cloud-platform"}]
                and not target[0].get("oidc_token") and len(retries) == 1
                and {k: retries[0].get(k) for k in ("retry_count", "max_retry_duration", "min_backoff_duration", "max_backoff_duration", "max_doublings")} == {
                    "retry_count": 2, "max_retry_duration": "600s", "min_backoff_duration": "60s", "max_backoff_duration": "300s", "max_doublings": 2})
    if key == "metric":
        return (after.get("name") == "tasteduel_cleanup_completed"
                and after.get("filter") == 'resource.type="cloud_run_job" resource.labels.job_name="tasteduel-cleanup" (jsonPayload.status="PASS" OR jsonPayload.status="BACKLOG")'
                and len(after.get("metric_descriptor", [])) == 1
                and all(after["metric_descriptor"][0].get(k) == v for k, v in {"metric_kind": "DELTA", "value_type": "INT64", "unit": "1"}.items()))
    if key in {"failure", "missing"}:
        if after.get("combiner") != "OR" or after.get("enabled") is not True or after.get("notification_channels") not in ([], None):
            return False
        conditions = after.get("conditions", [])
        if len(conditions) != 1:
            return False
        if key == "failure":
            logs = conditions[0].get("condition_matched_log", [])
            strategy = after.get("alert_strategy", [])
            return (len(logs) == 1 and logs[0].get("filter") == 'resource.type="cloud_run_job" resource.labels.job_name="tasteduel-cleanup" (jsonPayload.status="FAIL" OR jsonPayload.oldest_expired_session_seconds>1800)'
                    and len(strategy) == 1 and strategy[0].get("auto_close") == "3600s"
                    and strategy[0].get("notification_rate_limit") == [{"period": "1800s"}])
        absent = conditions[0].get("condition_absent", [])
        aggregations = absent[0].get("aggregations", []) if len(absent) == 1 else []
        # The pinned provider emits null for omitted grouping/reducer in a
        # create plan, then []/"" after refresh. These observed empty values
        # apply no grouping/reduction; never accept a nonempty setting.
        aggregation_safe = (len(aggregations) == 1
            and set(aggregations[0]) == {"alignment_period", "per_series_aligner", "cross_series_reducer", "group_by_fields"}
            and aggregations[0].get("alignment_period") == "600s"
            and aggregations[0].get("per_series_aligner") == "ALIGN_SUM"
            and aggregations[0].get("cross_series_reducer") in (None, "")
            and aggregations[0].get("group_by_fields") in (None, []))
        return (len(absent) == 1 and absent[0].get("filter") == 'resource.type="cloud_run_job" metric.type="logging.googleapis.com/user/tasteduel_cleanup_completed"'
                and absent[0].get("duration") == "1800s" and aggregation_safe)
    return False


def audit_plan(plan, manifest, phase):
    validate_manifest(manifest)
    values = phase_variables(manifest, phase)
    entries = plan.get("resource_changes", [])
    records = {row.get("address"): row for row in entries}
    required = {ADDRESSES[k] for k in ("api", "web", "migrate", "api_web")} | {PUBLIC_WEB, *MONITORS, *CLEANUP.values()}
    blocked = bool(plan.get("errored")) or len(records) != len(entries) or not required.issubset(records)
    actions = []
    for address, row in records.items():
        change = row.get("change", {})
        operation, before, after = change.get("actions"), change.get("before") or {}, change.get("after") or {}
        safe = operation == ["no-op"] and before == after
        if operation == ["read"] and row.get("mode") == "data":
            safe = True
        try:
            if address in {ADDRESSES["api"], ADDRESSES["web"]}:
                actor = "api" if address == ADDRESSES["api"] else "web"
                safe = operation in (["update"], ["no-op"]) and service_change_safe(before, after, actor, manifest, phase)
            elif address == ADDRESSES["migrate"]:
                safe = (operation in (["no-op"], ["update"]) and safe_job(after, {"api": values["tasteduel_release_migration_image"]},
                        ops_cost_hash=manifest["cost_sha256"], ops_through=manifest["reviewed_through_utc"]))
                if operation == ["update"]:
                    left, right = deepcopy(before), deepcopy(after)
                    for obj in (left, right):
                        container = obj["template"][0]["template"][0]["containers"][0]
                        container["env"] = [env for env in container["env"] if env["name"] != "TASTEDUEL_OPS_COST_REVIEW_HASH"]
                    safe &= phase in {"bridge-candidate", "migration-pin"} and image_only_update(left, right, actor="migrate")
            elif address in CLEANUP.values():
                key = next(key for key, value in CLEANUP.items() if value == address)
                safe = cleanup_safe(key, after, manifest, phase)
                if phase == "bridge-candidate":
                    safe &= operation == ["create"] and not before
                elif key == "job" and phase == "migration-pin":
                    safe &= operation in (["no-op"], ["update"]) and image_only_update(before, after, actor="migrate")
                elif key == "job" and phase == "feature-candidate":
                    # Shared release labels change source_ref; image remains pinned.
                    safe &= operation in (["no-op"], ["update"]) and image_only_update(before, after, actor="migrate")
                elif key == "schedule" and phase == "cleanup-resume":
                    old = deepcopy(after)
                    old["paused"] = True
                    safe &= operation == ["update"] and before == old
                else:
                    safe &= operation == ["no-op"] and before == after
            elif address == PUBLIC_WEB:
                safe &= after.get("member") == "allUsers" and after.get("role") == "roles/run.invoker" and after.get("name") in {"tasteduel-web", f"projects/{PROJECT}/locations/{REGION}/services/tasteduel-web"}
            elif address == ADDRESSES["api_web"]:
                safe &= after.get("member") == "serviceAccount:" + SA["web"] and after.get("role") == "roles/run.invoker"
            elif address == DASHBOARD:
                expected = dashboard_document()
                content = expected["mosaicLayout"]["tiles"][0]["widget"]["text"]["content"]
                expected["mosaicLayout"]["tiles"][0]["widget"]["text"]["content"] = content.replace("USD90", "USD100")
                safe = (operation == ["update"] and phase == "bridge-candidate"
                        and normalized_dashboard(json.loads(before["dashboard_json"])) == dashboard_document()
                        and normalized_dashboard(json.loads(after["dashboard_json"])) == expected)
                safe |= (operation == ["no-op"] and before == after
                         and normalized_dashboard(json.loads(after["dashboard_json"])) == expected)
            if after.get("member") in {"allUsers", "allAuthenticatedUsers"} and address != PUBLIC_WEB:
                safe = False
        except (KeyError, IndexError, TypeError, ValueError):
            safe = False
        blocked |= not safe
        if phase == "final-check" and operation not in (["no-op"], ["read"]):
            blocked = True
        if operation != ["no-op"]:
            actions.append({"address": address if safe else "outside_named_release_scope", "actions": operation, "approved_scope": bool(safe)})
    return {"status": "BLOCKED" if blocked else "REVIEWABLE", "phase": phase, "manifest_sha256": digest(manifest),
            "actions": actions, "public_access": True, "requires_independent_review": True, "provider_attributes_exported": False}


def reviewed_inputs(cost, manifest, phase, tester):
    validate_manifest(manifest)
    if digest(cost) != manifest["cost_sha256"] or cost["reviewed_through_utc"] != manifest["reviewed_through_utc"]:
        raise PlanBlocked("NAMED_COST_REVIEW_CHANGED")
    if not re.fullmatch(r"user:[^\s@]+@[^\s@]+", tester):
        raise PlanBlocked("NAMED_EXISTING_TESTER_REQUIRED")
    return {**foundation.approved_variables(cost), **phase_variables(manifest, phase), "tasteduel_candidate_tester": tester}


def verify_sources(manifest, fetch=None):
    """Re-read exact green main-push CI before credentials or any cloud mutation."""
    def github(run_id):
        request = Request(f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{run_id}",
                          headers={"User-Agent": "TasteDuel-named-release", "Accept": "application/vnd.github+json"})
        with urlopen(request, timeout=15) as response:
            return json.load(response)
    fetch = fetch or github
    for stage in ("bridge", "feature"):
        images = manifest[stage]["images"]
        run_id = images.get("ci", {}).get("id")
        if type(run_id) is not int or run_id <= 0:
            raise PlanBlocked("NAMED_EXACT_CI_RUN_REQUIRED")
        verified_ci(fetch(run_id), images["source_sha"])


def check_evidence(value, manifest, phase):
    """Evidence is bound to stage images, revisions and the immutable manifest."""
    required = {"status", "manifest_sha256", "phase", "source_sha", "api_revision", "web_revision", "checked_at_utc", "checks"}
    stage = manifest[stage_for(phase)]
    # Sealed revisions have no tag and still receive zero traffic. Browser
    # evidence therefore belongs to the reachable candidate, while promotion
    # separately requires inspected sealed configuration/readiness evidence.
    promotion = phase.endswith("-promote")
    target = stage["candidate"] if phase.endswith("-seal") or promotion else stage["release"]
    checks = {"browser", "private_api", "fixed_replay", "expiry", "revocation"}
    if promotion:
        required |= {"sealed_api_revision", "sealed_web_revision"}
        checks.add("sealed_configuration_ready")
    if phase == "feature-promote":
        checks |= {"named_verdict", "physical_cleanup"}
    if phase == "cleanup-resume":
        checks = {"physical_cleanup", "cleanup_job", "alerts", "public_browser"}
    try:
        checked = datetime.fromisoformat(value["checked_at_utc"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - checked).total_seconds()
        safe = (set(value) == required and value["status"] == "PASS" and value["phase"] == phase
                and value["manifest_sha256"] == digest(manifest)
                and value["source_sha"] == stage["images"]["source_sha"]
                and all(value[actor + "_revision"] == target[actor + "_revision"] for actor in ("api", "web"))
                and (not promotion or all(value["sealed_" + actor + "_revision"] == stage["release"][actor + "_revision"] for actor in ("api", "web")))
                and 0 <= age <= 3600 and set(value["checks"]) == checks
                and all(item is True for item in value["checks"].values()))
    except (KeyError, TypeError, ValueError):
        safe = False
    if not safe:
        raise PlanBlocked("NAMED_FRESH_BOUND_EVIDENCE_REQUIRED")


EVIDENCE_PHASES = {"bridge-seal", "bridge-promote", "feature-seal", "feature-promote", "cleanup-resume"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply"):
        command = sub.add_parser(name)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--cost", "--review", dest="cost", type=Path, required=True)
        command.add_argument("--phase", choices=PHASES, required=True)
        command.add_argument("--tester", required=True)
        command.add_argument("--evidence", type=Path)
        if name == "apply":
            command.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    owned = False
    journal = None
    try:
        manifest = validate_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
        cost = json.loads(args.cost.read_text(encoding="utf-8"))
        values = reviewed_inputs(cost, manifest, args.phase, args.tester)
        verify_sources(manifest)
        if args.command == "plan":
            evidence = None
            if args.phase in EVIDENCE_PHASES:
                if args.evidence is None:
                    raise PlanBlocked("NAMED_EXTERNAL_EVIDENCE_REQUIRED")
                evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
                check_evidence(evidence, manifest, args.phase)
            directory = ROOT / ".data/tasteduel-cloud-review" / ("release-named-" + args.phase + "-" + secrets.token_hex(8))
            source = foundation.source_snapshot(directory)
            adc, environment = foundation.adc_path(), credential_environment(values)
            foundation.terraform(directory, adc, environment, "init", "-input=false", "-lockfile=readonly",
                                 "-backend-config=bucket=" + foundation.BACKEND_BUCKET, "-backend-config=prefix=" + foundation.BACKEND_PREFIX)
            foundation.terraform(directory, adc, environment, "plan", "-input=false", "-no-color", "-lock-timeout=60s", "-out=release.tfplan")
            plan = json.loads(foundation.terraform(directory, adc, environment, "show", "-json", "release.tfplan"))
            verify_plan_inputs(plan, values)
            result = audit_plan(plan, manifest, args.phase)
            result.update(source_sha256=source, plan_sha256=hashlib.sha256((directory / "release.tfplan").read_bytes()).hexdigest(),
                          image_source_sha=values["tasteduel_release_source_sha"], reviewed_total_usd=cost["reviewed_total_usd"],
                          created_at_utc=datetime.now(timezone.utc).isoformat(), applied=False)
            for name, value in (("review.json", result), ("named-manifest.json", manifest), ("smoke-evidence.json", evidence)):
                if value is not None:
                    (directory / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"status": result["status"], "review": str(directory / "review.json"), "applied": False}))
            return 0 if result["status"] == "REVIEWABLE" else 2
        directory = args.directory.resolve()
        if directory.parent != (ROOT / ".data/tasteduel-cloud-review").resolve():
            raise PlanBlocked("NAMED_PLAN_OUTSIDE_PRIVATE_BOUNDARY")
        review = json.loads((directory / "review.json").read_text(encoding="utf-8"))
        approval = json.loads((directory / "independent-approval.json").read_text(encoding="utf-8"))
        if (review.get("status") != "REVIEWABLE" or approval.get("independent_review") != "PASS"
                or review.get("phase") != args.phase
                or any(approval.get(k) != review.get(k) for k in ("source_sha256", "plan_sha256", "image_source_sha", "phase", "manifest_sha256"))
                or review.get("manifest_sha256") != digest(manifest)
                or json.loads((directory / "named-manifest.json").read_text(encoding="utf-8")) != manifest
                or source_hash(directory) != review["source_sha256"] or source_hash(ROOT / "infra/terraform") != review["source_sha256"]
                or hashlib.sha256((directory / "release.tfplan").read_bytes()).hexdigest() != review["plan_sha256"]
                or review.get("reviewed_total_usd") != cost["reviewed_total_usd"]
                or review.get("image_source_sha") != values["tasteduel_release_source_sha"]):
            raise PlanBlocked("NAMED_EXACT_APPROVED_SAVED_PLAN_REQUIRED")
        if (directory / "apply-journal.json").exists():
            raise PlanBlocked("NAMED_PRIOR_ATTEMPT_REQUIRES_RECOVERY_REVIEW")
        if args.phase in EVIDENCE_PHASES:
            check_evidence(json.loads((directory / "smoke-evidence.json").read_text(encoding="utf-8")), manifest, args.phase)
        adc = foundation.adc_path()
        plan = json.loads(foundation.terraform(directory, adc, {}, "show", "-json", "release.tfplan"))
        verify_plan_inputs(plan, values)
        if audit_plan(plan, manifest, args.phase)["status"] != "REVIEWABLE":
            raise PlanBlocked("NAMED_SAVED_SCOPE_RECHECK_FAILED")
        environment = credential_environment(values)
        journal = {"status": "STARTED", "phase": args.phase, "plan_sha256": review["plan_sha256"],
                   "source_sha256": review["source_sha256"], "manifest_sha256": digest(manifest),
                   "started_at_utc": datetime.now(timezone.utc).isoformat(), "automatic_retry": False, "credential_payload_files": False}
        with (directory / "apply-journal.json").open("x", encoding="utf-8") as handle:
            json.dump(journal, handle, indent=2)
        owned = True
        result = subprocess.run(apply_command(directory, adc, environment), env={**os.environ, **environment}, capture_output=True, text=True)
        journal.update(status="APPLIED" if result.returncode == 0 else "FAILED_REQUIRES_RECOVERY",
                       completed_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=result.returncode)
        (directory / "apply-journal.json").write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(journal))
        return 0 if result.returncode == 0 else 2
    except Exception as failure:
        if owned:
            journal.update(status="FAILED_REQUIRES_RECOVERY", completed_at_utc=datetime.now(timezone.utc).isoformat())
            (directory / "apply-journal.json").write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "BLOCKED", "reason_code": str(failure) if isinstance(failure, PlanBlocked) else "NAMED_RELEASE_FAILED_" + type(failure).__name__,
                          "execution_started": owned, "automatic_retry": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

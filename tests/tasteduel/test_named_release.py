"""Named-duel release policy: synthetic plans only; no cloud/credential access."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

import test_hotfix_release as old
import test_release_plan as fixtures

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import tasteduel_named_release as release


def manifest():
    baseline = release.baseline_reference()
    image_record = old.manifest()["images"]
    groups = {}
    for stage, token in (("bridge", "b"), ("feature", "c")):
        images = deepcopy(image_record)
        images["source_sha"] = images["ci"]["head_sha"] = token * 40
        for actor in ("api", "web"):
            images["images"][actor] = {"digest": "sha256:" + token * 64,
                "reference": fixtures.publisher.immutable_reference("tasteduel-" + actor, "sha256:" + token * 64)}
        groups[stage] = {"images": images,
            "candidate": {"api_revision": "tasteduel-api-" + stage + "-candidate", "web_revision": "tasteduel-web-" + stage + "-candidate",
                "tag": stage, "origin": f"https://{stage}---tasteduel-web-dfthmgvvaa-el.a.run.app", "api_url": f"https://{stage}---tasteduel-api-dfthmgvvaa-el.a.run.app"},
            "release": {"api_revision": "tasteduel-api-" + stage + "-sealed", "web_revision": "tasteduel-web-" + stage + "-sealed"}}
    return {"version": 1, "kind": "named-duels-schema-release", "project": release.PROJECT, "region": release.REGION,
        "origin": release.ORIGIN, "baseline_manifest_sha256": release.digest(baseline),
        "baseline": {**{key: baseline[key] for key in ("source_sha", "api_revision", "web_revision")},
            **{actor + "_image": fixtures.publisher.immutable_reference("tasteduel-" + actor, baseline[actor + "_image_digest"]) for actor in ("api", "web")}},
        **groups, "schema": {"from": "td0011", "to": "td0014", "backward_compatible": True},
        "cost_sha256": "a" * 64, "reviewed_through_utc": "2026-11-07T04:45:00Z", "preview_exposure": "public-tag-intentionally-reachable"}


def service(actor, phase, record):
    value = old.service(actor, "baseline")
    if phase is None:
        value["template"][0]["revision"] = record["baseline"][actor + "_revision"]
        value["template"][0]["containers"][0]["image"] = record["baseline"][actor + "_image"]
        value["traffic"] = release.routes(record, None, actor)
        return value
    stage = record[release.stage_for(phase)]
    values = release.phase_variables(record, phase)
    value["template"][0]["revision"] = values[f"tasteduel_{actor}_candidate_revision"]
    value["template"][0]["containers"][0]["image"] = values[f"tasteduel_release_{actor}_image"]
    value["labels"]["source_ref"] = values["tasteduel_release_source_sha"][:12]
    value["traffic"] = release.routes(record, phase, actor)
    candidate = stage["candidate"] if phase.endswith("-candidate") else None
    for row in value["template"][0]["containers"][0]["env"]:
        if row["name"] == "TASTEDUEL_ALLOWED_ORIGINS":
            row["value"] = release.json.dumps([release.ORIGIN] + ([candidate["origin"]] if candidate else []), separators=(",", ":"))
        elif row["name"] == "TASTEDUEL_WEB_ORIGINS":
            row["value"] = release.ORIGIN + ("," + candidate["origin"] if candidate else "")
        elif row["name"] == "TASTEDUEL_API_URL":
            row["value"] = candidate["api_url"] if candidate else release.API_URI
    if actor == "api":
        value["template"][0]["containers"][0]["env"] += fixtures.environment(release.expected_cutoffs(record))
    return value


def job(record, phase):
    value = fixtures.job()
    values = release.phase_variables(record, phase)
    container = value["template"][0]["template"][0]["containers"][0]
    container.update(image=values["tasteduel_release_migration_image"], command=["python", "-m", "tasteduel.operations"], args=["migrate"])
    container["env"] += fixtures.environment({"TASTEDUEL_OPS_COST_REVIEW_HASH": record["cost_sha256"], "TASTEDUEL_OPS_REVIEWED_THROUGH_UTC": record["reviewed_through_utc"]})
    value["labels"] = {"app": "tasteduel", "source_ref": values["tasteduel_release_migration_source_sha"][:12]}
    return value


def cleanup(key, record, phase):
    base = {"project": release.PROJECT}
    if key == "sa":
        return {**base, "account_id": "tasteduel-cleanup-invoker", "disabled": False, "email": release.INVOKER}
    if key == "job":
        value = job(record, phase)
        value["name"] = "tasteduel-cleanup"
        task = value["template"][0]["template"][0]
        task.update(timeout="180s", max_retries=1)
        task["containers"][0].update(command=["python", "-m", "tasteduel.cleanup"], args=[])
        value["labels"]["source_ref"] = release.phase_variables(record, phase)["tasteduel_release_source_sha"][:12]
        return value
    if key == "iam":
        return {**base, "location": release.REGION, "name": "tasteduel-cleanup", "role": "roles/run.invoker", "member": "serviceAccount:" + release.INVOKER}
    if key == "schedule":
        return {**base, "region": release.REGION, "name": "tasteduel-cleanup", "schedule": "*/10 * * * *", "time_zone": "Etc/UTC",
            "paused": release.phase_variables(record, phase)["tasteduel_cleanup_paused"], "attempt_deadline": "30s",
            "retry_config": [{"retry_count": 2, "max_retry_duration": "600s", "min_backoff_duration": "60s", "max_backoff_duration": "300s", "max_doublings": 2}],
            "http_target": [{"uri": f"https://run.googleapis.com/v2/projects/{release.PROJECT}/locations/{release.REGION}/jobs/tasteduel-cleanup:run", "http_method": "POST", "body": "e30=", "headers": {"Content-Type": "application/json"},
                "oauth_token": [{"service_account_email": release.INVOKER, "scope": "https://www.googleapis.com/auth/cloud-platform"}]}]}
    if key == "metric":
        return {**base, "name": "tasteduel_cleanup_completed", "filter": 'resource.type="cloud_run_job" resource.labels.job_name="tasteduel-cleanup" (jsonPayload.status="PASS" OR jsonPayload.status="BACKLOG")',
            "metric_descriptor": [{"metric_kind": "DELTA", "value_type": "INT64", "unit": "1"}]}
    if key == "failure":
        return {**base, "enabled": True, "combiner": "OR", "notification_channels": [],
            "conditions": [{"condition_matched_log": [{"filter": 'resource.type="cloud_run_job" resource.labels.job_name="tasteduel-cleanup" (jsonPayload.status="FAIL" OR jsonPayload.oldest_expired_session_seconds>1800)'}]}],
            "alert_strategy": [{"auto_close": "3600s", "notification_rate_limit": [{"period": "1800s"}]}]}
    return {**base, "enabled": True, "combiner": "OR", "notification_channels": [],
        "conditions": [{"condition_absent": [{"filter": 'resource.type="cloud_run_job" metric.type="logging.googleapis.com/user/tasteduel_cleanup_completed"', "duration": "1800s",
            "aggregations": [{"alignment_period": "600s", "per_series_aligner": "ALIGN_SUM", "cross_series_reducer": None, "group_by_fields": []}]}]}]}


def plan(phase):
    record = manifest()
    prior = release.PREVIOUS[phase]
    entries = []
    for actor in ("api", "web"):
        before, after = service(actor, prior, record), service(actor, phase, record)
        entries.append({"address": release.ADDRESSES[actor], "change": {"actions": ["no-op"] if before == after else ["update"], "before": before, "after": after}})
    after = job(record, phase)
    before = job(record, prior or phase)
    if phase == "bridge-candidate":
        next(row for row in before["template"][0]["template"][0]["containers"][0]["env"] if row["name"] == "TASTEDUEL_OPS_COST_REVIEW_HASH")["value"] = "d" * 64
    entries.append({"address": release.ADDRESSES["migrate"], "change": {"actions": ["no-op"] if before == after else ["update"], "before": before, "after": after}})
    for key, address in release.CLEANUP.items():
        before = cleanup(key, record, prior) if prior else None
        after = cleanup(key, record, phase)
        entries.append({"address": address, "change": {"actions": ["create"] if not prior else ["no-op"] if before == after else ["update"], "before": before, "after": after}})
    protected = {release.PUBLIC_WEB: {"member": "allUsers", "role": "roles/run.invoker", "name": "tasteduel-web"},
        release.ADDRESSES["api_web"]: {"member": "serviceAccount:" + release.SA["web"], "role": "roles/run.invoker"},
        **{address: {"id": address} for address in release.MONITORS}}
    old_dashboard = release.dashboard_document()
    new_dashboard = deepcopy(old_dashboard)
    content = new_dashboard["mosaicLayout"]["tiles"][0]["widget"]["text"]["content"]
    new_dashboard["mosaicLayout"]["tiles"][0]["widget"]["text"]["content"] = content.replace("USD90", "USD100")
    protected.pop(release.DASHBOARD)
    entries.append({"address": release.DASHBOARD, "change": {"actions": ["update"] if phase == "bridge-candidate" else ["no-op"],
        "before": {"dashboard_json": release.json.dumps(old_dashboard if phase == "bridge-candidate" else new_dashboard)},
        "after": {"dashboard_json": release.json.dumps(new_dashboard)}}})
    for address, value in protected.items():
        entries.append({"address": address, "change": {"actions": ["no-op"], "before": deepcopy(value), "after": deepcopy(value)}})
    return {"resource_changes": entries}


@pytest.mark.parametrize("phase", release.PHASES)
def test_full_root_phase_policy_and_fixed_guards(phase):
    proposed = plan(phase)
    saved = deepcopy(proposed)
    result = release.audit_plan(proposed, manifest(), phase)
    assert result["status"] == "REVIEWABLE", result
    assert proposed == saved
    values = release.phase_variables(manifest(), phase)
    assert values["tasteduel_vertex_requests_per_day"] == 50
    assert values["tasteduel_qloo_requests_per_day"] == 100
    assert values["tasteduel_cleanup_enabled"]
    assert values["tasteduel_cleanup_paused"] is (phase not in {"cleanup-resume", "feature-rollback", "feature-rollforward", "final-check"})


@pytest.mark.parametrize("attack", ["sql_delete", "secret_replace", "unknown_update", "public_api", "job_override", "cutoff", "early_schedule", "counter_reset", "wrong_image", "missing_monitor", "duplicate"])
def test_plan_rejects_preservation_privacy_and_cost_attacks(attack):
    proposed = plan("bridge-candidate")
    rows = proposed["resource_changes"]
    if attack in {"sql_delete", "secret_replace", "unknown_update", "public_api", "counter_reset"}:
        rows.append({"address": attack, "change": {"actions": ["delete", "create"] if attack == "secret_replace" else ["delete"] if attack == "sql_delete" else ["update"],
            "before": {}, "after": {"member": "allUsers", "role": "roles/run.invoker"} if attack == "public_api" else {"changed": True}}})
    elif attack == "missing_monitor":
        rows[:] = [row for row in rows if row["address"] != next(iter(release.MONITORS))]
    elif attack == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif attack == "job_override":
        row = next(row for row in rows if row["address"] == release.CLEANUP["iam"])
        row["change"]["after"]["role"] = "roles/run.jobsExecutorWithOverrides"
    elif attack == "early_schedule":
        next(row for row in rows if row["address"] == release.CLEANUP["schedule"])["change"]["after"]["paused"] = False
    else:
        container = rows[0]["change"]["after"]["template"][0]["containers"][0]
        if attack == "cutoff":
            next(row for row in container["env"] if row["name"] == "TASTEDUEL_SESSION_HARD_CLOSES_AT")["value"] = "2027-01-01T00:00:00Z"
        else:
            container["image"] = manifest()["feature"]["images"]["images"]["api"]["reference"]
    assert release.audit_plan(proposed, manifest(), "bridge-candidate")["status"] == "BLOCKED"


def test_rejects_original_schema_rollback_and_named_identity_changes():
    value = manifest()
    value["schema"]["to"] = "td0011"
    with pytest.raises(release.PlanBlocked):
        release.validate_manifest(value)
    value = manifest()
    value["bridge"]["release"]["api_revision"] = value["baseline"]["api_revision"]
    with pytest.raises(release.PlanBlocked):
        release.validate_manifest(value)


def test_evidence_is_exact_fresh_and_cannot_claim_missing_cleanup():
    record = manifest()
    target = record["feature"]["candidate"]
    evidence = {"status": "PASS", "manifest_sha256": release.digest(record), "phase": "feature-promote",
        "source_sha": record["feature"]["images"]["source_sha"],
        **{actor + "_revision": target[actor + "_revision"] for actor in ("api", "web")},
        **{"sealed_" + actor + "_revision": record["feature"]["release"][actor + "_revision"] for actor in ("api", "web")},
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {key: True for key in ("browser", "private_api", "fixed_replay", "expiry", "revocation", "named_verdict", "physical_cleanup", "sealed_configuration_ready")}}
    release.check_evidence(evidence, record, "feature-promote")
    del evidence["checks"]["physical_cleanup"]
    with pytest.raises(release.PlanBlocked):
        release.check_evidence(evidence, record, "feature-promote")


@pytest.mark.parametrize("stage", ["bridge", "feature"])
def test_promotion_requires_candidate_browser_evidence_and_separate_sealed_inspection(stage):
    record = manifest()
    phase = stage + "-promote"
    evidence = {"status": "PASS", "manifest_sha256": release.digest(record), "phase": phase,
        "source_sha": record[stage]["images"]["source_sha"],
        **{actor + "_revision": record[stage]["candidate"][actor + "_revision"] for actor in ("api", "web")},
        **{"sealed_" + actor + "_revision": record[stage]["release"][actor + "_revision"] for actor in ("api", "web")},
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {key: True for key in ("browser", "private_api", "fixed_replay", "expiry", "revocation", "sealed_configuration_ready")}}
    if stage == "feature":
        evidence["checks"].update(named_verdict=True, physical_cleanup=True)
    release.check_evidence(evidence, record, phase)
    for attack in ("relabel_browser", "wrong_sealed_revision", "missing_sealed_check"):
        changed = deepcopy(evidence)
        if attack == "relabel_browser":
            changed["api_revision"] = record[stage]["release"]["api_revision"]
        elif attack == "wrong_sealed_revision":
            changed["sealed_web_revision"] = record[stage]["candidate"]["web_revision"]
        else:
            del changed["checks"]["sealed_configuration_ready"]
        with pytest.raises(release.PlanBlocked):
            release.check_evidence(changed, record, phase)


def test_cleanup_resume_requires_post_promotion_public_browser_evidence():
    record = manifest()
    evidence = {"status": "PASS", "manifest_sha256": release.digest(record), "phase": "cleanup-resume",
        "source_sha": record["feature"]["images"]["source_sha"], **record["feature"]["release"],
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {"physical_cleanup": True, "cleanup_job": True, "alerts": True, "public_browser": True}}
    release.check_evidence(evidence, record, "cleanup-resume")
    del evidence["checks"]["public_browser"]
    with pytest.raises(release.PlanBlocked):
        release.check_evidence(evidence, record, "cleanup-resume")


def test_final_check_never_allows_cloud_mutation_and_cleanup_uses_feature_digest():
    proposed = plan("final-check")
    assert all(row["change"]["actions"] == ["no-op"] for row in proposed["resource_changes"])
    record = manifest()
    cleanup_job = next(row for row in proposed["resource_changes"] if row["address"] == release.CLEANUP["job"])
    container = cleanup_job["change"]["after"]["template"][0]["template"][0]["containers"][0]
    assert container["image"] == record["feature"]["images"]["images"]["api"]["reference"]
    container["image"] = record["bridge"]["images"]["images"]["api"]["reference"]
    assert release.audit_plan(proposed, record, "final-check")["status"] == "BLOCKED"


def test_live_source_review_rejects_forged_green_manifest_before_cloud_credentials():
    record = manifest()
    record["bridge"]["images"]["ci"]["id"] = 101
    record["feature"]["images"]["ci"]["id"] = 102
    seen = []

    def fetch(run_id):
        seen.append(run_id)
        stage = "bridge" if run_id == 101 else "feature"
        return {"id": run_id, "html_url": "https://github.com/example", "head_sha": record[stage]["images"]["source_sha"],
            "head_branch": "main", "status": "completed", "conclusion": "success", "event": "push",
            "path": ".github/workflows/ci.yml", "repository": {"full_name": release.REPOSITORY}}

    release.verify_sources(record, fetch)
    assert seen == [101, 102]

    def forged(run_id):
        value = fetch(run_id)
        value["head_sha"] = "0" * 40
        return value

    with pytest.raises(release.PlanBlocked):
        release.verify_sources(record, forged)

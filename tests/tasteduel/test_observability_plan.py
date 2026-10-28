"""Synthetic full-root monitoring review: no cloud, secrets or provider calls."""

from copy import deepcopy
import json
import re

import pytest

import test_production_release as source
import tasteduel_observability_plan as review


def plan():
    value = source.plan("production-promote")
    value["resource_changes"][-1]["change"]["actions"] = ["no-op"]
    project = review.PROJECT
    records = {
        review.UPTIME: {"project": project, "uptime_check_id": "reviewed-check-123", "display_name": "Taste Duel public readiness",
            "timeout": "30s", "period": "900s", "selected_regions": ["EUROPE", "SOUTH_AMERICA", "ASIA_PACIFIC"],
            "http_check": [{"path": "/api/v1/health/ready", "port": 443, "use_ssl": True, "validate_ssl": True,
                "request_method": "GET", "headers": {}, "auth_info": [], "body": ""}],
            "content_matchers": [{"content": '"generation_available":true', "matcher": "CONTAINS_STRING", "json_path_matcher": []}],
            "monitored_resource": [{"type": "uptime_url", "labels": {"project_id": project, "host": review.ORIGIN.removeprefix("https://")}}]},
        review.GATE: {"input": None, "triggers_replace": None},
        review.EXCLUSION: {"project": project, "name": "tasteduel-private-request-urls", "description": review.EXCLUSION_DESCRIPTION,
            "filter": review.REQUEST_FILTER, "disabled": False},
        review.DASHBOARD: {"project": project, "dashboard_json": json.dumps(review.dashboard_document())},
        review.ALERT: {"project": project, "display_name": "Taste Duel readiness unavailable", "combiner": "OR", "enabled": True,
            "notification_channels": [], "user_labels": {},
            "documentation": [{"mime_type": "text/markdown", "content": review.ALERT_DOCUMENTATION, "subject": ""}],
            "conditions": [{"display_name": "Canonical readiness failed", "condition_absent": [], "condition_threshold": [{
                "filter": 'metric.type="monitoring.googleapis.com/uptime_check/check_passed" AND resource.type="uptime_url" '
                    'AND metric.label.check_id="reviewed-check-123"',
                "comparison": "COMPARISON_LT", "threshold_value": 1, "duration": "900s", "trigger": [{"count": 1}],
                "aggregations": [{"alignment_period": "900s", "per_series_aligner": "ALIGN_FRACTION_TRUE",
                    "cross_series_reducer": "REDUCE_MEAN", "group_by_fields": []}]}]}]},
    }
    for address, after in records.items():
        value["resource_changes"].append({"address": address, "change": {
            "actions": ["update"] if address == review.UPTIME else ["create"], "before": {}, "after": after}})
    return value


def after(value, address):
    return next(item["change"]["after"] for item in value["resource_changes"] if item["address"] == address)


def test_exact_additive_monitoring_is_reviewable_but_never_automatically_applied():
    result = review.audit_observability(plan(), source.manifest())
    assert result["status"] == "REVIEWABLE"
    assert result["requires_independent_review"] is True
    assert result["provider_attributes_exported"] is False
    assert len(result["actions"]) == 5


@pytest.mark.parametrize("field,value", [("period", "300s"), ("selected_regions", []),
    ("selected_regions", ["USA", "EUROPE", "ASIA_PACIFIC"]), ("project", "unrelated"), ("timeout", "60s")])
def test_uptime_scope_and_priced_checker_count_are_exact(field, value):
    proposed = plan()
    after(proposed, review.UPTIME)[field] = value
    assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"


@pytest.mark.parametrize("field,value", [("path", "/"), ("use_ssl", False), ("validate_ssl", False),
    ("headers", {"Authorization": "synthetic-operator-secret"}), ("auth_info", [{"username": "synthetic"}]),
    ("request_method", "POST"), ("body", "synthetic-private")])
def test_uptime_has_no_credentials_mutations_or_generic_liveness_substitution(field, value):
    proposed = plan()
    after(proposed, review.UPTIME)["http_check"][0][field] = value
    assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"


def test_canonical_host_and_generation_content_cannot_be_weakened():
    for field in ("host", "content"):
        proposed = plan()
        uptime = after(proposed, review.UPTIME)
        if field == "host":
            uptime["monitored_resource"][0]["labels"]["host"] = "unrelated.example"
        else:
            uptime["content_matchers"][0]["content"] = '"status":"ok"'
        assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"


@pytest.mark.parametrize("address", sorted(review.MONITORS))
@pytest.mark.parametrize("operation", [["delete"], ["delete", "create"], ["create", "delete"]])
def test_monitoring_never_deletes_or_replaces_existing_resources(address, operation):
    proposed = plan()
    next(item for item in proposed["resource_changes"] if item["address"] == address)["change"]["actions"] = operation
    assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"


def test_missing_resources_and_new_public_grant_cannot_hide_inside_monitoring():
    proposed = plan()
    proposed["resource_changes"] = [item for item in proposed["resource_changes"] if item["address"] != review.DASHBOARD]
    assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"
    proposed = plan()
    next(item for item in proposed["resource_changes"] if item["address"] == review.PUBLIC_WEB)["change"]["actions"] = ["create"]
    assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"


@pytest.mark.parametrize("address", ["google_sql_database.app", "google_secret_manager_secret_iam_member.new", "google_logging_project_exclusion.unrelated"])
def test_no_unrelated_or_secret_database_change_is_permitted(address):
    proposed = plan()
    proposed["resource_changes"].append({"address": address, "change": {"actions": ["update"], "after": {}}})
    assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"


def test_monitoring_cannot_change_services_or_leave_public_preview_tags():
    for attack in ("service", "tag"):
        proposed = plan()
        web = proposed["resource_changes"][1]["change"]
        if attack == "service":
            web["actions"] = ["update"]
        else:
            web["after"]["traffic"].append({"tag": "unsafe-preview", "percent": 0})
        assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"


def test_logging_filter_excludes_only_new_request_logs():
    proposed = plan()
    after(proposed, review.EXCLUSION)["filter"] = 'resource.type="cloud_run_revision"'
    assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"


def test_alert_has_no_external_recipient_and_checks_the_exact_uptime_id():
    for attack in ("channel", "id", "duration"):
        proposed = plan()
        alert = after(proposed, review.ALERT)
        if attack == "channel":
            alert["notification_channels"] = ["projects/unrelated/notificationChannels/1"]
        elif attack == "id":
            alert["conditions"][0]["condition_threshold"][0]["filter"] = 'metric.type="unrelated"'
        else:
            alert["conditions"][0]["condition_threshold"][0]["duration"] = "0s"
        assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"


def test_dashboard_cannot_add_private_raw_logs_or_unrelated_metric_sources():
    proposed = plan()
    dashboard = deepcopy(review.dashboard_document())
    dashboard["mosaicLayout"]["tiles"][2]["widget"]["logsPanel"]["filter"] = 'resource.type="cloud_run_revision"'
    after(proposed, review.DASHBOARD)["dashboard_json"] = json.dumps(dashboard)
    assert review.audit_observability(proposed, source.manifest())["status"] == "BLOCKED"


@pytest.mark.parametrize("event", ["generation", "request_error", "provider_admission_snapshot"])
def test_dashboard_matches_actual_uvicorn_text_and_structured_event_envelopes(event):
    # Observed in the locked local Docker runtime using Uvicorn's default
    # formatter, no provider/network access or application logger changes.
    line = "INFO:     " + json.dumps({"event": event, "status": 201}, separators=(",", ":"))
    assert re.search(review.TEXT_EVENT_PATTERN, line)
    assert f'jsonPayload.event="{event}"' in review.SANITIZED_EVENT_FILTER
    assert "textPayload=~" + json.dumps(review.TEXT_EVENT_PATTERN) in review.SANITIZED_EVENT_FILTER
    assert review.dashboard_document()["mosaicLayout"]["tiles"][2]["widget"]["logsPanel"]["filter"] == review.SANITIZED_EVENT_FILTER


@pytest.mark.parametrize("line", [
    'INFO:     {"event":"arbitrary_metadata","status":200}',
    'INFO:     request /entities/search?query=SYNTHETIC',
    'INFO:     {"message":"prefix","event":"generation"}',
    'ERROR:    {"event":"generation","private":"SYNTHETIC"}',
])
def test_dashboard_text_branch_does_not_become_a_generic_text_log_filter(line):
    assert re.search(review.TEXT_EVENT_PATTERN, line) is None

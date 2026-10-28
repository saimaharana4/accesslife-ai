"""Strict additive Taste Duel observability plan review; never applies a plan."""

from __future__ import annotations

from copy import deepcopy
import json
import re

from tasteduel_foundation_plan import PROJECT, REGION
from tasteduel_production_release import ORIGIN, audit_production, digest

UPTIME = "google_monitoring_uptime_check_config.web"
GATE = "terraform_data.tasteduel_monitoring_gate[0]"
EXCLUSION = "google_logging_project_exclusion.tasteduel_request_urls[0]"
ALERT = "google_monitoring_alert_policy.tasteduel_readiness[0]"
DASHBOARD = "google_monitoring_dashboard.tasteduel[0]"
MONITORS = frozenset({UPTIME, GATE, EXCLUSION, ALERT, DASHBOARD})
PUBLIC_WEB = "google_cloud_run_v2_service_iam_member.tasteduel_web_public[0]"
REQUEST_FILTER = ('resource.type="cloud_run_revision" AND (resource.labels.service_name="tasteduel-web" '
                  'OR resource.labels.service_name="tasteduel-api") AND log_id("run.googleapis.com/requests")')
EXCLUSION_DESCRIPTION = ("Exclude only Taste Duel Cloud Run HTTP request logs; retain sanitized application events, "
                         "system and audit logs.")
ALERT_DOCUMENTATION = ("Taste Duel canonical readiness has failed for fifteen minutes. Inspect sanitized "
    "generation/error/admission events and shared quota state. Keep the API private; do not reset counters or retry "
    "providers without a bounded review. Incidents appear in Monitoring; no external notification recipient is configured.")


def dashboard_document() -> dict:
    """Only built-in API metrics and allowlisted sanitized event names are displayed."""
    return {"displayName": "Taste Duel production", "mosaicLayout": {"columns": 12, "tiles": [
        {"xPos": 0, "yPos": 0, "width": 12, "height": 3, "widget": {
            "title": "Readiness, errors and bounded admission", "text": {"format": "MARKDOWN", "content":
                f"Canonical: {ORIGIN}\n\nGeneration/request_error/provider_admission_snapshot events contain numeric execution facts only. "
                "Admitted calls are conservative reservations, not exact billed usage. No raw rankings, searches, answers, "
                "chain-of-thought or identities. Billing alerts notify; they do not cap spend. The cumulative reviewed "
                "ceiling is USD90 through 7 November 2026 04:45 UTC."}}},
        {"xPos": 0, "yPos": 3, "width": 12, "height": 5, "widget": {
            "title": "API request rate by response class", "xyChart": {"dataSets": [{"plotType": "LINE", "timeSeriesQuery": {
                "timeSeriesFilter": {"filter": 'metric.type="run.googleapis.com/request_count" AND '
                    'resource.type="cloud_run_revision" AND resource.labels.service_name="tasteduel-api"',
                    "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_RATE",
                        "crossSeriesReducer": "REDUCE_SUM", "groupByFields": ["metric.label.response_code_class"]}}}}]}}},
        {"xPos": 0, "yPos": 8, "width": 12, "height": 6, "widget": {
            "title": "Sanitized generation, errors and admission observations", "logsPanel": {
                "resourceNames": [f"projects/{PROJECT}"], "filter": 'resource.type="cloud_run_revision" AND '
                    'resource.labels.service_name="tasteduel-api" AND (jsonPayload.event="generation" OR '
                    'jsonPayload.event="request_error" OR jsonPayload.event="provider_admission_snapshot")'}}},
    ]}}


def safe_uptime(value: dict) -> bool:
    check, resource = value["http_check"], value["monitored_resource"]
    if len(check) != 1 or len(resource) != 1:
        return False
    check = check[0]
    return (value.get("project") == PROJECT and value.get("display_name") == "Taste Duel public readiness" and value.get("timeout") == "10s"
        and value.get("period") == "900s"
        and set(value.get("selected_regions", [])) == {"EUROPE", "SOUTH_AMERICA", "ASIA_PACIFIC"}
        and len(value["selected_regions"]) == 3
        and check.get("path") == "/api/v1/health/ready" and check.get("port") == 443
        and check.get("use_ssl") is True and check.get("validate_ssl") is True
        and check.get("request_method") in (None, "GET") and check.get("body") in (None, "")
        and check.get("headers") in (None, {}) and check.get("auth_info") in (None, [])
        and check.get("service_agent_authentication") in (None, [])
        and check.get("accepted_response_status_codes") in (None, [])
        and value.get("content_matchers") == [{"content": '"generation_available":true', "matcher": "CONTAINS_STRING"}]
        and resource == [{"type": "uptime_url", "labels": {"project_id": PROJECT, "host": ORIGIN.removeprefix("https://")}}]
        and value.get("is_internal") in (None, False) and value.get("internal_checkers") in (None, []))


def compact(value):
    """Ignore provider-emitted empty optional blocks without ignoring meaningful values."""
    if isinstance(value, dict):
        return {key: compact(item) for key, item in value.items() if item is not None and item not in ("", [], {})}
    if isinstance(value, list):
        return [compact(item) for item in value]
    return value


def safe_alert(value: dict, check_id: str) -> bool:
    conditions = value.get("conditions", [])
    if len(conditions) != 1:
        return False
    condition = conditions[0]
    threshold = condition.get("condition_threshold", [])
    if len(threshold) != 1 or condition.get("display_name") != "Canonical readiness failed":
        return False
    threshold = threshold[0]
    return (value.get("project") == PROJECT and value.get("display_name") == "Taste Duel readiness unavailable"
        and value.get("combiner") == "OR" and value.get("enabled") is True
        and value.get("notification_channels") in (None, []) and value.get("user_labels") in (None, {})
        and value.get("documentation") == [{"mime_type": "text/markdown", "content": ALERT_DOCUMENTATION}]
        and threshold.get("filter") == 'metric.type="monitoring.googleapis.com/uptime_check/check_passed" AND '
            f'resource.type="uptime_url" AND metric.label.check_id="{check_id}"'
        and threshold.get("comparison") == "COMPARISON_LT" and threshold.get("threshold_value") == 1
        and threshold.get("duration") == "900s" and threshold.get("trigger") == [{"count": 1}]
        and threshold.get("aggregations") == [{"alignment_period": "900s", "per_series_aligner": "ALIGN_FRACTION_TRUE",
            "cross_series_reducer": "REDUCE_MEAN"}]
        and threshold.get("denominator_filter") in (None, "")
        and all(not condition.get(key) for key in ("condition_matched_log", "condition_absent", "condition_monitoring_query_language",
            "condition_prometheus_query_language", "condition_sql")))


def audit_observability(plan: dict, manifest: dict) -> dict:
    """Allow five exact monitoring resources while services, data and IAM remain unchanged."""
    base = deepcopy(plan)
    base["resource_changes"] = [item for item in plan.get("resource_changes", []) if item.get("address") not in MONITORS]
    checked = audit_production(base, manifest, "production-promote")
    blocked = checked["status"] != "REVIEWABLE"
    resources = {item.get("address"): item for item in plan.get("resource_changes", []) if item.get("address") in MONITORS}
    blocked |= set(resources) != MONITORS
    public = next((item for item in base["resource_changes"] if item.get("address") == PUBLIC_WEB), {})
    public_after = public.get("change", {}).get("after") or {}
    blocked |= (public.get("change", {}).get("actions") != ["no-op"] or public_after.get("name") != "tasteduel-web"
        or public_after.get("member") != "allUsers" or public_after.get("role") != "roles/run.invoker"
        or public_after.get("project") != PROJECT or public_after.get("location") != REGION)
    uptime = (resources.get(UPTIME, {}).get("change", {}).get("after") or {})
    check_id = uptime.get("uptime_check_id", "")
    blocked |= not isinstance(check_id, str) or not bool(re.fullmatch(r"[A-Za-z0-9_-]{1,200}", check_id))
    actions = list(checked["actions"])
    for address in sorted(resources):
        change = resources[address].get("change", {})
        after, operation = compact(change.get("after") or {}), change.get("actions")
        safe = operation in (["update"], ["no-op"]) if address == UPTIME else operation in (["create"], ["no-op"])
        try:
            if address == UPTIME:
                safe &= safe_uptime(after)
            elif address == GATE:
                safe &= after.get("input") is None and after.get("triggers_replace") is None
            elif address == EXCLUSION:
                safe &= (after.get("project") == PROJECT and after.get("name") == "tasteduel-private-request-urls"
                    and after.get("description") == EXCLUSION_DESCRIPTION and after.get("filter") == REQUEST_FILTER
                    and after.get("disabled") in (None, False))
            elif address == ALERT:
                safe &= safe_alert(after, check_id)
            elif address == DASHBOARD:
                safe &= after.get("project") == PROJECT and json.loads(after["dashboard_json"]) == dashboard_document()
        except (KeyError, TypeError, ValueError):
            safe = False
        blocked |= not safe
        if operation != ["no-op"]:
            actions.append({"address": address, "actions": operation, "approved_scope": bool(safe)})
    return {"status": "BLOCKED" if blocked else "REVIEWABLE", "phase": "production-observability", "actions": actions,
        "manifest_sha256": digest(manifest), "public_access": True, "requires_independent_review": True,
        "provider_attributes_exported": False}

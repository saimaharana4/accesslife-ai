# Explicit release handoff: the initial private candidate does not expose health.
variable "tasteduel_observability_enabled" {
  type    = bool
  default = false
}

locals {
  # The locked Uvicorn formatter prefixes our JSON facts with INFO. Cloud Logging
  # therefore ingests these as textPayload rather than a structured JSON record.
  tasteduel_operational_event_text_pattern = "^INFO: +[{]\"event\":\"(generation|request_error|provider_admission_snapshot)\","
}

resource "terraform_data" "tasteduel_monitoring_gate" {
  count = var.tasteduel_observability_enabled ? 1 : 0
  lifecycle {
    precondition {
      condition     = var.tasteduel_public_enabled && var.tasteduel_candidate_tag == null && var.tasteduel_candidate_origin == null
      error_message = "Public readiness monitoring requires the sealed public release without candidate tags or origins."
    }
  }
  depends_on = [terraform_data.cost_gate]
}

# Never retain request URLs containing search text, anonymous capabilities or IDs.
# Existing entries age out under the existing bucket policy; this is not deletion
# of historical logs or a change to unrelated services/audit/system logs.
resource "google_logging_project_exclusion" "tasteduel_request_urls" {
  count       = var.tasteduel_observability_enabled ? 1 : 0
  project     = var.project_id
  name        = "tasteduel-private-request-urls"
  description = "Exclude only Taste Duel Cloud Run HTTP request logs; retain sanitized application events, system and audit logs."
  filter      = "resource.type=\"cloud_run_revision\" AND (resource.labels.service_name=\"tasteduel-web\" OR resource.labels.service_name=\"tasteduel-api\") AND log_id(\"run.googleapis.com/requests\")"
  depends_on  = [terraform_data.tasteduel_monitoring_gate]
}

resource "google_monitoring_alert_policy" "tasteduel_readiness" {
  count        = var.tasteduel_observability_enabled ? 1 : 0
  display_name = "Taste Duel readiness unavailable"
  combiner     = "OR"
  enabled      = true
  documentation {
    mime_type = "text/markdown"
    content   = "Taste Duel canonical readiness has failed for fifteen minutes. Inspect sanitized generation/error/admission events and shared quota state. Keep the API private; do not reset counters or retry providers without a bounded review. Incidents appear in Monitoring; no external notification recipient is configured."
  }
  conditions {
    display_name = "Canonical readiness failed"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.web.uptime_check_id}\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "900s"
      aggregations {
        alignment_period     = "900s"
        per_series_aligner   = "ALIGN_FRACTION_TRUE"
        cross_series_reducer = "REDUCE_MEAN"
      }
      trigger { count = 1 }
    }
  }
  depends_on = [terraform_data.tasteduel_monitoring_gate]
}

resource "google_monitoring_dashboard" "tasteduel" {
  count = var.tasteduel_observability_enabled ? 1 : 0
  dashboard_json = jsonencode({
    displayName = "Taste Duel production"
    mosaicLayout = { columns = 12, tiles = [
      { width = 12, height = 3, widget = {
        title = "Readiness, errors and bounded admission"
        text  = { format = "MARKDOWN", content = "Canonical: ${local.tasteduel_web_origin}\n\nGeneration/request_error/provider_admission_snapshot events contain numeric execution facts only. Admitted calls are conservative reservations, not exact billed usage. No raw rankings, searches, answers, chain-of-thought or identities. Billing alerts notify; they do not cap spend. The cumulative reviewed ceiling is USD90 through 7 November 2026 04:45 UTC." }
      } },
      { yPos = 3, width = 12, height = 5, widget = {
        title = "API request rate by response class"
        xyChart = { dataSets = [{ plotType = "LINE", timeSeriesQuery = { timeSeriesFilter = {
          filter      = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"tasteduel-api\""
          aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["metric.label.response_code_class"] }
        } } }] }
      } },
      { yPos = 8, width = 12, height = 6, widget = {
        title     = "Sanitized generation, errors and admission observations"
        logsPanel = { resourceNames = ["projects/${var.project_id}"], filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"tasteduel-api\" AND (jsonPayload.event=\"generation\" OR jsonPayload.event=\"request_error\" OR jsonPayload.event=\"provider_admission_snapshot\" OR textPayload=~${jsonencode(local.tasteduel_operational_event_text_pattern)})" }
      } }
    ] }
  })
  depends_on = [terraform_data.tasteduel_monitoring_gate]
}

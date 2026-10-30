# Opt-in only after an updated cost review and td0014 migration verification.
variable "tasteduel_cleanup_enabled" {
  type    = bool
  default = false
}
variable "tasteduel_cleanup_paused" {
  type    = bool
  default = true
}

locals {
  # Known before creation, allowing exact saved-plan review of both bindings.
  tasteduel_cleanup_invoker_email = "tasteduel-cleanup-invoker@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_service_account" "tasteduel_cleanup_invoker" {
  count        = var.tasteduel_cleanup_enabled ? 1 : 0
  project      = var.project_id
  account_id   = "tasteduel-cleanup-invoker"
  display_name = "Invoke only the Taste Duel cleanup job"
}

resource "google_cloud_run_v2_job" "tasteduel_cleanup" {
  count               = var.tasteduel_cleanup_enabled ? 1 : 0
  project             = var.project_id
  location            = var.region
  name                = "tasteduel-cleanup"
  deletion_protection = true
  labels              = local.tasteduel_release_labels
  lifecycle {
    # Application-only releases leave the cleanup job's pinned image intact.
    ignore_changes = [labels["source_ref"]]
    precondition {
      condition     = var.tasteduel_release_migration_enabled && var.tasteduel_ops_cost_review_hash != null
      error_message = "Cleanup requires the reviewed migration configuration and refreshed cost hash."
    }
  }
  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = module.tasteduel_foundation[0].service_accounts["migrate"]
      timeout         = "180s"
      max_retries     = 1
      volumes {
        name = "cloudsql"
        cloud_sql_instance { instances = [google_sql_database_instance.db.connection_name] }
      }
      containers {
        image   = var.tasteduel_release_migration_image == null ? var.tasteduel_release_api_image : var.tasteduel_release_migration_image
        command = ["python", "-m", "tasteduel.cleanup"]
        args    = []
        resources { limits = { cpu = "1", memory = "512Mi" } }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        dynamic "env" {
          for_each = {
            TASTEDUEL_DATABASE_MODE                     = "cloud_sql"
            TASTEDUEL_CLOUD_SQL_CONNECTION_NAME         = google_sql_database_instance.db.connection_name
            TASTEDUEL_MIGRATION_DATABASE_SECRET_VERSION = local.tasteduel_database_secret.migrate
            TASTEDUEL_QLOO_ENABLED                      = "false"
            TASTEDUEL_GENERATION_ENABLED                = "false"
            TASTEDUEL_OPS_COST_REVIEW_HASH              = var.tasteduel_ops_cost_review_hash
            TASTEDUEL_OPS_REVIEWED_THROUGH_UTC          = var.reviewed_through_utc
          }
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }
  depends_on = [terraform_data.tasteduel_release_gate]
}

resource "google_cloud_run_v2_job_iam_member" "tasteduel_cleanup_invoker" {
  count      = var.tasteduel_cleanup_enabled ? 1 : 0
  project    = var.project_id
  location   = var.region
  name       = google_cloud_run_v2_job.tasteduel_cleanup[0].name
  role       = "roles/run.invoker"
  member     = "serviceAccount:${local.tasteduel_cleanup_invoker_email}"
  depends_on = [google_service_account.tasteduel_cleanup_invoker]
}

resource "google_cloud_scheduler_job" "tasteduel_cleanup" {
  count            = var.tasteduel_cleanup_enabled ? 1 : 0
  project          = var.project_id
  region           = var.region
  name             = "tasteduel-cleanup"
  schedule         = "*/10 * * * *"
  time_zone        = "Etc/UTC"
  paused           = var.tasteduel_cleanup_paused
  attempt_deadline = "30s"
  retry_config {
    retry_count          = 2
    max_retry_duration   = "600s"
    min_backoff_duration = "60s"
    max_backoff_duration = "300s"
    max_doublings        = 2
  }
  http_target {
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/tasteduel-cleanup:run"
    http_method = "POST"
    body        = base64encode("{}")
    headers     = { "Content-Type" = "application/json" }
    oauth_token {
      service_account_email = local.tasteduel_cleanup_invoker_email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
  depends_on = [google_cloud_run_v2_job_iam_member.tasteduel_cleanup_invoker]
}

resource "google_monitoring_alert_policy" "tasteduel_cleanup_failure" {
  count        = var.tasteduel_cleanup_enabled ? 1 : 0
  project      = var.project_id
  display_name = "Taste Duel cleanup failed or backlog exceeded 30 minutes"
  combiner     = "OR"
  conditions {
    display_name = "Cleanup execution failure"
    condition_matched_log {
      filter = "resource.type=\"cloud_run_job\" resource.labels.job_name=\"tasteduel-cleanup\" (jsonPayload.status=\"FAIL\" OR jsonPayload.oldest_expired_session_seconds>1800)"
    }
  }
  alert_strategy {
    notification_rate_limit { period = "1800s" }
    auto_close = "3600s"
  }
}

resource "google_logging_metric" "tasteduel_cleanup_heartbeat" {
  count   = var.tasteduel_cleanup_enabled ? 1 : 0
  project = var.project_id
  name    = "tasteduel_cleanup_completed"
  filter  = "resource.type=\"cloud_run_job\" resource.labels.job_name=\"tasteduel-cleanup\" (jsonPayload.status=\"PASS\" OR jsonPayload.status=\"BACKLOG\")"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_alert_policy" "tasteduel_cleanup_missing" {
  count        = var.tasteduel_cleanup_enabled ? 1 : 0
  project      = var.project_id
  display_name = "Taste Duel cleanup has no completed execution for 30 minutes"
  combiner     = "OR"
  conditions {
    display_name = "Cleanup heartbeat absent"
    condition_absent {
      filter   = "resource.type=\"cloud_run_job\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.tasteduel_cleanup_heartbeat[0].name}\""
      duration = "1800s"
      aggregations {
        alignment_period   = "600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
}

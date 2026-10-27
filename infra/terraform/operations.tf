data "google_project" "app" {}

resource "google_secret_manager_secret_iam_member" "qloo" {
  secret_id = "projects/${var.project_id}/secrets/accesslife-qloo-api-key"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app["worker"].email}"
}


resource "google_project_iam_member" "ingest_tasks" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.app["ingest"].email}"
}
resource "google_service_account_iam_member" "ingest_task_actas" {
  service_account_id = google_service_account.app["task"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.app["ingest"].email}"
}


resource "google_artifact_registry_repository_iam_member" "deploy_images" {
  location   = var.region
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.app["deploy"].email}"
}
resource "google_service_account_iam_member" "deploy_actas" {
  for_each           = toset(["web", "api", "worker", "ingest"])
  service_account_id = google_service_account.app[each.key].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.app["deploy"].email}"
}

resource "google_monitoring_uptime_check_config" "web" {
  display_name = "AccessLife public web"
  timeout      = "10s"
  period       = "300s"
  http_check {
    path         = "/"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }
  monitored_resource {
    type = "uptime_url"
    labels = { project_id = var.project_id, host = replace(var.public_url, "https://", "")
    }

  }
}

resource "google_billing_budget" "accesslife" {
  billing_account = var.billing_account
  display_name    = "AccessLife hackathon USD80 alerts"
  budget_filter {
    projects = ["projects/${data.google_project.app.number}"]
    # Keep legacy notification coverage during the common-label transition.
    labels = { "app" = "accesslife"
    }
    custom_period {
      start_date {
        year  = 2026
        month = 10
        day   = 24
      }
      end_date {
        year  = 2026
        month = 11
        day   = 8
      }

    }

  }
  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.budget_alert_units)
    }
  }
  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.75
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  depends_on = [terraform_data.cost_gate]
}

# Proposed additional notification coverage, not another spending allocation.
# Labels do not backfill old/unlabelled costs; those require the manual ledger.
resource "google_billing_budget" "tasteduel_migration" {
  billing_account = var.billing_account
  display_name    = "Qloo migration cumulative USD90 alerts"
  budget_filter {
    projects = ["projects/${data.google_project.app.number}"]
    labels   = { "cost_scope" = "qloo-hackathon" }
    custom_period {
      start_date {
        year  = 2026
        month = 10
        day   = 24
      }
      end_date {
        year  = 2026
        month = 11
        day   = 8
      }
    }
  }
  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.migration_alert_units)
    }
  }
  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.75
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  depends_on = [terraform_data.cost_gate]
}

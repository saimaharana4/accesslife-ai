data "google_project" "app" {}

resource "google_secret_manager_secret_iam_member" "qloo" {
  secret_id = "projects/${var.project_id}/secrets/accesslife-qloo-api-key"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app["worker"].email}"
}

resource "google_cloud_run_v2_job" "maintenance" {
  for_each = {
    migrate   = ["alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"]
    ingest    = ["python", "-m", "accesslife.adapters.retrieval"]
    reconcile = ["python", "-m", "accesslife.worker", "--reconcile"]

  }
  name     = "accesslife-${each.key}"
  location = var.region
  labels   = local.labels
  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.app["ingest"].email
      timeout         = "300s"
      max_retries     = 1
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.db.connection_name]
        }

      }
      containers {
        image   = var.api_image
        command = [each.value[0]]
        args    = slice(each.value, 1, length(each.value))
        resources {
          limits = { cpu = "1", memory = "2Gi"
          }
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "INTERNAL_WORKER_TOKEN"
          value_source {
            secret_key_ref {
              secret  = data.google_secret_manager_secret.worker.secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "CLOUD_TASKS_QUEUE"
          value = "projects/${var.project_id}/locations/${var.region}/queues/accesslife-planning"
        }
        env {
          name  = "CLOUD_TASKS_INVOKER_SERVICE_ACCOUNT"
          value = google_service_account.app["task"].email
        }
        env {
          name  = "WORKER_INTERNAL_URL"
          value = google_cloud_run_v2_service.worker.uri
        }

      }

    }

  }
  depends_on = [google_secret_manager_secret_version.database, google_secret_manager_secret_iam_member.database, google_secret_manager_secret_iam_member.worker, google_project_iam_member.sql]
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

resource "google_cloud_scheduler_job" "reconcile" {
  name      = "accesslife-reconcile"
  region    = var.region
  schedule  = "*/5 * * * *"
  time_zone = "Etc/UTC"
  paused    = var.maintenance_paused # Resume only after schema migration and the external planning smoke pass.
  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/${google_cloud_run_v2_job.maintenance["reconcile"].id}:run"
    oauth_token {
      service_account_email = google_service_account.app["ingest"].email
    }

  }
}
resource "google_cloud_run_v2_job_iam_member" "scheduler" {
  name     = google_cloud_run_v2_job.maintenance["reconcile"].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.app["ingest"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "deploy_run" {
  for_each = { api = google_cloud_run_v2_service.backend["api"].name, worker = google_cloud_run_v2_service.worker.name, web = google_cloud_run_v2_service.web.name }
  name     = each.value
  location = var.region
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.app["deploy"].email}"
}
resource "google_cloud_run_v2_job_iam_member" "deploy_jobs" {
  for_each = google_cloud_run_v2_job.maintenance
  name     = each.value.name
  location = var.region
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.app["deploy"].email}"
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
        day   = 6
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

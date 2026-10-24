locals {

  labels = { app = "accesslife", environment = "hackathon"
  }
  actors = toset(["web", "api", "worker", "task", "ingest", "deploy"])

}

resource "terraform_data" "cost_gate" {

  lifecycle {

    precondition {

      condition     = var.cost_review_passed && var.budget_usd <= 80
      error_message = "Provisioning is blocked until the incremental regional forecast fits the agreed US$80 envelope."


    }


  }

}

resource "google_service_account" "app" {

  for_each     = local.actors
  account_id   = "accesslife-${each.key}"
  display_name = "AccessLife ${each.key}"
  depends_on   = [terraform_data.cost_gate]

}

resource "google_artifact_registry_repository" "images" {

  location      = var.region
  repository_id = "accesslife"
  format        = "DOCKER"
  labels        = local.labels
  depends_on    = [terraform_data.cost_gate]

}

resource "google_sql_database_instance" "db" {

  name                = "accesslife-db"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = true
  settings {

    tier                        = "db-custom-1-3840"
    edition                     = "ENTERPRISE"
    availability_type           = "ZONAL"
    disk_size                   = 20
    disk_autoresize             = true
    disk_autoresize_limit       = 40
    user_labels                 = local.labels
    deletion_protection_enabled = true
    ip_configuration {
      ipv4_enabled = true

    }

    backup_configuration {

      enabled    = true
      start_time = "20:00"
      backup_retention_settings {
        retained_backups = 7

      }


    }


  }

  depends_on = [terraform_data.cost_gate]

}

resource "google_sql_database" "app" {

  name     = "accesslife"
  instance = google_sql_database_instance.db.name

}

resource "google_sql_user" "app" {

  name                = "accesslife"
  instance            = google_sql_database_instance.db.name
  password_wo         = var.database_password
  password_wo_version = 1

}

resource "google_secret_manager_secret" "database" {

  secret_id = "accesslife-database-url"
  labels    = local.labels
  replication {
    auto {


    }


  }

  depends_on = [terraform_data.cost_gate]

}

resource "google_secret_manager_secret_version" "database" {

  secret                 = google_secret_manager_secret.database.id
  secret_data_wo         = "postgresql+psycopg://accesslife:${urlencode(var.database_password)}@/accesslife?host=/cloudsql/${google_sql_database_instance.db.connection_name}"
  secret_data_wo_version = 1

}

data "google_secret_manager_secret" "worker" {
  secret_id = "accesslife-worker-token"
}

resource "google_secret_manager_secret_iam_member" "database" {

  for_each  = toset(["api", "worker", "ingest"])
  secret_id = google_secret_manager_secret.database.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app[each.key].email}"

}

resource "google_secret_manager_secret_iam_member" "worker" {

  for_each  = toset(["api", "worker", "ingest"])
  secret_id = data.google_secret_manager_secret.worker.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app[each.key].email}"

}

resource "google_project_iam_member" "sql" {

  for_each = toset(["api", "worker", "ingest"])
  project  = var.project_id
  role     = "roles/cloudsql.client"
  member   = "serviceAccount:${google_service_account.app[each.key].email}"

}

resource "google_project_iam_member" "vertex" {

  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.app["worker"].email}"

}

resource "google_project_iam_member" "api_vertex" {

  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.app["api"].email}"

}

resource "google_cloud_run_v2_service" "backend" {

  for_each = toset(["api"])
  name     = "accesslife-${each.key}"
  labels   = local.labels
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {

    service_account                  = google_service_account.app[each.key].email
    timeout                          = "120s"
    max_instance_request_concurrency = each.key == "worker" ? 3 : 20
    scaling {

      min_instance_count = 0
      max_instance_count = each.key == "worker" ? 1 : 2


    }

    volumes {

      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.db.connection_name]

      }


    }

    containers {

      image   = var.api_image
      command = ["uvicorn"]
      args    = [each.key == "worker" ? "accesslife.worker:app" : "accesslife.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
      ports {
        container_port = 8080

      }

      resources {
        limits = { cpu = each.key == "worker" ? "2" : "1", memory = each.key == "worker" ? "4Gi" : "1Gi"
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
        name  = "APP_ENV"
        value = "production"

      }
      env {
        name  = "TASTE_PROVIDER"
        value = "qloo"
      }
      env {
        name  = "QLOO_API_KEY_SECRET"
        value = "projects/${var.project_id}/secrets/accesslife-qloo-api-key"
      }
      env {
        name  = "MAX_DAILY_MODEL_CALLS"
        value = "35"
      }


      env {
        name  = "APP_PUBLIC_URL"
        value = var.public_url

      }

      env {
        name  = "TASK_BACKEND"
        value = "cloud_tasks"

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

  depends_on = [google_secret_manager_secret_version.database, google_secret_manager_secret_iam_member.database, google_secret_manager_secret_iam_member.worker, google_project_iam_member.sql]

}

resource "google_cloud_run_v2_service" "worker" {

  name     = "accesslife-worker"
  labels   = local.labels
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {

    service_account                  = google_service_account.app["worker"].email
    timeout                          = "120s"
    max_instance_request_concurrency = 3
    scaling {
      min_instance_count = 0
      max_instance_count = 1

    }

    volumes {

      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.db.connection_name]

      }


    }

    containers {

      image   = var.api_image
      command = ["uvicorn"]
      args    = ["accesslife.worker:app", "--host", "0.0.0.0", "--port", "8080"]
      ports {
        container_port = 8080

      }

      resources {
        limits = { cpu = "2", memory = "4Gi"
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
        name  = "APP_ENV"
        value = "production"

      }
      env {
        name  = "TASTE_PROVIDER"
        value = "qloo"
      }
      env {
        name  = "QLOO_API_KEY_SECRET"
        value = "projects/${var.project_id}/secrets/accesslife-qloo-api-key"
      }
      env {
        name  = "MAX_DAILY_MODEL_CALLS"
        value = "35"
      }



    }


  }

  depends_on = [google_secret_manager_secret_version.database, google_secret_manager_secret_iam_member.database, google_secret_manager_secret_iam_member.worker, google_project_iam_member.sql]

}

resource "google_cloud_tasks_queue" "planning" {

  name     = "accesslife-planning"
  location = var.region
  rate_limits {
    max_concurrent_dispatches = 3
    max_dispatches_per_second = 3

  }

  retry_config {
    max_attempts = 3
    min_backoff  = "2s"
    max_backoff  = "30s"

  }

  depends_on = [terraform_data.cost_gate]

}

resource "google_project_iam_member" "tasks" {

  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.app["api"].email}"

}

resource "google_service_account_iam_member" "task_actas" {

  service_account_id = google_service_account.app["task"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.app["api"].email}"

}

resource "google_cloud_run_v2_service_iam_member" "api" {

  name     = google_cloud_run_v2_service.backend["api"].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.app["web"].email}"

}

resource "google_cloud_run_v2_service_iam_member" "worker" {

  name     = google_cloud_run_v2_service.worker.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.app["task"].email}"

}

resource "google_cloud_run_v2_service" "web" {

  name     = "accesslife-web"
  labels   = local.labels
  location = var.region
  template {

    service_account = google_service_account.app["web"].email
    scaling {
      min_instance_count = 0
      max_instance_count = 2

    }

    containers {

      image = var.web_image
      ports {
        container_port = 3000

      }

      resources {
        limits = { cpu = "1", memory = "1Gi"
        }

      }

      env {
        name  = "API_INTERNAL_URL"
        value = google_cloud_run_v2_service.backend["api"].uri

      }

      env {
        name  = "API_AUDIENCE"
        value = google_cloud_run_v2_service.backend["api"].uri

      }

      env {
        name  = "APP_PUBLIC_URL"
        value = var.public_url

      }


    }


  }

}

resource "google_cloud_run_v2_service_iam_member" "public_web" {

  name     = google_cloud_run_v2_service.web.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"

}

resource "google_storage_bucket" "private" {

  for_each                    = toset(["docs", "backups"])
  name                        = "accesslife-${each.key}-${var.project_id}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels
  versioning {
    enabled = true

  }

  lifecycle_rule {

    action {
      type = "Delete"

    }

    condition {
      age        = each.key == "backups" ? 7 : 30
      with_state = "ARCHIVED"

    }


  }

  depends_on = [terraform_data.cost_gate]

}

resource "google_iam_workload_identity_pool" "github" {

  workload_identity_pool_id = "accesslife-github"
  depends_on                = [terraform_data.cost_gate]

}

resource "google_iam_workload_identity_pool_provider" "github" {

  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  attribute_mapping = { "google.subject" = "assertion.sub", "attribute.repository" = "assertion.repository"
  }
  attribute_condition = "assertion.repository == 'saimaharana4/accesslife-ai' && assertion.ref == 'refs/heads/main'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"

  }

}

resource "google_service_account_iam_member" "github" {

  service_account_id = google_service_account.app["deploy"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/saimaharana4/accesslife-ai"

}

output "web_url" {
  value = google_cloud_run_v2_service.web.uri
}

output "worker_url" {
  value = google_cloud_run_v2_service.worker.uri
}

locals {

  # Proposed common billing scope; source review only until the cumulative gate passes.
  # Taste Duel resources must carry this same cost_scope alongside app=tasteduel.
  labels = { app = "accesslife", environment = "hackathon", cost_scope = "qloo-hackathon"
  }
  actors = toset(["web", "api", "worker", "task", "ingest", "deploy"])

}

resource "terraform_data" "cost_gate" {

  lifecycle {

    precondition {

      condition = (
        var.cost_review_passed && var.billing_reconciled && var.budget_usd > 0 && var.budget_usd <= 100 &&
        (var.reviewed_total_usd == null ? false : var.reviewed_total_usd >= 0 && var.reviewed_total_usd <= var.budget_usd) &&
        (can(timecmp(var.reviewed_through_utc, "2026-11-07T04:45:00Z")) ? timecmp(var.reviewed_through_utc, "2026-11-07T04:45:00Z") >= 0 : false)
      )
      error_message = "Provisioning is blocked: reconcile incurred/unlabelled billing and price cumulative cost within the explicitly approved ceiling (maximum US$100) through the reviewed judging/follow-up/rollback window (at least 7 November 2026 04:45 UTC)."


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

  lifecycle {
    prevent_destroy = true
  }

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

  lifecycle {
    prevent_destroy = true
  }

  name     = "accesslife"
  instance = google_sql_database_instance.db.name

}

resource "google_sql_user" "app" {

  lifecycle {
    prevent_destroy = true
  }

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
  attribute_mapping = merge(
    { "google.subject" = "assertion.sub", "attribute.repository" = "assertion.repository" },
    var.tasteduel_foundation_enabled ? {
      "attribute.repository_id"       = "assertion.repository_id"
      "attribute.repository_owner_id" = "assertion.repository_owner_id"
    } : {}
  )
  attribute_condition = var.tasteduel_foundation_enabled ? "assertion.repository_id == '1431472864' && assertion.repository_owner_id == '60200140' && assertion.ref == 'refs/heads/main' && assertion.environment == 'foundation-review'" : "assertion.repository == 'saimaharana4/accesslife-ai' && assertion.ref == 'refs/heads/main'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"

  }

}

resource "google_service_account_iam_member" "github" {

  service_account_id = google_service_account.app["deploy"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/saimaharana4/accesslife-ai"

}

terraform {
  required_version = ">= 1.13, < 2"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.50"
    }
  }
}

locals {
  labels         = { app = "tasteduel", environment = "hackathon", cost_scope = "qloo-hackathon" }
  actors         = toset(["web", "api", "migrate", "deploy"])
  usernames      = { runtime = "tasteduel_runtime", migrate = "tasteduel_migrator" }
  secret_readers = { runtime = "api", migrate = "migrate" }
}

resource "google_service_account" "app" {
  for_each     = local.actors
  project      = var.project_id
  account_id   = "tasteduel-${each.key}"
  display_name = "Taste Duel ${each.key}"
}

resource "google_sql_database" "app" {
  project  = var.project_id
  name     = "tasteduel"
  instance = var.sql_instance_name
  lifecycle { prevent_destroy = true }
}

# Cloud SQL built-in user creation does NOT establish PostgreSQL least privilege.
# Restricted grants/inherited-role removal require a separately reviewed bootstrap.
resource "google_sql_user" "app" {
  for_each            = local.usernames
  project             = var.project_id
  instance            = var.sql_instance_name
  name                = each.value
  password_wo         = each.key == "runtime" ? var.runtime_password : var.migration_password
  password_wo_version = var.credential_version
  lifecycle { prevent_destroy = true }
}

resource "google_secret_manager_secret" "database" {
  for_each  = local.usernames
  project   = var.project_id
  secret_id = "tasteduel-${each.key}-database-url"
  labels    = local.labels
  replication {
    auto {}
  }
  lifecycle { prevent_destroy = true }
}

resource "google_secret_manager_secret_version" "database" {
  for_each               = local.usernames
  secret                 = google_secret_manager_secret.database[each.key].id
  secret_data_wo         = "postgresql+psycopg://${each.value}:${urlencode(each.key == "runtime" ? var.runtime_password : var.migration_password)}@/tasteduel?host=/cloudsql/${var.sql_connection_name}"
  secret_data_wo_version = var.credential_version
  deletion_policy        = "ABANDON"
  depends_on             = [google_sql_user.app, google_sql_database.app]
}

resource "google_secret_manager_secret_iam_member" "database" {
  for_each  = local.secret_readers
  project   = var.project_id
  secret_id = google_secret_manager_secret.database[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app[each.value].email}"
}

# IAM is scoped to the existing secret, not a version: release configuration must
# consume exactly version 1. No secret data source or new copy of the key exists.
resource "google_secret_manager_secret_iam_member" "qloo" {
  project   = var.project_id
  secret_id = "accesslife-qloo-api-key"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app["api"].email}"
}

resource "google_project_iam_member" "sql" {
  for_each = toset(["api", "migrate"])
  project  = var.project_id
  role     = "roles/cloudsql.client"
  member   = "serviceAccount:${google_service_account.app[each.key].email}"
}

resource "google_project_iam_custom_role" "vertex_predict" {
  project     = var.project_id
  role_id     = "tasteduelVertexPredictor"
  title       = "Taste Duel Vertex prediction"
  description = "Inference only; no dataset, model administration or deployment rights."
  permissions = ["aiplatform.endpoints.predict", "serviceusage.services.use"]
}

resource "google_project_iam_member" "vertex" {
  project = var.project_id
  role    = google_project_iam_custom_role.vertex_predict.name
  member  = "serviceAccount:${google_service_account.app["api"].email}"
}

resource "google_artifact_registry_repository_iam_member" "deploy" {
  project    = var.project_id
  location   = var.region
  repository = var.registry_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.app["deploy"].email}"
}

resource "google_service_account_iam_member" "deploy_act_as" {
  for_each           = toset(["web", "api", "migrate"])
  service_account_id = google_service_account.app[each.key].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.app["deploy"].email}"
}

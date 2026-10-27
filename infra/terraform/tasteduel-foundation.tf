variable "tasteduel_foundation_enabled" {
  type        = bool
  default     = false
  description = "Enable only for the reviewed full-root saved foundation plan after cumulative billing and preservation gates pass."
}
variable "tasteduel_credential_version" {
  type    = number
  default = 1
}
variable "tasteduel_runtime_password" {
  type      = string
  sensitive = true
  ephemeral = true
  default   = null
  nullable  = true
  validation {
    condition     = !var.tasteduel_foundation_enabled || (var.tasteduel_runtime_password != null ? length(var.tasteduel_runtime_password) >= 32 : false)
    error_message = "Enabled foundation requires a fresh ephemeral runtime credential; never put it in source or payload files."
  }
}
variable "tasteduel_migration_password" {
  type      = string
  sensitive = true
  ephemeral = true
  default   = null
  nullable  = true
  validation {
    condition     = !var.tasteduel_foundation_enabled || (var.tasteduel_migration_password != null ? length(var.tasteduel_migration_password) >= 32 : false)
    error_message = "Enabled foundation requires a fresh ephemeral migration credential; never put it in source or payload files."
  }
}

module "tasteduel_foundation" {
  count               = var.tasteduel_foundation_enabled ? 1 : 0
  source              = "./modules/tasteduel-foundation"
  project_id          = var.project_id
  region              = var.region
  sql_instance_name   = google_sql_database_instance.db.name
  sql_connection_name = google_sql_database_instance.db.connection_name
  registry_id         = google_artifact_registry_repository.images.repository_id
  runtime_password    = var.tasteduel_runtime_password
  migration_password  = var.tasteduel_migration_password
  credential_version  = var.tasteduel_credential_version
  depends_on          = [terraform_data.cost_gate]
}

resource "google_service_account_iam_member" "tasteduel_github" {
  count              = var.tasteduel_foundation_enabled ? 1 : 0
  service_account_id = "projects/${var.project_id}/serviceAccounts/${module.tasteduel_foundation[0].service_accounts["deploy"]}"
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/1431472864"
  depends_on         = [google_iam_workload_identity_pool_provider.github]
}

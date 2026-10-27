output "service_accounts" {
  value = { for key, identity in google_service_account.app : key => identity.email }
}
output "database_name" { value = google_sql_database.app.name }
output "database_secret_versions" {
  description = "Non-payload exact numeric version references for release; never use latest."
  value       = { for key, version in google_secret_manager_secret_version.database : key => version.name }
}
output "qloo_secret_version" {
  value = "projects/${var.project_id}/secrets/accesslife-qloo-api-key/versions/1"
}

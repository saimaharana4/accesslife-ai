variable "project_id" { type = string }
variable "region" { type = string }
variable "sql_instance_name" { type = string }
variable "sql_connection_name" { type = string }
variable "registry_id" { type = string }
variable "credential_version" {
  type = number
  validation {
    condition     = var.credential_version >= 1 && floor(var.credential_version) == var.credential_version
    error_message = "Credential revision must be a positive integer; increment deliberately for rotation."
  }
}
variable "runtime_password" {
  type      = string
  sensitive = true
  ephemeral = true
  validation {
    condition     = length(var.runtime_password) >= 32
    error_message = "A fresh runtime credential of at least 32 characters is required."
  }
}
variable "migration_password" {
  type      = string
  sensitive = true
  ephemeral = true
  validation {
    condition     = length(var.migration_password) >= 32 && var.migration_password != var.runtime_password
    error_message = "A distinct fresh migration credential of at least 32 characters is required."
  }
}

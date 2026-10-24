variable "project_id" {

  type    = string
  default = "project-bb13ecd8-9d67-408d-9a7"

}

variable "region" {

  type    = string
  default = "asia-south1"

}

variable "web_image" {
  type = string
}

variable "api_image" {
  type = string
}

variable "public_url" {
  type = string
}

variable "database_password" {

  type      = string
  sensitive = true
  ephemeral = true

}

variable "budget_usd" {

  type    = number
  default = 80

}

variable "cost_review_passed" {

  type        = bool
  default     = false
  description = "Set only after a regional forecast and billing review pass; no resources should be applied before this."

}


variable "billing_account" {
  type = string

}

variable "maintenance_paused" {
  type        = bool
  default     = true
  description = "Unpause after schema migration and the external planning smoke pass."
}

variable "budget_currency" {
  type    = string
  default = "INR"
}
variable "budget_alert_units" {
  type = number
}

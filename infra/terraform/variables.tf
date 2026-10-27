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
  default = 90

}

variable "cost_review_passed" {

  type        = bool
  default     = false
  description = "Set only after a regional forecast and billing review pass; no resources should be applied before this."

}

variable "billing_reconciled" {
  type        = bool
  default     = false
  description = "True only after dedicated-resource incurred charges, unlabeled spend and credits/tax treatment are reconciled."
}

variable "reviewed_total_usd" {
  type        = number
  default     = null
  description = "Reviewed cumulative incurred plus remaining cost, including overlap, recovery, FX and tax; not a new allocation."
}

variable "reviewed_through_utc" {
  type        = string
  default     = ""
  description = "RFC3339 end of priced judging/follow-up/rollback window; reprice after a later cutover."
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

variable "migration_alert_units" {
  type        = number
  default     = 6972
  description = "Explicitly approved US$90 cumulative ceiling notification subtotal, at INR95.98875/USD reserving 18% tax and 5% FX. Recheck before apply; alert only, not a spending cap. Legacy alert amount remains unchanged."
}

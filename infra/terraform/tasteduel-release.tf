# Release A creates only the reviewed migration job. After that exact job has
# migrated/verified Taste Duel, release B adds IAM-restricted initial services.
# Initial revision allocation is genuinely 100%, NOT zero-traffic; IAM is the
# candidate boundary. Public promotion is a separately reviewed release action.
variable "tasteduel_release_migration_enabled" {
  type    = bool
  default = false
}
variable "tasteduel_release_services_enabled" {
  type    = bool
  default = false
}
variable "tasteduel_release_api_image" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_release_api_image == null ? true : can(regex("^asia-south1-docker\\.pkg\\.dev/project-bb13ecd8-9d67-408d-9a7/accesslife/tasteduel-api@sha256:[0-9a-f]{64}$", var.tasteduel_release_api_image))
    error_message = "Supply a reviewed published Taste Duel API digest in the retained registry, never a tag or placeholder."
  }
}
variable "tasteduel_release_web_image" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_release_web_image == null ? true : can(regex("^asia-south1-docker\\.pkg\\.dev/project-bb13ecd8-9d67-408d-9a7/accesslife/tasteduel-web@sha256:[0-9a-f]{64}$", var.tasteduel_release_web_image))
    error_message = "Supply a reviewed published Taste Duel web digest in the retained registry, never a tag or placeholder."
  }
}
variable "tasteduel_release_source_sha" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_release_source_sha == null ? true : can(regex("^[0-9a-f]{40}$", var.tasteduel_release_source_sha))
    error_message = "Release source must identify the exact successful-CI commit."
  }
}
variable "tasteduel_release_migration_image" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_release_migration_image == null ? true : can(regex("^asia-south1-docker\\.pkg\\.dev/project-bb13ecd8-9d67-408d-9a7/accesslife/tasteduel-api@sha256:[0-9a-f]{64}$", var.tasteduel_release_migration_image))
    error_message = "Migration needs a reviewed published Taste Duel API digest."
  }
}
variable "tasteduel_release_migration_source_sha" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_release_migration_source_sha == null ? true : can(regex("^[0-9a-f]{40}$", var.tasteduel_release_migration_source_sha))
    error_message = "Migration source must identify its exact successful-CI SHA."
  }
}
variable "tasteduel_ops_cost_review_hash" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_ops_cost_review_hash == null ? true : can(regex("^[0-9a-f]{64}$", var.tasteduel_ops_cost_review_hash))
    error_message = "Mutating operations need the exact reviewed cost SHA256."
  }
}
variable "tasteduel_candidate_tester" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_candidate_tester == null ? true : can(regex("^user:[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+$", var.tasteduel_candidate_tester))
    error_message = "Candidate access must name one reviewed IAM user; no public, domain or owner-wide group."
  }
}
variable "tasteduel_public_enabled" {
  type    = bool
  default = false
}
variable "tasteduel_public_hotfix_preview" {
  type        = bool
  default     = false
  description = "Explicit reviewed follow-on hotfix preview: web tag is publicly reachable, never an IAM boundary."
}
variable "tasteduel_api_traffic_revision" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_api_traffic_revision == null ? true : can(regex("^tasteduel-api-[a-z0-9-]+$", var.tasteduel_api_traffic_revision))
    error_message = "Pin a verified Taste Duel API revision, never a legacy service."
  }
}
variable "tasteduel_web_traffic_revision" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_web_traffic_revision == null ? true : can(regex("^tasteduel-web-[a-z0-9-]+$", var.tasteduel_web_traffic_revision))
    error_message = "Pin a verified Taste Duel web revision, never a legacy service."
  }
}
variable "tasteduel_api_candidate_revision" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_api_candidate_revision == null ? true : can(regex("^tasteduel-api-[a-z0-9-]+$", var.tasteduel_api_candidate_revision))
    error_message = "Candidate API revision must be an explicit reviewed Taste Duel name."
  }
}
variable "tasteduel_web_candidate_revision" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_web_candidate_revision == null ? true : can(regex("^tasteduel-web-[a-z0-9-]+$", var.tasteduel_web_candidate_revision))
    error_message = "Candidate web revision must be an explicit reviewed Taste Duel name."
  }
}
variable "tasteduel_candidate_tag" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_candidate_tag == null ? true : can(regex("^[a-z][a-z0-9-]{0,30}$", var.tasteduel_candidate_tag))
    error_message = "Candidate tag must be a reviewed short DNS label."
  }
}
variable "tasteduel_candidate_origin" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_candidate_origin == null ? true : can(regex("^https://[a-z0-9-]+\\.a\\.run\\.app$", var.tasteduel_candidate_origin))
    error_message = "Candidate origin must be a verified HTTPS Cloud Run tag URL without a path."
  }
}
variable "tasteduel_candidate_api_url" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.tasteduel_candidate_api_url == null ? true : can(regex("^https://[a-z0-9-]+\\.a\\.run\\.app$", var.tasteduel_candidate_api_url))
    error_message = "Candidate API target must be an exact verified private HTTPS revision-tag URL."
  }
}
variable "tasteduel_vertex_requests_per_day" {
  type    = number
  default = 10
  validation {
    condition     = contains([10, 50], var.tasteduel_vertex_requests_per_day)
    error_message = "Only the reviewed candidate10/public50 model envelopes are supported."
  }
}
variable "tasteduel_qloo_requests_per_day" {
  type    = number
  default = 12
  validation {
    condition     = contains([12, 100], var.tasteduel_qloo_requests_per_day)
    error_message = "Only the reviewed candidate12/public100 Qloo envelopes are supported."
  }
}

locals {
  tasteduel_release_enabled = var.tasteduel_release_migration_enabled || var.tasteduel_release_services_enabled
  tasteduel_release_labels = {
    app        = "tasteduel", environment = "hackathon", cost_scope = "qloo-hackathon"
    source_ref = var.tasteduel_release_source_sha == null ? "disabled" : substr(var.tasteduel_release_source_sha, 0, 12)
  }
  # Official deterministic run.app URL; verify its real alias after creation.
  # https://docs.cloud.google.com/run/docs/triggering/https-request
  tasteduel_web_origin      = "https://tasteduel-web-${data.google_project.app.number}.${var.region}.run.app"
  tasteduel_release_origins = concat([local.tasteduel_web_origin], var.tasteduel_candidate_origin == null ? [] : [var.tasteduel_candidate_origin])
  tasteduel_database_secret = {
    runtime = "projects/${var.project_id}/secrets/tasteduel-runtime-database-url/versions/1"
    migrate = "projects/${var.project_id}/secrets/tasteduel-migrate-database-url/versions/1"
  }
}

resource "terraform_data" "tasteduel_release_gate" {
  count = local.tasteduel_release_enabled ? 1 : 0
  lifecycle {
    precondition {
      condition = (var.tasteduel_foundation_enabled && var.tasteduel_release_migration_enabled &&
        var.tasteduel_release_api_image != null && var.tasteduel_release_source_sha != null &&
      (!var.tasteduel_release_services_enabled || (var.tasteduel_release_web_image != null && var.tasteduel_candidate_tester != null)))
      error_message = "Release needs preserved foundation, a real reviewed API digest/source SHA, and reviewed web digest/tester for service creation; migrate the new schema before enabling services."
    }
    precondition {
      condition = (!var.tasteduel_public_enabled || (
        ((var.tasteduel_candidate_tag == null && var.tasteduel_candidate_origin == null && var.tasteduel_candidate_api_url == null) || var.tasteduel_public_hotfix_preview) &&
        var.tasteduel_api_traffic_revision != null && var.tasteduel_web_traffic_revision != null &&
      var.tasteduel_vertex_requests_per_day == 50 && var.tasteduel_qloo_requests_per_day == 100))
      error_message = "Public release requires compatible revision pins, reviewed quota limits and no tags except an explicitly reviewed publicly reachable hotfix preview."
    }
    precondition {
      condition = (var.tasteduel_candidate_tag == null ? (var.tasteduel_candidate_origin == null && var.tasteduel_candidate_api_url == null) : (
        (!var.tasteduel_public_enabled || var.tasteduel_public_hotfix_preview) && var.tasteduel_candidate_origin != null && var.tasteduel_candidate_api_url != null &&
        var.tasteduel_api_candidate_revision != null && var.tasteduel_web_candidate_revision != null &&
      var.tasteduel_api_traffic_revision != null && var.tasteduel_web_traffic_revision != null))
      error_message = "Candidate tags require an IAM-private initial release or explicit public hotfix preview, both revision pins and exact temporary origins."
    }
    precondition {
      condition = (!var.tasteduel_public_hotfix_preview ? true : (
        var.tasteduel_candidate_tag == null ? false : (
          var.tasteduel_public_enabled && var.tasteduel_observability_enabled &&
          var.tasteduel_candidate_origin == "https://${var.tasteduel_candidate_tag}---tasteduel-web-dfthmgvvaa-el.a.run.app" &&
      var.tasteduel_candidate_api_url == "https://${var.tasteduel_candidate_tag}---tasteduel-api-dfthmgvvaa-el.a.run.app")))
      error_message = "A public hotfix preview must retain monitoring and use only the exact existing services' tag URLs. A zero-percent web tag remains public."
    }
    precondition {
      condition = ((var.tasteduel_vertex_requests_per_day == 10 && var.tasteduel_qloo_requests_per_day == 12) ||
      (var.tasteduel_vertex_requests_per_day == 50 && var.tasteduel_qloo_requests_per_day == 100))
      error_message = "Do not mix candidate/public admission policy pairs."
    }
    precondition {
      condition     = can(timecmp(timestamp(), var.reviewed_through_utc)) ? timecmp(timestamp(), var.reviewed_through_utc) < 0 : false
      error_message = "The reviewed operating window has expired; reprice/review before any release."
    }
  }
  depends_on = [terraform_data.cost_gate, module.tasteduel_foundation]
}

resource "google_cloud_run_v2_job" "tasteduel_migrate" {
  count               = var.tasteduel_release_migration_enabled ? 1 : 0
  project             = var.project_id
  name                = "tasteduel-migrate"
  location            = var.region
  labels              = merge(local.tasteduel_release_labels, var.tasteduel_release_migration_source_sha == null ? {} : { source_ref = substr(var.tasteduel_release_migration_source_sha, 0, 12) })
  deletion_protection = true
  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = module.tasteduel_foundation[0].service_accounts["migrate"]
      timeout         = "300s"
      max_retries     = 0
      volumes {
        name = "cloudsql"
        cloud_sql_instance { instances = [google_sql_database_instance.db.connection_name] }
      }
      containers {
        image   = var.tasteduel_release_migration_image == null ? var.tasteduel_release_api_image : var.tasteduel_release_migration_image
        command = var.tasteduel_ops_cost_review_hash == null ? ["alembic"] : ["python", "-m", "tasteduel.operations"]
        args    = var.tasteduel_ops_cost_review_hash == null ? ["-c", "apps/api/tasteduel-alembic.ini", "upgrade", "head"] : ["migrate"]
        resources { limits = { cpu = "1", memory = "512Mi" } }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        env {
          name  = "TASTEDUEL_DATABASE_MODE"
          value = "cloud_sql"
        }
        env {
          name  = "TASTEDUEL_CLOUD_SQL_CONNECTION_NAME"
          value = google_sql_database_instance.db.connection_name
        }
        env {
          name  = "TASTEDUEL_MIGRATION_DATABASE_SECRET_VERSION"
          value = local.tasteduel_database_secret.migrate
        }
        env {
          name  = "TASTEDUEL_QLOO_ENABLED"
          value = "false"
        }
        env {
          name  = "TASTEDUEL_GENERATION_ENABLED"
          value = "false"
        }
        dynamic "env" {
          for_each = var.tasteduel_ops_cost_review_hash == null ? {} : {
            TASTEDUEL_OPS_COST_REVIEW_HASH     = var.tasteduel_ops_cost_review_hash
            TASTEDUEL_OPS_REVIEWED_THROUGH_UTC = var.reviewed_through_utc
          }
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }
  depends_on = [terraform_data.tasteduel_release_gate]
}

resource "google_cloud_run_v2_service" "tasteduel_api" {
  count               = var.tasteduel_release_services_enabled ? 1 : 0
  project             = var.project_id
  name                = "tasteduel-api"
  location            = var.region
  labels              = local.tasteduel_release_labels
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = true
  scaling {
    min_instance_count    = 0
    manual_instance_count = 0
  }
  template {
    revision                         = var.tasteduel_api_candidate_revision
    service_account                  = module.tasteduel_foundation[0].service_accounts["api"]
    timeout                          = "60s"
    max_instance_request_concurrency = 8
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance { instances = [google_sql_database_instance.db.connection_name] }
    }
    containers {
      image = var.tasteduel_release_api_image
      ports { container_port = 8000 }
      resources {
        limits            = { cpu = "1", memory = "1Gi" }
        cpu_idle          = true
        startup_cpu_boost = false
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      env {
        name  = "TASTEDUEL_DATABASE_MODE"
        value = "cloud_sql"
      }
      env {
        name  = "TASTEDUEL_CLOUD_SQL_CONNECTION_NAME"
        value = google_sql_database_instance.db.connection_name
      }
      env {
        name  = "TASTEDUEL_DATABASE_SECRET_VERSION"
        value = local.tasteduel_database_secret.runtime
      }
      env {
        name  = "TASTEDUEL_COOKIE_SECURE"
        value = "true"
      }
      env {
        name  = "TASTEDUEL_ALLOWED_ORIGINS"
        value = jsonencode(local.tasteduel_release_origins)
      }
      env {
        name  = "TASTEDUEL_QLOO_ENABLED"
        value = "true"
      }
      env {
        name  = "TASTEDUEL_QLOO_TRANSPORT"
        value = "http_ranked"
      }
      env {
        name  = "TASTEDUEL_QLOO_HTTP_TYPED_SEARCH"
        value = "true"
      }
      env {
        name  = "TASTEDUEL_QLOO_SECRET_VERSION"
        value = module.tasteduel_foundation[0].qloo_secret_version
      }
      env {
        name  = "TASTEDUEL_GENERATION_ENABLED"
        value = "true"
      }
      env {
        name  = "TASTEDUEL_VERTEX_PROJECT"
        value = var.project_id
      }
      env {
        name  = "TASTEDUEL_VERTEX_REQUESTS_PER_DAY"
        value = tostring(var.tasteduel_vertex_requests_per_day)
      }
      env {
        name  = "TASTEDUEL_VERTEX_TOKENS_PER_DAY"
        value = "500000"
      }
      env {
        name  = "TASTEDUEL_QLOO_REQUESTS_PER_DAY"
        value = tostring(var.tasteduel_qloo_requests_per_day)
      }
      env {
        name  = "TASTEDUEL_QLOO_REQUESTS_PER_MINUTE"
        value = "12"
      }
      startup_probe {
        tcp_socket { port = 8000 }
        initial_delay_seconds = 0
        period_seconds        = 2
        timeout_seconds       = 1
        failure_threshold     = 30
      }
      liveness_probe {
        http_get {
          path = "/v1/health/live"
          port = 8000
        }
        period_seconds    = 30
        timeout_seconds   = 2
        failure_threshold = 3
      }
    }
  }
  traffic {
    type     = var.tasteduel_api_traffic_revision == null ? "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST" : "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION"
    revision = var.tasteduel_api_traffic_revision
    percent  = 100
  }
  dynamic "traffic" {
    for_each = var.tasteduel_candidate_tag == null ? [] : [var.tasteduel_candidate_tag]
    content {
      type     = "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION"
      revision = var.tasteduel_api_candidate_revision
      percent  = 0
      tag      = traffic.value
    }
  }
  depends_on = [terraform_data.tasteduel_release_gate]
}

resource "google_cloud_run_v2_service" "tasteduel_web" {
  count               = var.tasteduel_release_services_enabled ? 1 : 0
  project             = var.project_id
  name                = "tasteduel-web"
  location            = var.region
  labels              = local.tasteduel_release_labels
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = true
  scaling {
    min_instance_count    = 0
    manual_instance_count = 0
  }
  template {
    revision                         = var.tasteduel_web_candidate_revision
    service_account                  = module.tasteduel_foundation[0].service_accounts["web"]
    timeout                          = "60s"
    max_instance_request_concurrency = 20
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      image = var.tasteduel_release_web_image
      ports { container_port = 3000 }
      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = false
      }
      env {
        name  = "TASTEDUEL_API_URL"
        value = var.tasteduel_candidate_api_url == null ? google_cloud_run_v2_service.tasteduel_api[0].uri : var.tasteduel_candidate_api_url
      }
      env {
        name  = "TASTEDUEL_API_AUDIENCE"
        value = google_cloud_run_v2_service.tasteduel_api[0].uri
      }
      env {
        name  = "TASTEDUEL_API_IAM"
        value = "true"
      }
      env {
        name  = "TASTEDUEL_WEB_ORIGINS"
        value = join(",", local.tasteduel_release_origins)
      }
      env {
        name  = "TASTEDUEL_CANONICAL_ORIGIN"
        value = local.tasteduel_web_origin
      }
      env {
        name  = "TASTEDUEL_ALLOW_LOCAL_HTTP"
        value = "false"
      }
      startup_probe {
        tcp_socket { port = 3000 }
        period_seconds    = 2
        timeout_seconds   = 1
        failure_threshold = 30
      }
    }
  }
  traffic {
    type     = var.tasteduel_web_traffic_revision == null ? "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST" : "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION"
    revision = var.tasteduel_web_traffic_revision
    percent  = 100
  }
  dynamic "traffic" {
    for_each = var.tasteduel_candidate_tag == null ? [] : [var.tasteduel_candidate_tag]
    content {
      type     = "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION"
      revision = var.tasteduel_web_candidate_revision
      percent  = 0
      tag      = traffic.value
    }
  }
  depends_on = [terraform_data.tasteduel_release_gate]
}

resource "google_cloud_run_v2_service_iam_member" "tasteduel_api_web" {
  count    = var.tasteduel_release_services_enabled ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.tasteduel_api[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.tasteduel_foundation[0].service_accounts["web"]}"
}
resource "google_cloud_run_v2_service_iam_member" "tasteduel_web_tester" {
  count    = var.tasteduel_release_services_enabled ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.tasteduel_web[0].name
  role     = "roles/run.invoker"
  member   = var.tasteduel_candidate_tester
}
resource "google_cloud_run_v2_service_iam_member" "tasteduel_web_public" {
  count    = var.tasteduel_release_services_enabled && var.tasteduel_public_enabled ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.tasteduel_web[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
resource "google_cloud_run_v2_service_iam_member" "tasteduel_deploy" {
  for_each = var.tasteduel_release_services_enabled ? { api = google_cloud_run_v2_service.tasteduel_api[0].name, web = google_cloud_run_v2_service.tasteduel_web[0].name } : {}
  project  = var.project_id
  location = var.region
  name     = each.value
  role     = "roles/run.developer"
  member   = "serviceAccount:${module.tasteduel_foundation[0].service_accounts["deploy"]}"
}
resource "google_cloud_run_v2_job_iam_member" "tasteduel_deploy" {
  count    = var.tasteduel_release_migration_enabled ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.tasteduel_migrate[0].name
  role     = "roles/run.developer"
  member   = "serviceAccount:${module.tasteduel_foundation[0].service_accounts["deploy"]}"
}

output "tasteduel_candidate" {
  value = var.tasteduel_release_services_enabled ? {
    web_uri    = google_cloud_run_v2_service.tasteduel_web[0].uri
    web_origin = local.tasteduel_web_origin
    api_uri    = google_cloud_run_v2_service.tasteduel_api[0].uri
    allocation = var.tasteduel_public_enabled ? "Public web, private API; explicitly pinned compatible revisions" : "IAM-restricted candidate; actual allocation recorded in revision traffic"
  } : null
}

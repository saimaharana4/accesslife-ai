# Permanent legacy runtime retirement. Exact resources are deleted only through
# the separately authorized out-of-band allowlist after source review. These
# blocks later forget their old state addresses WITHOUT provider destruction.
# Never run state rm, apply, or delete cloud resources to make validation pass.
# SQL/data/users, registry, secrets, identities, buckets/state and rollback assets
# retain their current addresses. Reinstatement requires an explicit rollback
# review of Git history + recorded digests, not a feature toggle recreating jobs.
# The old uptime monitor remains unchanged and will be stale after retirement;
# its review/retirement is a separate scoped action.

removed {
  from = google_cloud_run_v2_service.backend
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_run_v2_service.worker
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_run_v2_service.web
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_tasks_queue.planning
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_run_v2_service_iam_member.api
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_run_v2_service_iam_member.worker
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_run_v2_service_iam_member.public_web
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_run_v2_job.maintenance
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_scheduler_job.reconcile
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_run_v2_job_iam_member.scheduler
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_run_v2_service_iam_member.deploy_run
  lifecycle {
    destroy = false
  }
}

removed {
  from = google_cloud_run_v2_job_iam_member.deploy_jobs
  lifecycle {
    destroy = false
  }
}

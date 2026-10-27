"""Read the single existing state in memory and emit ownership metadata only.

Never calls Secret Manager, writes raw state, enumerates credential fields, or
invokes Terraform. The downloaded state remains private even if values are marked
sensitive. Only fixed selected attributes reach the ignored review artifact.
"""

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession

PROJECT = "project-bb13ecd8-9d67-408d-9a7"
BUCKET = "accesslife-tfstate-" + PROJECT
OBJECT = "accesslife/state/default.tfstate"
ROOT = Path(__file__).resolve().parents[1]
REVIEWED_TYPES = frozenset({
    "terraform_data", "google_project", "google_service_account",
    "google_artifact_registry_repository", "google_artifact_registry_repository_iam_member",
    "google_billing_budget", "google_cloud_run_v2_job", "google_cloud_run_v2_job_iam_member",
    "google_cloud_run_v2_service", "google_cloud_run_v2_service_iam_member",
    "google_cloud_scheduler_job", "google_cloud_tasks_queue",
    "google_iam_workload_identity_pool", "google_iam_workload_identity_pool_provider",
    "google_monitoring_uptime_check_config", "google_project_iam_member",
    "google_secret_manager_secret", "google_secret_manager_secret_iam_member",
    "google_secret_manager_secret_version", "google_service_account_iam_member",
    "google_sql_database", "google_sql_database_instance", "google_sql_user", "google_storage_bucket",
})


def ownership(state):
    resources = []
    for resource in state.get("resources", []):
        prefix = resource.get("module", "")
        address = (prefix + "." if prefix else "")
        if resource["mode"] == "data":
            address += "data."
        address += resource["type"] + "." + resource["name"]
        if resource["type"] not in REVIEWED_TYPES:
            resources.append({"address": address, "type": resource["type"], "review_status": "unsupported_type_attributes_omitted"})
            continue  # e.g. random_password.id may itself contain a credential.
        for instance in resource.get("instances", []):
            suffix = "[" + json.dumps(instance["index_key"]) + "]" if "index_key" in instance else ""
            attributes = instance.get("attributes", {})
            entry = {"address": address + suffix, "type": resource["type"], "id": attributes.get("id")}
            for key in ("name", "project", "region", "location", "labels", "paused", "schedule", "database_version", "deletion_protection"):
                if key in attributes:
                    entry[key] = attributes[key]
            if resource["type"] == "google_sql_database_instance":
                settings = (attributes.get("settings") or [{}])[0]
                entry["sql_settings"] = {key: settings.get(key) for key in (
                    "tier", "edition", "availability_type", "disk_size", "disk_autoresize_limit", "user_labels", "deletion_protection_enabled",
                )}
            if resource["type"] == "google_cloud_run_v2_service":
                template = (attributes.get("template") or [{}])[0]
                entry["images"] = [value.get("image") for value in template.get("containers", [])]
                entry["traffic"] = [{key: value.get(key) for key in ("type", "revision", "percent")} for value in attributes.get("traffic", [])]
            resources.append(entry)
    return resources


def main():
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    with AuthorizedSession(credentials) as http:
        response = http.get(f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{quote(OBJECT, safe='')}", params={"alt": "media"}, timeout=25)
        if response.status_code != 200 or len(response.content) > 2_000_000:
            raise RuntimeError("State unavailable or outside reviewed bounds")
        data = response.content
        state = json.loads(data)
    result = {
        "observed_at": datetime.now(UTC).isoformat(), "bucket": BUCKET,
        "object": OBJECT, "serial": state.get("serial"), "terraform_version": state.get("terraform_version"),
        "state_sha256": hashlib.sha256(data).hexdigest(), "raw_state_saved": False,
        "ownership": ownership(state),
    }
    target = ROOT / ".data/tasteduel-cloud-review/state-ownership.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state_serial": result["serial"], "owned_records": len(result["ownership"]), "raw_state_saved": False}))


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        print(json.dumps({"status": "blocked", "safe_error_type": type(failure).__name__}))
        raise SystemExit(1)

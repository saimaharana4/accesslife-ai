"""Read selected metadata for the dedicated AccessLife migration boundary.

Uses ADC in memory, never Secret Manager :access, database queries, bucket object
payloads, container environment values, task bodies or unrelated project assets.
The output is a private audit artifact, not a deployable state file.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession

PROJECT = "project-bb13ecd8-9d67-408d-9a7"
REGION = "asia-south1"
ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = f"projects/{PROJECT}/locations/{REGION}"
SECRET_IDS = (
    "accesslife-qloo-api-key", "accesslife-db-password", "accesslife-database-url",
    "accesslife-worker-token",
)


def select(value: dict, keys: tuple[str, ...]) -> dict:
    return {key: value[key] for key in keys if key in value}


class Inventory:
    def __init__(self) -> None:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        self.http = AuthorizedSession(credentials)
        self.requests = 0
        self.errors: list[dict] = []

    def get(self, url: str, **params: str) -> dict:
        self.requests += 1
        try:
            response = self.http.get(url, params=params, timeout=25)
            if response.status_code != 200:
                self.errors.append({"resource": url, "status": response.status_code})
                return {}
            return response.json()
        except Exception as error:
            # Exception strings can contain HTTP bodies/credential details.
            self.errors.append({"resource": url, "failure_type": type(error).__name__})
            return {}

    def collect(self) -> dict:
        result: dict = {
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "project": PROJECT, "region": REGION, "mode": "read-only-selected-metadata",
            "services": [], "jobs": [], "secrets": [], "buckets": [],
        }
        for name in ("accesslife-web", "accesslife-api", "accesslife-worker"):
            url = f"https://run.googleapis.com/v2/{RUN_ROOT}/services/{name}"
            service = self.get(url)
            item = select(service, (
                "name", "uid", "generation", "createTime", "updateTime", "labels", "uri",
                "latestReadyRevision", "latestCreatedRevision", "traffic", "trafficStatuses",
                "ingress", "scaling", "reconciling",
            ))
            item["terminalCondition"] = select(service.get("terminalCondition", {}), ("type", "state", "lastTransitionTime", "reason"))
            template = service.get("template", {})
            item["runtime"] = select(template, (
                "serviceAccount", "timeout", "maxInstanceRequestConcurrency", "scaling",
            ))
            item["containers"] = [select(container, ("image", "resources")) for container in template.get("containers", [])]
            item["revisions"] = []
            page = ""
            while True:
                revisions = self.get(url + "/revisions", pageSize="100", **({"pageToken": page} if page else {}))
                for revision in revisions.get("revisions", []):
                    cleaned = select(revision, (
                        "name", "createTime", "updateTime", "labels", "serviceAccount",
                        "scaling", "timeout", "maxInstanceRequestConcurrency",
                    ))
                    cleaned["containers"] = [select(container, ("image", "resources")) for container in revision.get("containers", [])]
                    cleaned["conditions"] = [select(condition, ("type", "state", "severity", "revisionReason", "lastTransitionTime")) for condition in revision.get("conditions", [])]
                    item["revisions"].append(cleaned)
                page = revisions.get("nextPageToken", "")
                if not page:
                    break
            result["services"].append(item or {"requested_name": name})
        for name in ("accesslife-migrate", "accesslife-ingest", "accesslife-reconcile"):
            job = self.get(f"https://run.googleapis.com/v2/{RUN_ROOT}/jobs/{name}")
            template = job.get("template", {}).get("template", {})
            item = select(job, ("name", "createTime", "updateTime", "labels", "executionCount", "latestCreatedExecution"))
            item["runtime"] = select(template, ("serviceAccount", "timeout", "maxRetries"))
            item["containers"] = [select(container, ("image", "resources")) for container in template.get("containers", [])]
            result["jobs"].append(item or {"requested_name": name})
        scheduler = self.get(f"https://cloudscheduler.googleapis.com/v1/{RUN_ROOT}/jobs/accesslife-reconcile")
        result["scheduler"] = select(scheduler, ("name", "schedule", "timeZone", "state", "lastAttemptTime", "scheduleTime"))
        result["scheduler"]["last_status_code"] = scheduler.get("status", {}).get("code", 0)
        queue = self.get(f"https://cloudtasks.googleapis.com/v2/{RUN_ROOT}/queues/accesslife-planning")
        result["queue"] = select(queue, ("name", "state", "rateLimits", "retryConfig", "purgeTime"))
        task_counts = self.get(
            f"https://cloudtasks.googleapis.com/v2/{RUN_ROOT}/queues/accesslife-planning/tasks",
            pageSize="1000", fields="tasks(name,scheduleTime,dispatchCount,responseCount),nextPageToken",
        )
        result["tasks"] = {
            "listed_count": len(task_counts.get("tasks", [])),
            "has_more": bool(task_counts.get("nextPageToken")),
            "scope": "metadata-only; no task body or headers",
        }
        sql = f"https://sqladmin.googleapis.com/sql/v1beta4/projects/{PROJECT}/instances/accesslife-db"
        instance = self.get(sql)
        result["sql_instance"] = select(instance, (
            "name", "region", "databaseVersion", "state", "createTime", "connectionName",
            "currentDiskSize", "maxDiskSize", "backendType", "gceZone", "secondaryGceZone",
        ))
        settings = instance.get("settings", {})
        result["sql_instance"]["settings"] = select(settings, (
            "tier", "edition", "availabilityType", "dataDiskSizeGb", "dataDiskType", "storageAutoResize",
            "storageAutoResizeLimit", "activationPolicy", "userLabels", "backupConfiguration", "deletionProtectionEnabled",
        ))
        result["sql_instance"]["network_policy"] = select(settings.get("ipConfiguration", {}), ("ipv4Enabled", "requireSsl", "sslMode"))
        result["sql_databases"] = [select(item, ("name", "charset", "collation", "instance", "project")) for item in self.get(sql + "/databases").get("items", [])]
        result["sql_users"] = [select(item, ("name", "host", "type", "instance", "project", "sqlserverUserDetails")) for item in self.get(sql + "/users").get("items", [])]
        result["sql_backups"] = [select(item, ("id", "status", "type", "kind", "startTime", "endTime", "location", "backupKind", "diskEncryptionConfiguration")) for item in self.get(sql + "/backupRuns", maxResults="30").get("items", [])]
        repository = self.get(f"https://artifactregistry.googleapis.com/v1/{RUN_ROOT}/repositories/accesslife")
        result["registry"] = select(repository, ("name", "format", "createTime", "updateTime", "labels", "sizeBytes", "cleanupPolicies", "cleanupPolicyDryRun", "dockerConfig"))
        images = self.get(f"https://artifactregistry.googleapis.com/v1/{RUN_ROOT}/repositories/accesslife/dockerImages", pageSize="1000")
        result["registry_images"] = [select(item, ("name", "uri", "tags", "imageSizeBytes", "uploadTime", "buildTime", "mediaType")) for item in images.get("dockerImages", [])]
        result["registry_images_have_more"] = bool(images.get("nextPageToken"))
        for suffix in ("docs", "backups", "tfstate"):
            name = f"accesslife-{suffix}-{PROJECT}"
            bucket = self.get(f"https://storage.googleapis.com/storage/v1/b/{name}")
            result["buckets"].append(select(bucket, ("name", "location", "storageClass", "timeCreated", "updated", "labels", "versioning", "iamConfiguration", "lifecycle", "retentionPolicy", "softDeletePolicy")))
            if suffix == "tfstate":
                state_objects = self.get(f"https://storage.googleapis.com/storage/v1/b/{name}/o", prefix="accesslife/state", fields="items(name,generation,metageneration,size,updated),nextPageToken", maxResults="100")
                result["state_object_metadata"] = {
                    "items": [select(item, ("name", "generation", "metageneration", "size", "updated")) for item in state_objects.get("items", [])],
                    "has_more": bool(state_objects.get("nextPageToken")),
                }
        for secret_id in SECRET_IDS:
            url = f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets/{quote(secret_id)}"
            secret = self.get(url)
            item = select(secret, ("name", "createTime", "labels", "replication", "expireTime", "rotation", "versionAliases"))
            versions = self.get(url + "/versions", pageSize="100")
            item["versions"] = [select(version, ("name", "createTime", "destroyTime", "state")) for version in versions.get("versions", [])]
            result["secrets"].append(item or {"requested_name": secret_id})
        # Exact identifier verified from the dedicated legacy state/inventory.
        check = self.get(f"https://monitoring.googleapis.com/v3/projects/{PROJECT}/uptimeCheckConfigs/accesslife-public-web-iutELD7g_s8", fields="name,displayName,period,timeout")
        result["uptime_checks"] = [select(check, ("name", "displayName", "period", "timeout"))] if check else []
        result["http_requests"] = self.requests
        result["errors"] = self.errors
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".data/tasteduel-cloud-review/inventory.json")
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    private_root = (ROOT / ".data/tasteduel-cloud-review").resolve()
    if not output.is_relative_to(private_root):
        raise SystemExit("Inventory output must remain inside ignored .data/tasteduel-cloud-review.")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = Inventory().collect()
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output.relative_to(ROOT)), "requests": result["http_requests"], "errors": result["errors"]}, indent=2))


if __name__ == "__main__":
    main()

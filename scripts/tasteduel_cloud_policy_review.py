"""Bounded exact-owned IAM and filtered alert metadata; no IAM mutation."""

import json
from pathlib import Path

from tasteduel_cloud_inventory import Inventory, PROJECT, REGION

ROOT = Path(__file__).resolve().parents[1]


def selected_policy(value):
    rows = []
    for binding in value.get("bindings", []):
        members = [member for member in binding.get("members", []) if member in ("allUsers", "allAuthenticatedUsers") or (
            member.startswith("serviceAccount:accesslife-") and member.endswith(f"@{PROJECT}.iam.gserviceaccount.com")
        )]
        if members:
            entry = {"role": binding.get("role"), "members": members}
            if "condition" in binding:
                entry["conditional"] = True
                entry["condition"] = {
                    key: value for key, value in binding["condition"].items()
                    if key in {"title", "expression"} and isinstance(value, str) and len(value) <= 4096
                }
            rows.append(entry)
    return rows


def main():
    client = Inventory()
    policies = {}
    root = f"projects/{PROJECT}/locations/{REGION}"
    for name in ("accesslife-web", "accesslife-api", "accesslife-worker"):
        policies[name] = selected_policy(client.get(f"https://run.googleapis.com/v2/{root}/services/{name}:getIamPolicy"))
    for name in ("accesslife-qloo-api-key", "accesslife-db-password", "accesslife-database-url", "accesslife-worker-token"):
        policies[name] = selected_policy(client.get(f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets/{name}:getIamPolicy"))
    for name in ("docs", "backups", "tfstate"):
        bucket = f"accesslife-{name}-{PROJECT}"
        policies[bucket] = selected_policy(client.get(f"https://storage.googleapis.com/storage/v1/b/{bucket}/iam"))
    policies["registry"] = selected_policy(client.get(f"https://artifactregistry.googleapis.com/v1/{root}/repositories/accesslife:getIamPolicy"))
    alerts = client.get(
        f"https://monitoring.googleapis.com/v3/projects/{PROJECT}/alertPolicies",
        filter='display_name=starts_with("AccessLife")',
        fields="alertPolicies(name,displayName,enabled,combiner,userLabels),nextPageToken",
    )
    result = {
        "policies": policies,
        "dedicated_alert_policies": [row for row in alerts.get("alertPolicies", []) if row.get("displayName", "").startswith("AccessLife")],
        "alerts_have_more": bool(alerts.get("nextPageToken")),
        "requests": client.requests, "errors": client.errors,
        "inherited_iam_scope": "resource policies only; project SA grants reviewed separately",
        "effective_access_evaluated": False,
    }
    target = ROOT / ".data/tasteduel-cloud-review/policy-metadata.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"requests": client.requests, "errors": client.errors, "dedicated_alert_count": len(result["dedicated_alert_policies"])}))


if __name__ == "__main__":
    main()

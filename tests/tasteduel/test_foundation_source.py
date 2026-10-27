"""Foundation boundary checks; no state reads, credentials or cloud mutations.

These protect source review boundaries, not a substitute for a refreshed saved
Terraform plan or live database privilege/WIF verification.
"""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "infra/terraform/modules/tasteduel-foundation"


def source(path):
    return path.read_text(encoding="utf-8")


def test_foundation_cannot_create_runtime_infrastructure_or_read_secret_payloads():
    text = "\n".join(source(path) for path in MODULE.glob("*.tf"))
    resource_types = set(re.findall(r'resource\s+"([^"]+)"', text))
    assert resource_types <= {
        "google_service_account", "google_sql_database", "google_sql_user",
        "google_secret_manager_secret", "google_secret_manager_secret_version",
        "google_secret_manager_secret_iam_member", "google_project_iam_member",
        "google_artifact_registry_repository_iam_member",
        "google_service_account_iam_member", "google_project_iam_custom_role",
    }
    assert not re.search(r'data\s+"google_secret_manager_secret_version', text)
    assert not re.search(r"\b(secret_data|password)\s*=", text)
    assert "secret_data_wo" in text and "password_wo" in text
    assert "allUsers" not in text and "allAuthenticatedUsers" not in text
    assert not re.search(r'roles/(?:owner|editor|run.admin|cloudsql.admin|iam.securityAdmin)', text)


def test_new_database_identity_and_credentials_are_separate_from_legacy():
    text = source(MODULE / "main.tf")
    assert re.search(r'resource "google_sql_database" "app"\s*\{[^}]*name\s*=\s*"tasteduel"', text)
    assert "tasteduel_runtime" in text
    assert "tasteduel_migrat" in text
    assert "accesslife-db-password" not in text
    assert "accesslife-database-url" not in text
    variables = source(MODULE / "variables.tf")
    assert variables.count("ephemeral = true") == 2
    assert "var.migration_password != var.runtime_password" in variables
    root = source(ROOT / "infra/terraform/tasteduel-foundation.tf")
    assert re.search(r'variable "tasteduel_foundation_enabled"\s*\{[^}]*default\s*=\s*false', root)
    assert "depends_on" in root and "terraform_data.cost_gate" in root


def test_identity_probe_is_manual_exact_repository_and_non_deploying():
    text = source(ROOT / ".github/workflows/foundation-auth.yml")
    assert "workflow_dispatch:" in text
    assert "github.repository_id == '1431472864'" in text
    assert "github.repository_owner_id == '60200140'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "vars.FOUNDATION_AUTH_ENABLED == 'true'" in text
    assert "environment: foundation-review" in text
    assert "id-token: write" in text
    assert "gcloud artifacts repositories describe" in text
    assert not re.search(r"terraform\s+(?:apply|destroy)|gcloud\s+(?:run|sql|secrets)\s", text)
    assert "print-access-token" not in text


def test_retired_workflow_cannot_invoke_legacy_ingestion_or_deployment():
    text = source(ROOT / ".github/workflows/cloud-release.yml")
    assert "workflow_dispatch:" in text
    assert "id-token: write" not in text
    assert not re.search(r"gcloud\s|terraform\s+(?:apply|destroy)|docker\s+push|accesslife\.worker|accesslife\.adapters", text)

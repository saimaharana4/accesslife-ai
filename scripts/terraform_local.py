"""Run pinned Terraform using ADC and an ephemeral, Secret Manager sourced password.

Example: uv run python scripts/terraform_local.py plan -out=accesslife.tfplan
Requires the dated cost review; this script never provisions without explicit apply.
"""

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))
from accesslife.adapters.secrets import read_secret  # noqa: E402


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {
        "init",
        "plan",
        "apply",
        "show",
        "output",
        "validate",
        "state",
    }:
        raise SystemExit("Supply a Terraform command explicitly; no default mutation is performed.")
    project = "project-bb13ecd8-9d67-408d-9a7"
    adc = Path(os.environ.get("GCP_ADC_DIRECTORY", str(Path(os.environ["APPDATA"]) / "gcloud"))).resolve()
    if not (adc / "application_default_credentials.json").is_file():
        raise SystemExit("ADC missing; authenticate without creating a service-account key.")
    # Windows normalizes environment keys to uppercase; Terraform variable names
    # are case sensitive inside Linux. Keep the TF_VAR prefix, normalize its suffix.
    env = {
        (key[:7] + key[7:].lower() if key.startswith("TF_VAR_") else key): value
        for key, value in os.environ.items()
    }
    controls = ROOT / ".env.cloud"
    if controls.exists():
        for line in controls.read_text(encoding="utf-8").splitlines():
            if line.startswith("TF_VAR_") and "=" in line:
                name, value = line.split("=", 1)
                if name.lower() != "tf_var_cost_review_passed":
                    env.setdefault(name[:7] + name[7:].lower(), value.strip())
    if sys.argv[1] in {"plan", "apply"}:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        response = AuthorizedSession(credentials).get(
            f"https://cloudbilling.googleapis.com/v1/projects/{project}/billingInfo", timeout=15
        )
        response.raise_for_status()
        env.setdefault("TF_VAR_billing_account", response.json()["billingAccountName"].split("/")[-1])
        env["TF_VAR_database_password"] = read_secret(f"projects/{project}/secrets/accesslife-db-password")
    if sys.argv[1] in {"plan", "apply"}:
        required = ["TF_VAR_web_image", "TF_VAR_api_image", "TF_VAR_public_url", "TF_VAR_budget_alert_units"]
        if any(not env.get(name) for name in required):
            raise SystemExit(
                "Set reviewed image digests, canonical URL and account-currency alert subtotal in TF_VAR controls."
            )
    # The reviewed gate is explicit at invocation; do not override Terraform's false default here.
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{ROOT / 'infra/terraform'}:/work",
        "-v",
        f"{adc}:/credentials:ro",
        "-w",
        "/work",
        "-e",
        "GOOGLE_APPLICATION_CREDENTIALS=/credentials/application_default_credentials.json",
    ]
    for key in [k for k in env if k.startswith("TF_VAR_")]:
        cmd += ["-e", key]
    cmd += ["hashicorp/terraform:1.13.3", *sys.argv[1:]]
    raise SystemExit(subprocess.run(cmd, env=env).returncode)


if __name__ == "__main__":
    main()

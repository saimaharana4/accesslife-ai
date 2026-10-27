"""Backend-free schema and actual cost-gate checks; no ADC, state or cloud calls.

Uses isolated copies of tracked Terraform configuration, never the historical
plan files/backend initialization. Gate tests plan only built-in terraform_data.
"""

from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "hashicorp/terraform:1.13.3"


def terraform(directory, *args, providers=False):
    command = ["docker", "run", "--rm", "-v", f"{directory}:/work", "-w", "/work"]
    cache = ROOT / "infra/terraform/.terraform/providers"
    if providers and cache.is_dir():
        command += ["-v", f"{cache}:/providers:ro"]
    command += [IMAGE, *args]
    subprocess.run(command, check=True)


def main():
    target = ROOT / ".data/tasteduel-cloud-review/terraform-validation"
    target.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "infra/terraform").glob("*.tf"):
        shutil.copyfile(path, target / path.name)
    modules = ROOT / "infra/terraform/modules"
    if modules.is_dir():
        shutil.copytree(modules, target / "modules", dirs_exist_ok=True)
    shutil.copyfile(ROOT / "infra/terraform/.terraform.lock.hcl", target / ".terraform.lock.hcl")
    init_args = ["init", "-backend=false", "-input=false", "-lockfile=readonly"]
    if (ROOT / "infra/terraform/.terraform/providers").is_dir():
        init_args += ["-plugin-dir=/providers"]
    terraform(target, *init_args, providers=True)
    terraform(target, "validate", "-no-color", providers=True)

    # Extract the actual dependency-free guard block, not a second hand-written
    # implementation. Its true/false outcomes are tested without google resources.
    source = (ROOT / "infra/terraform/main.tf").read_text(encoding="utf-8")
    gate = source.split('resource "terraform_data" "cost_gate"', 1)[1].split('resource "google_service_account"', 1)[0]
    guards = target.parent / "gate-tests"
    guards.mkdir(exist_ok=True)
    variables = '''
variable "cost_review_passed" { type = bool }
variable "billing_reconciled" { type = bool }
variable "budget_usd" { type = number }
variable "reviewed_total_usd" { type = number }
variable "reviewed_through_utc" { type = string }
'''
    (guards / "main.tf").write_text(variables + '\nresource "terraform_data" "cost_gate"' + gate, encoding="utf-8")
    (guards / "gate.tftest.hcl").write_text('''
variables {
  cost_review_passed = true
  billing_reconciled = true
  budget_usd = 90
  reviewed_total_usd = 49
  reviewed_through_utc = "2026-11-07T04:45:00Z"
}
run "unreconciled_billing_is_blocked" {
  command = plan
  variables { billing_reconciled = false }
  expect_failures = [terraform_data.cost_gate]
}
run "over_envelope_is_blocked" {
  command = plan
  variables { reviewed_total_usd = 91 }
  expect_failures = [terraform_data.cost_gate]
}
run "ceiling_cannot_be_raised_by_input" {
  command = plan
  variables { budget_usd = 91 }
  expect_failures = [terraform_data.cost_gate]
}
run "short_horizon_is_blocked" {
  command = plan
  variables { reviewed_through_utc = "2026-11-06T04:45:00Z" }
  expect_failures = [terraform_data.cost_gate]
}
run "explicit_review_is_required" {
  command = plan
  variables { cost_review_passed = false }
  expect_failures = [terraform_data.cost_gate]
}
run "synthetic_complete_review_can_plan" {
  command = plan
}
''', encoding="utf-8")
    terraform(guards, "init", "-backend=false", "-input=false")
    terraform(guards, "test", "-no-color")
    subprocess.run([
        "docker", "compose", "--env-file", str(ROOT / "compose.tasteduel.env"),
        "-f", str(ROOT / "compose.yaml"), "config", "--quiet",
    ], check=True, cwd=ROOT)
    print("Backend-free Terraform, six synthetic cost-gate plans and Compose validation passed; no apply or cloud plan.")


if __name__ == "__main__":
    main()

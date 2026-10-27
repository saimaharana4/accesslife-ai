"""Narrow GitHub foundation coordination; credentials remain in process memory.

Run only after the separately reviewed foundation apply. This script does not
push source, deploy, grant cloud IAM, read secret payloads or upload artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.request

OWNER = "saimaharana4"
OLD_NAME = "accesslife-ai"
NEW_NAME = "taste-duel"
REPOSITORY_ID = 1431472864
OWNER_ID = 60200140
ENVIRONMENT = "foundation-review"
VARIABLES = {
    "TASTEDUEL_WIF_PROVIDER": (
        "projects/902056825143/locations/global/"
        "workloadIdentityPools/accesslife-github/providers/github"
    ),
    "TASTEDUEL_DEPLOY_SERVICE_ACCOUNT": (
        "tasteduel-deploy@project-bb13ecd8-9d67-408d-9a7.iam.gserviceaccount.com"
    ),
    "FOUNDATION_AUTH_ENABLED": "true",
}


class GitHub:
    def __init__(self) -> None:
        environment = os.environ.copy()
        environment.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            text=True,
            capture_output=True,
            timeout=30,
            env=environment,
            check=False,
        )
        credentials = dict(
            line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
        )
        self._token = credentials.get("password")
        if result.returncode or not self._token:
            raise RuntimeError("Existing GitHub credential helper is unavailable")

    def request(
        self, path: str, method: str = "GET", body: dict | None = None
    ) -> tuple[int, dict]:
        if not path.startswith(f"/repos/{OWNER}/"):
            raise RuntimeError("Request falls outside the reviewed owner repository scope")
        request = urllib.request.Request(
            "https://api.github.com" + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": "Bearer " + self._token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()
                return response.status, json.loads(content) if content else {}
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return 404, {}
            raise RuntimeError(f"GitHub request failed: HTTP {error.code}, {method} {path}") from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError(f"GitHub request failed: network/deadline, {method} {path}") from None


def verified_repository(client: GitHub, name: str) -> tuple[str, dict]:
    path = f"/repos/{OWNER}/{name}"
    status, repository = client.request(path)
    if status != 200:
        raise RuntimeError("Expected repository is unavailable")
    if (
        repository.get("id") != REPOSITORY_ID
        or repository.get("owner", {}).get("id") != OWNER_ID
        or repository.get("default_branch") != "main"
        or repository.get("visibility") != "public"
    ):
        raise RuntimeError("Repository identity, branch or public visibility mismatch")
    return path, repository


def rename(client: GitHub) -> None:
    path, _ = verified_repository(client, OLD_NAME)
    status, target = client.request(f"/repos/{OWNER}/{NEW_NAME}")
    if status == 200:
        if target.get("id") == REPOSITORY_ID:
            verified_repository(client, NEW_NAME)
        else:
            raise RuntimeError("Target repository already exists; refusing overwrite")
    elif status == 404:
        client.request(path, "PATCH", {"name": NEW_NAME})
        verified_repository(client, NEW_NAME)
    else:
        raise RuntimeError("Target-name availability is unverified")
    subprocess.run(
        ["git", "remote", "set-url", "origin", f"https://github.com/{OWNER}/{NEW_NAME}.git"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    print(json.dumps({"repository": f"{OWNER}/{NEW_NAME}", "id": REPOSITORY_ID, "remote_updated": True}))


def configure(client: GitHub) -> None:
    path, _ = verified_repository(client, NEW_NAME)
    environment_path = f"{path}/environments/{ENVIRONMENT}"
    status, existing = client.request(environment_path)
    protections = existing.get("protection_rules", []) if status == 200 else []
    if protections:
        raise RuntimeError("Existing environment protection needs review; refusing to replace it")
    client.request(
        environment_path,
        "PUT",
        {"deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}},
    )
    policies_path = environment_path + "/deployment-branch-policies"
    _, policies = client.request(policies_path)
    branches = policies.get("branch_policies", [])
    if any(p.get("name") != "main" or p.get("type", "branch") != "branch" for p in branches):
        raise RuntimeError("Unexpected environment branch policies; refusing automatic changes")
    if not branches:
        client.request(policies_path, "POST", {"name": "main", "type": "branch"})
    for name, value in VARIABLES.items():
        variable_path = f"{path}/actions/variables/{name}"
        status, _ = client.request(variable_path)
        if status == 404:
            client.request(f"{path}/actions/variables", "POST", {"name": name, "value": value})
        elif status == 200:
            client.request(variable_path, "PATCH", {"name": name, "value": value})
        else:
            raise RuntimeError("Cannot verify repository variable")
    _, environment = client.request(environment_path)
    _, policies = client.request(policies_path)
    if environment.get("deployment_branch_policy") != {"protected_branches": False, "custom_branch_policies": True}:
        raise RuntimeError("Environment branch restriction verification failed")
    if [(p.get("name"), p.get("type", "branch")) for p in policies.get("branch_policies", [])] != [("main", "branch")]:
        raise RuntimeError("Environment must permit only main branch")
    for name, value in VARIABLES.items():
        _, variable = client.request(f"{path}/actions/variables/{name}")
        if variable.get("value") != value:
            raise RuntimeError("Repository reference variable verification failed")
    print(json.dumps({"environment": ENVIRONMENT, "branches": ["main"], "variable_names": list(VARIABLES), "verified": True}))


def dispatch(client: GitHub, expected_sha: str) -> None:
    path, _ = verified_repository(client, NEW_NAME)
    status, commit = client.request(path + "/commits/main")
    if status != 200 or commit.get("sha") != expected_sha:
        raise RuntimeError("Remote main is not the reviewed commit; refusing dispatch")
    workflow = path + "/actions/workflows/foundation-auth.yml"
    status, metadata = client.request(workflow)
    if status != 200 or metadata.get("state") != "active":
        raise RuntimeError("Reviewed auth-only workflow is not active on the remote")
    client.request(workflow + "/dispatches", "POST", {"ref": "main"})
    print(json.dumps({"workflow": "foundation-auth.yml", "ref": "main", "dispatch_requested": True, "success_not_yet_verified": True}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["rename", "configure", "dispatch"])
    parser.add_argument("--execute-after-reviewed-foundation", action="store_true")
    parser.add_argument("--expected-sha", help="Reviewed published main commit required for dispatch")
    arguments = parser.parse_args()
    if not arguments.execute_after_reviewed_foundation:
        parser.error("Mutation disabled: separately confirmed reviewed foundation application is required")
    if arguments.action == "dispatch" and not arguments.expected_sha:
        parser.error("Auth dispatch requires --expected-sha of the reviewed published commit")
    try:
        client = GitHub()
        if arguments.action == "dispatch":
            dispatch(client, arguments.expected_sha)
        else:
            {"rename": rename, "configure": configure}[arguments.action](client)
    except (RuntimeError, subprocess.SubprocessError) as error:
        # No raw HTTP body, credential-helper output or subprocess diagnostics.
        if isinstance(error, RuntimeError):
            parser.exit(1, f"{error}\n")
        parser.exit(1, "Local Git coordination failed; inspect configuration without exposing credentials\n")


if __name__ == "__main__":
    main()

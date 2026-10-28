"""Publish two immutable images from an exact successful-CI Git archive.

No deployment, Terraform apply, credential payload lookup or working-tree copy.
Publishing requires --execute plus the refreshed approved cumulative cost record.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tarfile
from urllib.request import Request, urlopen

from tasteduel_foundation_plan import PROJECT, REGION, ROOT, PlanBlocked, approved_variables

REPOSITORY = "saimaharana4/taste-duel"
REGISTRY = f"{REGION}-docker.pkg.dev/{PROJECT}/accesslife"


def verified_ci(run: dict, source_sha: str) -> dict:
    if (not re.fullmatch(r"[0-9a-f]{40}", source_sha)
            or run.get("head_sha") != source_sha or run.get("head_branch") != "main"
            or run.get("status") != "completed" or run.get("conclusion") != "success"
            or run.get("event") != "push"
            or run.get("path") != ".github/workflows/ci.yml"
            or run.get("repository", {}).get("full_name") != REPOSITORY):
        raise PlanBlocked("SUCCESSFUL_CURRENT_SOURCE_CI_REQUIRED")
    return {"id": run["id"], "html_url": run["html_url"], "head_sha": source_sha,
            "status": "completed", "conclusion": "success"}


def process(arguments: list[str], *, binary: bool = False) -> str | bytes:
    executable = shutil.which(arguments[0])
    if executable is None:
        raise PlanBlocked("IMAGE_TOOL_UNAVAILABLE")
    arguments = [executable, *arguments[1:]]
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=not binary)
    if result.returncode:
        # Docker/gcloud/git diagnostics can contain local credential context.
        raise PlanBlocked("IMAGE_EXECUTION_STAGE_FAILED")
    return result.stdout


def archive_context(source_sha: str, target: Path) -> str:
    current = process(["git", "rev-parse", "HEAD"]).strip()
    if current != source_sha:
        raise PlanBlocked("SOURCE_NOT_CURRENT_COMMIT")
    # Uncommitted user notes may remain, but cannot enter this build. Reject
    # uncommitted production inputs so an old green SHA is not misrepresented.
    dirty = process(["git", "diff", "HEAD", "--name-only", "--", "apps", "runtime", "packages",
                     "infra/containers", "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", ".dockerignore"])
    if dirty.strip():
        raise PlanBlocked("PRODUCTION_INPUTS_NOT_COMMITTED")
    untracked = process(["git", "ls-files", "--others", "--exclude-standard", "--", "apps", "runtime", "packages", "infra/containers"])
    if untracked.strip():
        raise PlanBlocked("PRODUCTION_INPUTS_NOT_COMMITTED")
    data = process(["git", "archive", "--format=tar", source_sha], binary=True)
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        archive.extractall(target, filter="data")
    return hashlib.sha256(data).hexdigest()


def immutable_reference(package: str, digest: str) -> str:
    if package not in {"tasteduel-api", "tasteduel-web"} or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise PlanBlocked("IMAGE_METADATA_DIGEST_INVALID")
    return f"{REGISTRY}/{package}@{digest}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--ci-run-id", type=int, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        review = json.loads(args.review.read_text(encoding="utf-8"))
        approved_variables(review)
        if not args.execute:
            print(json.dumps({"status": "PREPARED_ONLY", "publishing": False, "deployment": False}))
            return 0
        request = Request(f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{args.ci_run_id}",
                          headers={"Accept": "application/vnd.github+json", "User-Agent": "TasteDuel-release-review"})
        with urlopen(request, timeout=15) as response:
            ci = verified_ci(json.load(response), args.source_sha)
        directory = ROOT / ".data/tasteduel-cloud-review" / ("release-images-" + secrets.token_hex(8))
        directory.mkdir(parents=True, exist_ok=False)
        context_hash = archive_context(args.source_sha, directory / "context")
        process(["gcloud", "auth", "configure-docker", f"{REGION}-docker.pkg.dev", "--quiet"])
        images = {}
        for name, dockerfile in (("api", "tasteduel-api.Dockerfile"), ("web", "web.Dockerfile")):
            package = "tasteduel-" + name
            tag = f"{REGISTRY}/{package}:sha-{args.source_sha}"
            metadata = directory / (name + "-build-metadata.json")
            process(["docker", "buildx", "build", "--platform=linux/amd64", "--pull", "--provenance=mode=min",
                     "--build-arg", "SOURCE_REVISION=" + args.source_sha, "--metadata-file", str(metadata),
                     "--file", str(directory / "context/infra/containers" / dockerfile),
                     "--tag", tag, "--push", str(directory / "context")])
            digest = json.loads(metadata.read_text(encoding="utf-8")).get("containerimage.digest", "")
            reference = immutable_reference(package, digest)
            # Read the exact published artifact before accepting build metadata.
            published = process(["gcloud", "artifacts", "docker", "images", "describe", reference,
                                 "--project", PROJECT, "--format=value(image_summary.digest)"])
            if published.strip() != digest:
                raise PlanBlocked("PUBLISHED_DIGEST_NOT_VERIFIED")
            images[name] = {"reference": reference, "digest": digest}
        record = {"source_sha": args.source_sha, "ci": ci, "source_archive_sha256": context_hash,
                  "images": images, "platform": "linux/amd64", "deployed": False,
                  "cost_reviewed_total_usd": review["reviewed_total_usd"], "cost_ceiling_usd": 90}
        output = directory / "images.json"
        output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "IMAGES_PUBLISHED", "record": str(output), "deployed": False}))
        return 0
    except Exception as failure:
        reason = str(failure) if isinstance(failure, PlanBlocked) else "IMAGE_PREPARATION_FAILED_" + type(failure).__name__
        print(json.dumps({"status": "BLOCKED", "reason_code": reason, "deployed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

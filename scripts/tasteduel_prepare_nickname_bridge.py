"""Prepare a reviewable compatibility source archive; never build/push/deploy.

The old UI/API shape is retained. New optional response fields are accepted by
the web proxy, and legacy API reads enforce lifecycle functions when installed.
"""

import ast
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".data/tasteduel-named-duels/compatibility-bridge-td0014-v3"


def main():
    baseline = json.loads((ROOT / "infra/releases/production-hotfix-2026-10-29.json").read_text(encoding="utf-8"))["source_sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", baseline):
        raise RuntimeError("A recorded immutable baseline is required")
    if OUTPUT.exists():
        raise RuntimeError("Bridge output already exists; preserve it for review")
    archive = subprocess.run(["git", "archive", "--format=tar", baseline], cwd=ROOT, check=True, capture_output=True).stdout
    OUTPUT.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(OUTPUT, filter="data")
    api = OUTPUT / "apps/api/src/tasteduel/api/main.py"
    config = OUTPUT / "apps/api/src/tasteduel/config.py"
    settings = config.read_text(encoding="utf-8")
    settings = settings.replace("from pydantic import Field, SecretStr", "from pydantic import AwareDatetime, Field, SecretStr")
    settings = settings.replace("    session_ttl_seconds: int = 86400", "    session_ttl_seconds: int = 86400\n    session_admission_closes_at: AwareDatetime | None = None\n    session_hard_closes_at: AwareDatetime | None = None")
    config.write_text(settings, encoding="utf-8")
    content = api.read_text(encoding="utf-8")
    assert content.count('if revision != "td0011":') == 1
    content = content.replace('if revision != "td0011":', 'if revision not in {"td0011", "td0012", "td0013", "td0014"}:')
    marker = "                or row.expires_at <= datetime.now(UTC)\n"
    assert marker in content
    content = content.replace(marker, marker + '''                or (db.scalar(text("SELECT to_regprocedure('tasteduel.session_live(uuid)')")) is not None
                    and not db.scalar(text("SELECT tasteduel.session_live(:owner)"), {"owner": owner}))
''', 1)
    api.write_text(content, encoding="utf-8")
    create_marker = '        token = f"{owner}.{secrets.token_urlsafe(32)}"\n        now = datetime.now(UTC)\n'
    assert create_marker in content
    content = content.replace(create_marker, create_marker + '''        if ((settings.session_admission_closes_at is not None and now >= settings.session_admission_closes_at)
            or (settings.session_hard_closes_at is not None and now >= settings.session_hard_closes_at)):
            raise AppError(503, "PLAY_CLOSED", "Play has closed for this demo.")
''')
    content = content.replace("expires_at=now + timedelta(seconds=settings.session_ttl_seconds)",
        "expires_at=min(now + timedelta(seconds=settings.session_ttl_seconds), settings.session_hard_closes_at or datetime.max.replace(tzinfo=UTC))")
    # Preserve exact legacy wire bodies while the bridge BFF accepts the next
    # API's optional public additions. Do not omit any existing default fields.
    content = content.replace("response_model=s.SessionPublic,", 'response_model=s.SessionPublic, response_model_exclude={"display_name"},')
    content = content.replace("response_model=s.ChallengeInvitationPublic,", 'response_model=s.ChallengeInvitationPublic, response_model_exclude={"creator_name"},')
    content = content.replace("response_model=s.ChallengeCreatedPublic,", 'response_model=s.ChallengeCreatedPublic, response_model_exclude={"invitation": {"creator_name"}},')
    api.write_text(content, encoding="utf-8")
    gameplay = OUTPUT / "apps/api/src/tasteduel/application/gameplay.py"
    content = gameplay.read_text(encoding="utf-8")
    marker = "        if row is None or row.revoked_at is not None or row.expires_at <= now:\n"
    assert marker in content
    content = content.replace(marker, '''        lifecycle_missing = db.scalar(text("SELECT to_regprocedure('tasteduel.session_live(uuid)')")) is None
        if row is None or row.revoked_at is not None or row.expires_at <= now or (
            not lifecycle_missing and not db.scalar(text("SELECT tasteduel.session_live(:id)"), {"id": session_id})
        ):
''', 1)
    gameplay.write_text(content, encoding="utf-8")
    challenges = OUTPUT / "apps/api/src/tasteduel/application/challenges.py"
    content = challenges.read_text(encoding="utf-8")
    content = content.replace("from sqlalchemy import null, select, text", "from sqlalchemy import null, select, text\nfrom sqlalchemy.orm.attributes import set_committed_value")
    helper = '''def effective_deadline(db, challenge):
    if challenge is not None and db.scalar(text("SELECT to_regprocedure('tasteduel.challenge_deadline(uuid)')")) is not None:
        deadline = db.scalar(text("SELECT tasteduel.challenge_deadline(:id)"), {"id": challenge.id})
        if deadline is not None:
            set_committed_value(challenge, "expires_at", min(challenge.expires_at, deadline))


'''
    content = content.replace("def active(challenge, now):", helper + "def active(challenge, now):")
    content = re.sub(r"^(\s*)active\(challenge, (.+)\)$", r"\1effective_deadline(db, challenge)\n\1active(challenge, \2)", content, flags=re.MULTILINE)
    challenges.write_text(content, encoding="utf-8")
    accounting = OUTPUT / "apps/api/src/tasteduel/application/event_accounting.py"
    content = accounting.read_text(encoding="utf-8")
    marker = '    now = db.scalar(select(text("clock_timestamp()")))\n'
    assert marker in content
    content = content.replace(marker, marker + '''    # Migration td0012 installs activity with session_live atomically. Keep
    # legacy rollback actions live, committing the touch with their event.
    if db.scalar(text("SELECT to_regprocedure('tasteduel.session_live(uuid)')")) is not None:
        db.execute(text("UPDATE tasteduel.sessions SET last_activity_at=:now WHERE id=:owner"),
                   {"now": now, "owner": owner})
''')
    accounting.write_text(content, encoding="utf-8")
    schemas = OUTPUT / "apps/api/src/tasteduel/api/schemas.py"
    content = schemas.read_text(encoding="utf-8")
    # Retain the legacy operation/request surface. Only these public response
    # additions are needed while a new API serves the old web revision. Export
    # from the bridge API itself so generated-contract CI remains meaningful.
    nickname = 'Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=24)]'
    content = content.replace("class SessionPublic(StrictRecord):\n", f"class SessionPublic(StrictRecord):\n    display_name: {nickname} | None = None\n")
    content = content.replace("class ChallengeInvitationPublic(StrictRecord):\n", f"class ChallengeInvitationPublic(StrictRecord):\n    creator_name: {nickname} | None = None\n")
    schemas.write_text(content, encoding="utf-8")
    subprocess.run(["uv", "run", "--project", str(ROOT / "runtime/python"), "--frozen", "python",
                    str(OUTPUT / "scripts/export_contracts.py")], cwd=OUTPUT, check=True)
    contracts = OUTPUT / "packages/contracts/openapi.json"
    declarations = OUTPUT / "apps/web/src/lib/api/schema.d.ts"
    corepack = shutil.which("corepack")
    if corepack is None:
        raise RuntimeError("Locked pnpm tooling is required to generate bridge contracts")
    subprocess.run([corepack, "pnpm", "exec", "openapi-typescript", str(contracts), "-o", str(declarations)], cwd=ROOT, check=True)
    # Run from the archive so the workspace .gitignore cannot hide this output.
    subprocess.run(["node", str(ROOT / "node_modules/prettier/bin/prettier.cjs"), "--write", str(declarations)], cwd=OUTPUT, check=True)
    for file in (api, config, gameplay, challenges, accounting, schemas):
        ast.parse(file.read_text(encoding="utf-8"))
    facts = {"baseline_source_sha": baseline, "supported_schemas": ["td0011", "td0012", "td0013", "td0014"],
        "public_ui": "unchanged baseline", "optional_contract_sha256": hashlib.sha256(contracts.read_bytes()).hexdigest(),
        "built": False, "deployed": False}
    (OUTPUT / "nickname-bridge-review.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(facts))


if __name__ == "__main__":
    main()

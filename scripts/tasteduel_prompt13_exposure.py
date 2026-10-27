"""Scan emitted public assets without printing a matched credential or payload.

This is a bounded pattern/canary check, not a proof that every secret is detectable.
Authorized post-answer winning_choice_id is a public contract, not an answer value.
"""

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "apps/web/.next/static"
PATTERNS = {
    "credential": re.compile(
        rb"sk-proj-[A-Za-z0-9_-]{25,}|gsk_[A-Za-z0-9]{25,}|hack_[a-fA-F0-9]{32,}"
        rb"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "server_private_contract": re.compile(
        rb"chain_of_thought|thought_signature|raw_(?:provider|qloo)_payload|raw_payload"
        rb"|winner_entity_id|private_pool|full_receipt"
    ),
    "server_provider_destination": re.compile(rb"hackathon\.api\.qloo\.com|aiplatform\.googleapis\.com"),
    "private_test_canary": re.compile(rb"PRIVATE_QLOO_RESPONSE_MARKER|PRIVATE_PROVIDER_DIAGNOSTIC"),
}


def main():
    if not PUBLIC.is_dir():
        raise RuntimeError("Build the production application first")
    files = [p for p in PUBLIC.rglob("*") if p.is_file() and p.suffix in {".js", ".json", ".html", ".map"}]
    findings = []
    for path in files:
        data = path.read_bytes()
        for name, pattern in PATTERNS.items():
            if pattern.search(data):
                findings.append({"path": path.relative_to(ROOT).as_posix(), "kind": name})
    result = {"public_files_scanned": len(files), "findings": findings, "pattern_only": True}
    out = ROOT / ".data/tasteduel-prompt13/public-exposure.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"public_files_scanned": len(files), "finding_count": len(findings)}))
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Export/check the actual Taste Duel API without a database/provider connection."""

import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))
from tasteduel.api.main import app  # noqa: E402

output = Path("packages/contracts/openapi.json")
output.parent.mkdir(parents=True, exist_ok=True)
schema = app.openapi()
if not schema.get("paths") or not all(path.startswith("/v1/") for path in schema["paths"]):
    raise RuntimeError("The application must export real Taste Duel endpoint paths.")
if "CurationReceipt" in schema.get("components", {}).get("schemas", {}):
    raise RuntimeError("Private receipt must not be an HTTP schema.")
content = json.dumps(schema, indent=2, sort_keys=True) + "\n"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
if args.check:
    if not output.exists() or output.read_text(encoding="utf-8") != content:
        raise SystemExit("Application OpenAPI drift: run corepack pnpm contracts.")
    print("Taste Duel application OpenAPI is current; no database/provider connection used.")
else:
    output.write_text(content, encoding="utf-8")
    print(f"Exported {len(schema['paths'])} Taste Duel paths; private receipt excluded.")

"""Export the API contract without opening a database connection."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))
from accesslife.api.main import app  # noqa: E402

output = Path("packages/contracts/openapi.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")

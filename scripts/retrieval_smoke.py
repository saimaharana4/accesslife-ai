"""Small index/attribution smoke, not a held-out quality benchmark."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))
from accesslife.adapters.retrieval import retrieve  # noqa: E402

cases = [
    ("london", "British Museum entrance lifts"),
    ("new-york", "MoMA accessible restrooms"),
    ("paris", "Orsay elevators ramps"),
    ("berlin", "Jewish Museum accessible bathrooms"),
    ("chicago", "Field Museum East entrance"),
]
results = []
for city, query in cases:
    result = retrieve(query, city)
    assert result["status"] == "indexed" and result["dimensions"] == 384
    assert result["passages"] and all(p["source_url"].startswith("https://") for p in result["passages"])
    results.append({"city": city, "attributed_passages": len(result["passages"]), "dimensions": 384})
print(
    json.dumps(
        {"kind": "five-query index and attribution smoke; not Recall@5 evaluation", "results": results}
    )
)

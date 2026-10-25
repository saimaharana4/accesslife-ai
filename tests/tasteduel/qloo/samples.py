"""Entirely invented wire examples, not retained Qloo response data."""

from copy import deepcopy

SEED_ID = "10000000-0000-4000-8000-000000000001"
FIRST_ID = "20000000-0000-4000-8000-000000000001"
SECOND_ID = "20000000-0000-4000-8000-000000000002"
CONTEXT_HASH = "d" * 64


def entity(identifier=FIRST_ID, *, domain="movie", score=0.8, name="Invented Film A"):
    return {
        "entity_id": identifier,
        "name": name,
        "type": "urn:entity",
        "subtype": "urn:entity:" + domain,
        "affinity": score,
    }


def envelope(status="ok", *, operation="recommend", results=None):
    rows = (
        results if results is not None else [entity(), entity(SECOND_ID, score=0.3, name="Invented Film B")]
    )
    value = {
        "schema_version": "1.0-preview.1",
        "operation": operation,
        "status": status,
        "results": deepcopy(rows),
        "result_count": len(rows),
        "execution": {
            "transport": "mcp",
            "transport_name": "synthetic-only-test",
            "correlation_id": "synthetic-correlation",
            "duration_ms": 1,
        },
        "interpretation": {"target_type": "urn:entity:movie"},
        "provenance": {
            "source": "Qloo API",
            "endpoint": "/v2/insights" if operation == "recommend" else "/entities",
            "documentation": "https://docs.qloo.com/reference/insights-api-deep-dive",
            "requests": [],
        },
    }
    if status == "error":
        value["results"] = []
        value["result_count"] = 0
        value["error"] = {
            "code": "SYNTHETIC_UNAVAILABLE",
            "layer": "provider",
            "retryable": True,
            "recovery": "Retry later.",
        }
    if status == "empty":
        value["results"] = []
        value["result_count"] = 0
    if status == "needs_input":
        value["results"] = []
        value["result_count"] = 0
        value["resolution"] = {
            "issues": [
                {
                    "input": "Invented ambiguous name",
                    "kind": "ambiguous",
                    "input_kind": "entity",
                    "field": "entity",
                    "scope": "urn:entity:movie",
                    "candidates": [
                        {"id": FIRST_ID, "name": "Invented Film A", "type": "urn:entity:movie"},
                        {"id": SECOND_ID, "name": "Invented Film B", "type": "urn:entity:movie"},
                    ],
                }
            ],
        }
    return value

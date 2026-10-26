"""Provider wire data must cross a deliberate typed, private boundary."""

from dataclasses import asdict
import json
from uuid import UUID

import pytest

from tasteduel.adapters.qloo.normalization import normalize_result

from .samples import CONTEXT_HASH, FIRST_ID, SECOND_ID, entity, envelope


def normalize(value, *, operation="recommend", domain="movie"):
    return normalize_result(value, operation=operation, domain=domain, context_hash=CONTEXT_HASH)


@pytest.mark.parametrize("status", ["ok", "empty", "needs_input", "partial", "degraded", "error"])
def test_six_wire_statuses_remain_distinct(status):
    result = normalize(envelope(status))
    assert result.status == status
    assert not isinstance(result, dict)
    assert not any(isinstance(row, dict) for row in result.candidates)
    if status in {"empty", "needs_input", "error"}:
        assert result.candidates == ()
    if status == "error":
        assert result.error.code == "SYNTHETIC_UNAVAILABLE"


def test_ambiguity_preserves_typed_choices_and_never_selects_a_seed():
    result = normalize(envelope("needs_input", operation="describe"), operation="describe")
    assert result.entities == result.candidates == ()
    assert len(result.issues) == 1
    assert result.issues[0].kind == "ambiguous"
    assert [(str(row.id), row.domain) for row in result.issues[0].choices] == [
        (FIRST_ID, "movie"),
        (SECOND_ID, "movie"),
    ]


def test_compact_description_can_use_matching_resolved_identity_not_guess_domain():
    value = envelope(operation="describe", results=[{"entity_id": FIRST_ID, "name": "Invented Film A"}])
    value["interpretation"] = {"entity": {"entityId": FIRST_ID, "type": "urn:entity:movie"}}
    result = normalize(value, operation="describe")
    assert result.entities[0].id == UUID(FIRST_ID)
    assert result.entities[0].domain == "movie"
    value["interpretation"]["entity"]["entityId"] = SECOND_ID
    assert normalize(value, operation="describe").entities == ()


def test_generic_compact_type_cannot_infer_domain_from_typed_search_context():
    # Mirrors pinned harness source, not a captured response: compactEntity drops
    # `types`; entityType returns direct generic `type` before inspecting `types`.
    value = envelope(
        operation="describe",
        results=[{"entity_id": FIRST_ID, "name": "Synthetic typed movie", "type": "urn:entity"}],
    )
    value["interpretation"] = {
        "entity": {
            "input": "Synthetic typed movie",
            "entityId": FIRST_ID,
            "name": "Synthetic typed movie",
            "type": "urn:entity",
            "match": "exact",
        }
    }
    value["resolution"] = {
        "outcomes": [
            {
                "input": "Synthetic typed movie",
                "status": "resolved",
                "match": "exact",
                "selected": {"id": FIRST_ID, "name": "Synthetic typed movie", "type": "urn:entity"},
                "provenance": {
                    "provider_id": "qloo_api",
                    "endpoint": "/search",
                    "strategy": "exact_name_context_or_choice",
                },
            }
        ]
    }
    result = normalize(value, operation="describe")
    assert result.status == "degraded"
    assert result.entities == ()
    # Only actual returned type evidence, preserved before compaction, can fix this.
    value["results"][0]["subtype"] = "urn:entity:movie"
    result = normalize(value, operation="describe")
    assert result.status == "ok"
    assert result.entities[0].id == UUID(FIRST_ID)
    assert result.entities[0].domain == "movie"


def test_order_ties_and_raw_units_survive_without_artificial_tiebreaking_or_scale_conversion():
    value = envelope(results=[entity(score=81), entity(SECOND_ID, score=81)])
    result = normalize(value)
    assert [row.affinity for row in result.candidates] == [81, 81]
    assert [row.entity.id for row in result.candidates] == [UUID(FIRST_ID), UUID(SECOND_ID)]
    assert len({row.position for row in result.candidates}) == 2
    assert result.evidence.context_hash == CONTEXT_HASH
    assert result.evidence.score_field == "harness.compact.affinity"
    assert result.evidence.ordering_verified is False


@pytest.mark.parametrize("score", [None, True, False, "0.8", float("nan"), float("inf"), -float("inf")])
def test_invalid_scores_cannot_enter_candidate_values(score):
    result = normalize(envelope(results=[entity(score=score)]))
    assert result.candidates == ()
    assert result.status != "ok"


def test_contradictory_type_does_not_get_relabelled_to_requested_target():
    result = normalize(envelope(results=[entity(domain="artist")]))
    assert result.candidates == ()
    assert result.status != "ok"


def test_missing_explanation_stays_absent_and_image_metadata_is_not_a_licence():
    row = entity()
    row["properties"] = {"image": {"url": "https://example.invalid/synthetic.jpg"}}
    result = normalize(envelope(results=[row]))
    assert result.candidates[0].explanation is None
    assert result.candidates[0].entity.image_url == "https://example.invalid/synthetic.jpg"
    assert result.candidates[0].entity.image_rights_verified is False


@pytest.mark.parametrize(
    "image", ["javascript:alert(1)", "http://127.0.0.1/private", "https://u:p@example.invalid/x"]
)
def test_unsafe_image_metadata_is_not_forwarded(image):
    row = entity()
    row["properties"] = {"image": {"url": image}}
    result = normalize(envelope(results=[row]))
    assert result.candidates[0].entity.image_url is None


def test_arbitrary_payloads_explanations_and_provenance_do_not_escape_normalizer():
    value = envelope(results=[entity()])
    value["secret_payload"] = "SYNTHETIC_PRIVATE_SENTINEL"
    value["summary"] = "SYNTHETIC_PRIVATE_SENTINEL"
    value["results"][0]["explainability"] = {
        "psychological_story": "SYNTHETIC_PRIVATE_SENTINEL",
        "chain_of_thought": "SYNTHETIC_PRIVATE_SENTINEL",
    }
    value["provenance"]["requests"] = [
        {"method": "GET", "path": "/v2/insights", "query": {"api_key": "SYNTHETIC_PRIVATE_SENTINEL"}}
    ]
    serialized = json.dumps(asdict(normalize(value)), default=str)
    assert "SYNTHETIC_PRIVATE_SENTINEL" not in serialized
    assert "psychological_story" not in serialized
    assert "chain_of_thought" not in serialized


@pytest.mark.parametrize("change", ["version", "operation", "status", "rows", "count"])
def test_invalid_envelope_is_an_explicit_failure(change):
    value = envelope()
    if change == "version":
        value["schema_version"] = "unexpected-version"
    elif change == "operation":
        value["operation"] = "rank"
    elif change == "status":
        value["status"] = "magically_successful"
    elif change == "rows":
        value["results"] = {"secret": "not-a-row-list"}
    else:
        value["result_count"] = 900
    result = normalize(value)
    assert result.status == "error"
    assert result.error is not None
    assert not result.candidates and not result.entities


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", []),
        ("status", {}),
        ("schema_version", {}),
        ("operation", []),
        ("results", None),
        ("results", "not rows"),
    ],
)
def test_malformed_json_values_return_safe_errors_instead_of_raising(field, value):
    payload = envelope()
    payload[field] = value
    result = normalize(payload)
    assert result.status == "error"
    assert result.error.code == "PROVIDER_CONTRACT_INVALID"


def test_nested_schema_warnings_are_visible_as_safe_codes_not_explanatory_claims():
    value = envelope(results=[entity()])
    value["warnings"] = ["Synthetic schema warning; unknown parameter ignored"]
    value["results"][0]["explainability"] = {"warnings": ["Synthetic limited signal influence"]}
    result = normalize(value)
    assert "PROVIDER_WARNINGS_PRESENT" in result.warnings
    assert "UNREVIEWED_EXPLANATION_PRESENT" in result.warnings
    assert result.candidates[0].explanation is None
    assert "unknown parameter ignored" not in json.dumps(asdict(result), default=str)


def test_rejected_candidate_never_shifts_the_surviving_upstream_position():
    value = envelope(results=[entity(score=None), entity(SECOND_ID, score=0.3)])
    result = normalize(value)
    assert result.status == "partial"
    assert len(result.candidates) == 1
    assert result.candidates[0].position == 1
    assert "CANDIDATES_REJECTED" in result.warnings

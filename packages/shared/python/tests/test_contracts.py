"""Validate the Pydantic contracts against the cross-language fixture suite."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from iopsych_contracts import (
    ALIGNMENT_CLASSIFICATIONS,
    CONFIDENCE_LEVELS,
    CONSTRUCT_DEFINITIONS,
    CONSTRUCT_DEFINITIONS_BY_KEY,
    CONSTRUCT_KEYS,
    AlignmentClassification,
    ApiProblem,
    ComparisonTarget,
    ConfidenceLevel,
    ConstructKey,
    RawScoreThreshold,
    RoleExtraction,
    ScoringConfig,
    parse_role_extraction,
)

FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "v1"
DEFINITION_ROOT = Path(__file__).parents[2] / "definitions" / "v1"


def load_fixture(relative_path: str) -> dict[str, Any]:
    """Load one synthetic fixture case from the language-neutral fixture tree."""

    return cast(
        dict[str, Any],
        json.loads((FIXTURE_ROOT / relative_path).read_text(encoding="utf-8")),
    )


def fixture_is_valid(fixture: dict[str, Any]) -> bool:
    """Apply the validator selected by a fixture's contract discriminator."""

    try:
        match fixture["contract"]:
            case "api_problem":
                ApiProblem.model_validate(fixture["payload"])
            case "scoring_config":
                ScoringConfig.model_validate(fixture["payload"])
            case "role_extraction":
                parse_role_extraction(
                    fixture["payload"], fixture.get("context", {}).get("job_description", "")
                )
            case contract:
                raise AssertionError(f"Unknown fixture contract: {contract}")
    except (ValidationError, ValueError):
        return False
    return True


def test_construct_definitions_are_complete_and_behavioral() -> None:
    """The API imports the same six keys and explicit structure exception as TypeScript."""

    assert [key.value for key in CONSTRUCT_KEYS] == [
        "autonomy",
        "structure",
        "ambiguity",
        "collaboration",
        "mastery",
        "pace",
    ]
    assert len(CONSTRUCT_DEFINITIONS) == 6
    assert (
        CONSTRUCT_DEFINITIONS_BY_KEY[ConstructKey.STRUCTURE].comparison_target
        is ComparisonTarget.INVERSE_ROLE_RATING
    )
    assert all(
        definition.comparison_target is ComparisonTarget.ROLE_RATING
        for definition in CONSTRUCT_DEFINITIONS
        if definition.key is not ConstructKey.STRUCTURE
    )
    assert tuple(ConfidenceLevel) == CONFIDENCE_LEVELS
    assert tuple(AlignmentClassification) == ALIGNMENT_CLASSIFICATIONS


def test_construct_definitions_match_language_neutral_document() -> None:
    """Pydantic metadata cannot drift from the document consumed by other runtimes."""

    document = json.loads((DEFINITION_ROOT / "constructs.json").read_text(encoding="utf-8"))
    assert document["contract_version"] == "1.0.0"
    assert document["constructs"] == [
        definition.model_dump(mode="json") for definition in CONSTRUCT_DEFINITIONS
    ]


@pytest.mark.parametrize(
    "relative_path",
    [
        "api-problem/valid.json",
        "api-problem/invalid-status.json",
        "role-extraction/valid.json",
        "role-extraction/invalid-evidence.json",
        "role-extraction/invalid-missing-construct.json",
        "scoring-config/valid.json",
        "scoring-config/invalid-gap.json",
    ],
)
def test_shared_fixture_case(relative_path: str) -> None:
    """Pydantic and Zod consume the same expected-validity fixture cases."""

    fixture = load_fixture(relative_path)
    assert fixture_is_valid(fixture) is fixture["expected_valid"]


def test_role_extraction_rejects_duplicate_construct_and_review_bypass() -> None:
    """Six entries are insufficient unless every construct is present exactly once."""

    fixture = load_fixture("role-extraction/valid.json")
    payload = deepcopy(fixture["payload"])
    payload["constructs"][-1] = deepcopy(payload["constructs"][0])

    with pytest.raises(ValidationError, match="each version 1 construct exactly once"):
        RoleExtraction.model_validate(payload)

    payload = deepcopy(fixture["payload"])
    payload["needs_human_review"] = False
    with pytest.raises(ValidationError, match="Input should be True"):
        RoleExtraction.model_validate(payload)


def test_role_extraction_requires_non_empty_source_context() -> None:
    """Evidence validation cannot run without the submitted job description."""

    fixture = load_fixture("role-extraction/valid.json")
    with pytest.raises(ValueError, match="non-empty job description"):
        parse_role_extraction(fixture["payload"], "   ")


def test_strict_models_reject_out_of_range_rating_and_extra_fields() -> None:
    """Serialized contracts reject coercion, invalid ratings, and unknown members."""

    fixture = load_fixture("role-extraction/valid.json")
    payload = deepcopy(fixture["payload"])
    payload["constructs"][0]["rating"] = 6
    payload["approved"] = True

    with pytest.raises(ValidationError):
        RoleExtraction.model_validate(payload)


def test_problem_field_locations_are_json_pointers() -> None:
    """Field errors cannot use ambiguous dotted or bare member paths."""

    with pytest.raises(ValidationError):
        ApiProblem.model_validate(
            {
                "title": "Invalid request",
                "status": 422,
                "code": "invalid_request",
                "errors": [
                    {"pointer": "title", "code": "required", "message": "Title is required."}
                ],
            }
        )


def test_score_thresholds_reject_reversed_bounds_and_duplicate_ratings() -> None:
    """Thresholds must be individually valid and collectively total and contiguous."""

    with pytest.raises(ValidationError, match="must not exceed"):
        RawScoreThreshold(rating=1, minimum_raw_score=2, maximum_raw_score=1)

    fixture = load_fixture("scoring-config/valid.json")
    payload = deepcopy(fixture["payload"])
    payload["rating_thresholds"][4]["rating"] = 4
    with pytest.raises(ValidationError, match="ratings 1 through 5 exactly once"):
        ScoringConfig.model_validate(payload)


def test_contracts_publish_json_schema() -> None:
    """Pydantic models remain available to API documentation and tooling."""

    assert RoleExtraction.model_json_schema()["type"] == "object"
    assert ScoringConfig.model_json_schema()["type"] == "object"
    assert ApiProblem.model_json_schema()["type"] == "object"

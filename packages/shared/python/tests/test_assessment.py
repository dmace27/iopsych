"""Exercise versioned assessment validation and deterministic scoring."""

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from iopsych_contracts import (
    CONSTRUCT_KEYS,
    AnsweredBlockResponse,
    AssessmentBlock,
    AssessmentDefinition,
    AssessmentResponseSet,
    AssessmentScoreResult,
    AssessmentScoringError,
    AssessmentScoringErrorCode,
    CandidateConstructScore,
    ConstructKey,
    SkippedBlockResponse,
    score_assessment,
)
from iopsych_contracts.assessment import _confidence_for_skips, _rating_for_raw_score

DEFINITION_PATH = Path(__file__).parents[2] / "definitions" / "v1" / "pilot-assessment.json"


def load_definition_payload() -> dict[str, Any]:
    """Load the language-neutral synthetic pilot definition."""

    return cast(dict[str, Any], json.loads(DEFINITION_PATH.read_text(encoding="utf-8")))


def load_definition() -> AssessmentDefinition:
    """Parse a fresh immutable definition for each test."""

    return AssessmentDefinition.model_validate(load_definition_payload())


def answered_response(
    block: AssessmentBlock,
    most_like_index: int = 0,
    least_like_index: int = 1,
) -> AnsweredBlockResponse:
    """Build one valid response from stable ids in a definition block."""

    return AnsweredBlockResponse(
        block_id=block.id,
        skipped=False,
        most_like_item_id=block.items[most_like_index].id,
        least_like_item_id=block.items[least_like_index].id,
    )


def complete_response_set(
    definition: AssessmentDefinition,
) -> AssessmentResponseSet:
    """Build one deterministic complete response set."""

    return AssessmentResponseSet(
        assessment_definition_id=definition.id,
        assessment_definition_version=definition.version,
        responses=tuple(answered_response(block) for block in definition.blocks),
    )


def responses_for_raw_score(
    definition: AssessmentDefinition,
    construct_key: ConstructKey,
    desired_raw_score: int,
) -> AssessmentResponseSet:
    """Select the target construct enough times to exercise one raw score."""

    target_selections_remaining = abs(desired_raw_score)
    responses: list[AnsweredBlockResponse] = []
    for block in definition.blocks:
        target_index = next(
            (
                index
                for index, item in enumerate(block.items)
                if item.construct_key is construct_key
            ),
            -1,
        )
        other_indexes = [index for index in range(len(block.items)) if index != target_index]
        if target_index == -1 or target_selections_remaining == 0:
            responses.append(answered_response(block, other_indexes[0], other_indexes[1]))
            continue

        target_selections_remaining -= 1
        if desired_raw_score > 0:
            responses.append(answered_response(block, target_index, other_indexes[0]))
        else:
            responses.append(answered_response(block, other_indexes[0], target_index))

    return AssessmentResponseSet(
        assessment_definition_id=definition.id,
        assessment_definition_version=definition.version,
        responses=tuple(responses),
    )


def score_for(
    definition: AssessmentDefinition,
    construct_key: ConstructKey,
    response_set: AssessmentResponseSet,
) -> CandidateConstructScore:
    """Return one construct result from a complete score result."""

    return next(
        score
        for score in score_assessment(definition, response_set).construct_scores
        if score.construct_key is construct_key
    )


def test_definition_is_balanced_and_explicitly_draft() -> None:
    """The synthetic content is useful for integration without claiming I-O review."""

    definition = load_definition()
    exposure = {
        key: sum(item.construct_key is key for block in definition.blocks for item in block.items)
        for key in CONSTRUCT_KEYS
    }

    assert definition.status.value == "draft"
    assert len(definition.blocks) == 6
    assert all(len(block.items) == 4 for block in definition.blocks)
    assert exposure == dict.fromkeys(CONSTRUCT_KEYS, 4)


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda payload: payload["blocks"][1].update(id=payload["blocks"][0]["id"]), "block ids"),
        (
            lambda payload: payload["blocks"][1].update(position=payload["blocks"][0]["position"]),
            "block positions",
        ),
        (
            lambda payload: payload["blocks"][1]["items"][0].update(
                id=payload["blocks"][0]["items"][0]["id"]
            ),
            "item ids",
        ),
        (
            lambda payload: payload["blocks"][0]["items"][1].update(
                construct_key=payload["blocks"][0]["items"][0]["construct_key"]
            ),
            "at most once",
        ),
        (
            lambda payload: payload["blocks"][0]["items"][1].update(construct_key="pace"),
            "must appear exactly",
        ),
        (
            lambda payload: payload["scoring"]["rating_thresholds"][0].update(minimum_raw_score=-5),
            "reachable raw-score range",
        ),
    ],
)
def test_definition_rejects_unbalanced_or_duplicate_content(
    mutation: Callable[[dict[str, Any]], object], message: str
) -> None:
    """Definition invariants fail before candidate responses can reference bad content."""

    payload = load_definition_payload()
    mutation(payload)
    with pytest.raises(ValidationError, match=message):
        AssessmentDefinition.model_validate(payload)


def test_response_snapshot_allows_save_resume_and_distinguishes_skips() -> None:
    """Omitted blocks remain different from an explicit prefer-not-to-answer choice."""

    definition = load_definition()
    partial = AssessmentResponseSet(
        assessment_definition_id=definition.id,
        assessment_definition_version=definition.version,
        responses=(answered_response(definition.blocks[0]),),
    )
    skipped = SkippedBlockResponse(
        block_id=definition.blocks[1].id,
        skipped=True,
        most_like_item_id=None,
        least_like_item_id=None,
    )

    assert len(partial.responses) == 1
    assert skipped.skipped is True
    with pytest.raises(ValidationError):
        SkippedBlockResponse.model_validate(
            {
                **skipped.model_dump(),
                "most_like_item_id": definition.blocks[1].items[0].id,
            }
        )


def test_response_snapshot_rejects_duplicate_blocks_and_same_selection() -> None:
    """Ambiguous block state and impossible forced choices never persist."""

    definition = load_definition()
    response = answered_response(definition.blocks[0])
    with pytest.raises(ValidationError, match="at most one response"):
        AssessmentResponseSet(
            assessment_definition_id=definition.id,
            assessment_definition_version=definition.version,
            responses=(response, response),
        )
    with pytest.raises(ValidationError, match="must be different"):
        AnsweredBlockResponse(
            block_id=response.block_id,
            skipped=False,
            most_like_item_id=response.most_like_item_id,
            least_like_item_id=response.most_like_item_id,
        )


@pytest.mark.parametrize(
    "raw_score, expected_rating",
    [(-4, 1), (-3, 1), (-2, 2), (-1, 2), (0, 3), (1, 4), (2, 4), (3, 5), (4, 5)],
)
def test_every_raw_score_threshold(raw_score: int, expected_rating: int) -> None:
    """Every inclusive boundary maps to the configured 1-5 rating."""

    definition = load_definition()
    response_set = responses_for_raw_score(definition, ConstructKey.AUTONOMY, raw_score)
    score = score_for(definition, ConstructKey.AUTONOMY, response_set)

    assert score.raw_score == raw_score
    assert score.rating == expected_rating
    assert score.confidence.value == "high"
    assert (score.assigned_item_count, score.answered_item_count, score.skipped_item_count) == (
        4,
        4,
        0,
    )


def test_extreme_scores_apply_to_every_construct() -> None:
    """No construct receives bespoke or directional scoring."""

    definition = load_definition()
    for construct_key in CONSTRUCT_KEYS:
        high_score = score_for(
            definition,
            construct_key,
            responses_for_raw_score(definition, construct_key, 4),
        )
        low_score = score_for(
            definition,
            construct_key,
            responses_for_raw_score(definition, construct_key, -4),
        )
        assert (high_score.raw_score, high_score.rating) == (4, 5)
        assert (low_score.raw_score, low_score.rating) == (-4, 1)


def test_skips_set_confidence_per_construct() -> None:
    """Only skipped statements assigned to a construct lower its confidence."""

    definition = load_definition()
    response_set = complete_response_set(definition)
    skipped_blocks = {"block-1", "block-2"}
    responses = tuple(
        SkippedBlockResponse(
            block_id=response.block_id,
            skipped=True,
            most_like_item_id=None,
            least_like_item_id=None,
        )
        if response.block_id in skipped_blocks
        else response
        for response in response_set.responses
    )
    result = score_assessment(
        definition,
        AssessmentResponseSet(
            assessment_definition_id=definition.id,
            assessment_definition_version=definition.version,
            responses=responses,
        ),
    )
    scores = {score.construct_key: score for score in result.construct_scores}

    assert scores[ConstructKey.AUTONOMY].confidence.value == "low"
    assert scores[ConstructKey.AUTONOMY].skipped_item_count == 2
    assert scores[ConstructKey.STRUCTURE].confidence.value == "medium"
    assert scores[ConstructKey.STRUCTURE].skipped_item_count == 1


def test_fully_skipped_assessment_is_neutral_and_low_confidence() -> None:
    """Skipping does not fabricate preference evidence."""

    definition = load_definition()
    response_set = AssessmentResponseSet(
        assessment_definition_id=definition.id,
        assessment_definition_version=definition.version,
        responses=tuple(
            SkippedBlockResponse(
                block_id=block.id,
                skipped=True,
                most_like_item_id=None,
                least_like_item_id=None,
            )
            for block in definition.blocks
        ),
    )

    for score in score_assessment(definition, response_set).construct_scores:
        assert (score.raw_score, score.rating, score.confidence.value) == (0, 3, "low")
        assert (score.answered_item_count, score.skipped_item_count) == (0, 4)


@pytest.mark.parametrize(
    "mutation, message",
    [
        (
            lambda payload: payload["construct_scores"][5].update(construct_key="autonomy"),
            "every construct",
        ),
        (
            lambda payload: payload["construct_scores"][0].update(assigned_item_count=3),
            "answered plus skipped",
        ),
        (
            lambda payload: payload["construct_scores"][0].update(
                assigned_item_count=5, answered_item_count=5
            ),
            "account for 4",
        ),
        (
            lambda payload: payload["construct_scores"][0].update(raw_score=5),
            "cannot exceed",
        ),
    ],
)
def test_score_snapshot_rejects_impossible_persisted_results(
    mutation: Callable[[dict[str, Any]], object], message: str
) -> None:
    """Persisted score contracts reject duplicates and inconsistent trace counts."""

    definition = load_definition()
    payload = score_assessment(definition, complete_response_set(definition)).model_dump(
        mode="json"
    )
    mutation(payload)

    with pytest.raises(ValidationError, match=message):
        AssessmentScoreResult.model_validate(payload)


def test_result_preserves_definition_and_scoring_versions() -> None:
    """Persisted scores carry enough policy identity for historical interpretation."""

    payload = load_definition_payload()
    payload["version"] = "1.1.0"
    payload["scoring"]["version"] = "2.0.0"
    definition = AssessmentDefinition.model_validate(payload)
    result = score_assessment(definition, complete_response_set(definition))

    assert result.assessment_definition_id == "work-preferences-pilot"
    assert result.assessment_definition_version == "1.1.0"
    assert result.scoring_version == "2.0.0"


@pytest.mark.parametrize(
    "mutation, expected_code",
    [
        (
            lambda payload: payload["responses"].pop(),
            AssessmentScoringErrorCode.INCOMPLETE_ASSESSMENT,
        ),
        (
            lambda payload: payload["responses"][0].update(block_id="unknown-block"),
            AssessmentScoringErrorCode.UNKNOWN_BLOCK,
        ),
        (
            lambda payload: payload["responses"][0].update(most_like_item_id="b2-ambiguity"),
            AssessmentScoringErrorCode.INVALID_ITEM_SELECTION,
        ),
    ],
)
def test_scoring_rejects_invalid_response_combinations(
    mutation: Callable[[dict[str, Any]], object],
    expected_code: AssessmentScoringErrorCode,
) -> None:
    """Cross-document constraints return stable domain error codes."""

    definition = load_definition()
    payload = complete_response_set(definition).model_dump(mode="json")
    mutation(payload)
    response_set = AssessmentResponseSet.model_validate(payload)

    with pytest.raises(AssessmentScoringError) as error:
        score_assessment(definition, response_set)
    assert error.value.code is expected_code


def test_scoring_rejects_definition_version_mismatch() -> None:
    """A response is never silently reinterpreted under newer content."""

    definition = load_definition()
    payload = complete_response_set(definition).model_dump(mode="json")
    payload["assessment_definition_version"] = "2.0.0"

    with pytest.raises(AssessmentScoringError) as error:
        score_assessment(definition, AssessmentResponseSet.model_validate(payload))
    assert error.value.code is AssessmentScoringErrorCode.DEFINITION_MISMATCH


def test_scoring_does_not_mutate_inputs() -> None:
    """Pure scoring leaves serialized definition and response snapshots unchanged."""

    definition = load_definition()
    response_set = complete_response_set(definition)
    before_definition = deepcopy(definition.model_dump(mode="json"))
    before_responses = deepcopy(response_set.model_dump(mode="json"))

    score_assessment(definition, response_set)

    assert definition.model_dump(mode="json") == before_definition
    assert response_set.model_dump(mode="json") == before_responses


def test_internal_policy_lookups_fail_closed_for_unmapped_values() -> None:
    """Defensive lookup guards fail loudly if validated policy is bypassed."""

    config = load_definition().scoring
    with pytest.raises(AssessmentScoringError) as score_error:
        _rating_for_raw_score(99, config)
    assert score_error.value.code is AssessmentScoringErrorCode.UNMAPPED_RAW_SCORE

    with pytest.raises(AssessmentScoringError) as confidence_error:
        _confidence_for_skips(-1, config)
    assert confidence_error.value.code is AssessmentScoringErrorCode.UNMAPPED_CONFIDENCE

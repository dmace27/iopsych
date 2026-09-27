"""Boundary and invariant tests for the pure matching engine."""

import json
from copy import deepcopy
from itertools import product
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import iopsych_contracts.matching as matching_module
from iopsych_contracts import (
    APPROVED_INTERVIEW_QUESTION_LIBRARY_V1,
    CONSTRUCT_KEYS,
    AlignmentClassification,
    AssessmentScoreResult,
    CandidateConstructScore,
    CandidateResponseSummary,
    ComparisonTarget,
    ConfidenceLevel,
    ConstructKey,
    MatchingError,
    MatchingErrorCode,
    MatchingResult,
    MatchingRoleProfile,
    MatchingRule,
    RoleConstructRating,
    RoleEvidenceSummary,
    comparison_rating,
    lower_confidence,
    match_construct,
    match_role_profile,
)

QUESTION_LIBRARY_PATH = (
    Path(__file__).parents[2] / "definitions" / "v1" / "interview-questions.json"
)


def role_rating(
    key: ConstructKey,
    rating: int = 3,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> RoleConstructRating:
    """Build synthetic, behaviorally grounded role evidence."""

    return RoleConstructRating(
        key=key,
        rating=rating,
        confidence=confidence,
        rationale=f"Synthetic rationale for {key.value}.",
        evidence=[f"Synthetic role evidence for {key.value}."],
    )


def candidate_score(
    key: ConstructKey,
    rating: int = 3,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> CandidateConstructScore:
    """Build a coherent trace summary at the requested confidence level."""

    skipped = {
        ConfidenceLevel.HIGH: 0,
        ConfidenceLevel.MEDIUM: 1,
        ConfidenceLevel.LOW: 2,
    }[confidence]
    return CandidateConstructScore(
        construct_key=key,
        raw_score=0,
        rating=rating,
        confidence=confidence,
        assigned_item_count=4,
        answered_item_count=4 - skipped,
        skipped_item_count=skipped,
    )


def role_profile(*, approved: bool = True) -> MatchingRoleProfile:
    """Build a complete matching input in deliberately reversed order."""

    return MatchingRoleProfile(
        approved=approved,
        constructs=tuple(role_rating(key) for key in reversed(CONSTRUCT_KEYS)),
    )


def score_result() -> AssessmentScoreResult:
    """Build a complete, versioned candidate score snapshot."""

    return AssessmentScoreResult(
        assessment_definition_id="synthetic-assessment",
        assessment_definition_version="2.1.0",
        scoring_version="3.0.0",
        construct_scores=tuple(candidate_score(key) for key in reversed(CONSTRUCT_KEYS)),
    )


@pytest.mark.parametrize(
    "role_value,candidate_value,expected_classification,expected_rule",
    [
        (1, 1, AlignmentClassification.ALIGNED, MatchingRule.DIFFERENCE_AT_MOST_ONE),
        (1, 2, AlignmentClassification.ALIGNED, MatchingRule.DIFFERENCE_AT_MOST_ONE),
        (1, 3, AlignmentClassification.WORTH_DISCUSSING, MatchingRule.DIFFERENCE_EQUALS_TWO),
        (1, 4, AlignmentClassification.POTENTIAL_FRICTION, MatchingRule.DIFFERENCE_AT_LEAST_THREE),
        (1, 5, AlignmentClassification.POTENTIAL_FRICTION, MatchingRule.DIFFERENCE_AT_LEAST_THREE),
        (5, 4, AlignmentClassification.ALIGNED, MatchingRule.DIFFERENCE_AT_MOST_ONE),
        (5, 3, AlignmentClassification.WORTH_DISCUSSING, MatchingRule.DIFFERENCE_EQUALS_TWO),
        (5, 2, AlignmentClassification.POTENTIAL_FRICTION, MatchingRule.DIFFERENCE_AT_LEAST_THREE),
        (5, 1, AlignmentClassification.POTENTIAL_FRICTION, MatchingRule.DIFFERENCE_AT_LEAST_THREE),
    ],
)
def test_every_distance_boundary_in_both_directions(
    role_value: int,
    candidate_value: int,
    expected_classification: AlignmentClassification,
    expected_rule: MatchingRule,
) -> None:
    """Distances 0/1, 2, and 3/4 map to the three interpretable labels."""

    result = match_construct(
        role_rating(ConstructKey.AUTONOMY, role_value),
        candidate_score(ConstructKey.AUTONOMY, candidate_value),
        role_profile_approved=True,
    )

    assert result.classification is expected_classification
    assert result.explanation.applied_rule.rule is expected_rule
    assert result.explanation.applied_rule.absolute_difference == abs(role_value - candidate_value)
    assert result.explanation.uncertainty is None


@pytest.mark.parametrize("key", CONSTRUCT_KEYS)
def test_boundaries_apply_to_every_construct(key: ConstructKey) -> None:
    """Every construct uses the same distance boundaries after target derivation."""

    # A role value of 3 is unchanged by structure inversion, isolating the
    # common classification rule for this all-construct assertion.
    expected = {
        3: AlignmentClassification.ALIGNED,
        4: AlignmentClassification.ALIGNED,
        5: AlignmentClassification.WORTH_DISCUSSING,
    }
    for candidate_value, classification in expected.items():
        result = match_construct(
            role_rating(key, 3),
            candidate_score(key, candidate_value),
            role_profile_approved=True,
        )
        assert result.classification is classification


@pytest.mark.parametrize("role_value", range(1, 6))
def test_structure_uses_the_explicit_inverse_target(role_value: int) -> None:
    """Structure exposes and compares against 6 - R exactly as specified."""

    target = 6 - role_value
    aligned = match_construct(
        role_rating(ConstructKey.STRUCTURE, role_value),
        candidate_score(ConstructKey.STRUCTURE, target),
        role_profile_approved=True,
    )

    assert comparison_rating(ConstructKey.STRUCTURE, role_value) == target
    assert aligned.classification is AlignmentClassification.ALIGNED
    assert aligned.explanation.role.comparison_target is ComparisonTarget.INVERSE_ROLE_RATING
    assert aligned.explanation.role.comparison_rating == target
    assert aligned.explanation.applied_rule.absolute_difference == 0


@pytest.mark.parametrize(
    "key", [key for key in CONSTRUCT_KEYS if key is not ConstructKey.STRUCTURE]
)
def test_non_structure_targets_use_role_rating(key: ConstructKey) -> None:
    """No other construct accidentally inherits structure's exceptional rule."""

    assert [comparison_rating(key, value) for value in range(1, 6)] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize(
    "role_confidence,candidate_confidence",
    list(product(ConfidenceLevel, repeat=2)),
)
def test_report_confidence_is_the_lower_input_and_low_fails_closed(
    role_confidence: ConfidenceLevel,
    candidate_confidence: ConfidenceLevel,
) -> None:
    """The full confidence matrix is ordered low, medium, high."""

    expected = min(
        (role_confidence, candidate_confidence),
        key={
            ConfidenceLevel.LOW: 0,
            ConfidenceLevel.MEDIUM: 1,
            ConfidenceLevel.HIGH: 2,
        }.__getitem__,
    )
    result = match_construct(
        role_rating(ConstructKey.PACE, 1, role_confidence),
        candidate_score(ConstructKey.PACE, 5, candidate_confidence),
        role_profile_approved=True,
    )

    assert lower_confidence(role_confidence, candidate_confidence) is expected
    assert result.confidence is expected
    if expected is ConfidenceLevel.LOW:
        assert result.classification is AlignmentClassification.INSUFFICIENT_EVIDENCE
        assert result.explanation.applied_rule.rule is MatchingRule.LOW_CONFIDENCE
        assert result.explanation.uncertainty is not None
    else:
        assert result.classification is AlignmentClassification.POTENTIAL_FRICTION


def test_unapproved_profile_always_returns_insufficient_evidence() -> None:
    """Approval gates interpretation even when both evidence sources are high confidence."""

    result = match_role_profile(role_profile(approved=False), score_result())

    assert result.role_profile_approved is False
    assert all(
        item.classification is AlignmentClassification.INSUFFICIENT_EVIDENCE
        for item in result.items
    )
    assert all(
        item.explanation.applied_rule.rule is MatchingRule.ROLE_PROFILE_NOT_APPROVED
        for item in result.items
    )
    assert all(item.explanation.uncertainty is not None for item in result.items)


def test_result_is_traceable_complete_and_canonically_ordered() -> None:
    """Output retains versions, source evidence, raw response counts, and stable ordering."""

    result = match_role_profile(role_profile(), score_result())

    assert result.algorithm_version == "1.0.0"
    assert result.assessment_definition_id == "synthetic-assessment"
    assert result.assessment_definition_version == "2.1.0"
    assert result.scoring_version == "3.0.0"
    assert [item.construct_key for item in result.items] == list(CONSTRUCT_KEYS)
    autonomy = result.items[0]
    assert autonomy.explanation.role.evidence == ("Synthetic role evidence for autonomy.",)
    assert autonomy.explanation.role.rationale == "Synthetic rationale for autonomy."
    assert autonomy.explanation.candidate_response.model_dump() == {
        "rating": 3,
        "confidence": ConfidenceLevel.HIGH,
        "raw_score": 0,
        "assigned_item_count": 4,
        "answered_item_count": 4,
        "skipped_item_count": 0,
    }


def test_question_library_is_total_approved_and_has_unique_stable_ids() -> None:
    """All 24 construct/classification combinations select two reviewed questions."""

    expected_keys = set(product(CONSTRUCT_KEYS, AlignmentClassification))
    observed_keys = {
        (entry.construct_key, entry.classification)
        for entry in APPROVED_INTERVIEW_QUESTION_LIBRARY_V1
    }
    ids = [
        question.id
        for entry in APPROVED_INTERVIEW_QUESTION_LIBRARY_V1
        for question in (entry.questions.primary, entry.questions.follow_up)
    ]

    assert observed_keys == expected_keys
    assert all(
        entry.review_status == "approved" for entry in APPROVED_INTERVIEW_QUESTION_LIBRARY_V1
    )
    assert len(ids) == len(set(ids)) == 48

    ambiguity = match_construct(
        role_rating(ConstructKey.AMBIGUITY, 1),
        candidate_score(ConstructKey.AMBIGUITY, 5),
        role_profile_approved=True,
    )
    assert ambiguity.interview_questions.primary.text == (
        "Tell me about a time requirements were incomplete or changed quickly. "
        "How did you decide what to do next?"
    )
    assert ambiguity.interview_questions.follow_up.text == (
        "What support, information, or routines helped you work effectively?"
    )


def test_question_library_matches_language_neutral_document() -> None:
    """Python and TypeScript expose the same reviewed interview content."""

    document = json.loads(QUESTION_LIBRARY_PATH.read_text(encoding="utf-8"))
    assert document == [
        entry.model_dump(mode="json") for entry in APPROVED_INTERVIEW_QUESTION_LIBRARY_V1
    ]


def test_matching_is_deterministic_and_does_not_mutate_inputs() -> None:
    """Repeated calls have identical output and preserve serialized snapshots."""

    profile = role_profile()
    scores = score_result()
    before_profile = deepcopy(profile.model_dump(mode="json"))
    before_scores = deepcopy(scores.model_dump(mode="json"))

    first = match_role_profile(profile, scores)
    second = match_role_profile(profile, scores)

    assert first == second
    assert profile.model_dump(mode="json") == before_profile
    assert scores.model_dump(mode="json") == before_scores
    serialized = first.model_dump(mode="json")
    assert "hire_score" not in str(serialized)
    assert "recommendation" not in serialized


def test_mismatched_constructs_raise_a_stable_domain_error() -> None:
    """A caller cannot silently compare evidence from different constructs."""

    with pytest.raises(MatchingError) as error:
        match_construct(
            role_rating(ConstructKey.AUTONOMY),
            candidate_score(ConstructKey.PACE),
            role_profile_approved=True,
        )
    assert error.value.code is MatchingErrorCode.CONSTRUCT_MISMATCH


def test_role_and_result_snapshots_reject_duplicate_constructs() -> None:
    """Complete length alone cannot hide a missing construct behind a duplicate."""

    constructs = [role_rating(key) for key in CONSTRUCT_KEYS]
    constructs[-1] = role_rating(ConstructKey.AUTONOMY)
    with pytest.raises(ValidationError, match="each version 1 construct"):
        MatchingRoleProfile(approved=True, constructs=tuple(constructs))

    result_payload: dict[str, Any] = match_role_profile(role_profile(), score_result()).model_dump(
        mode="json"
    )
    result_payload["items"][-1]["construct_key"] = "autonomy"
    with pytest.raises(ValidationError, match="each version 1 construct"):
        MatchingResult.model_validate(result_payload)


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"assigned_item_count": 3}, "answered plus skipped"),
        ({"assigned_item_count": 5, "answered_item_count": 5}, "account for 4"),
        ({"raw_score": 5}, "cannot exceed"),
    ],
)
def test_candidate_response_summary_rejects_impossible_counts(
    changes: dict[str, int], message: str
) -> None:
    """Persisted matching evidence cannot contain impossible assessment traces."""

    payload = {
        "rating": 3,
        "confidence": "high",
        "raw_score": 0,
        "assigned_item_count": 4,
        "answered_item_count": 4,
        "skipped_item_count": 0,
        **changes,
    }
    with pytest.raises(ValidationError, match=message):
        CandidateResponseSummary.model_validate(payload)


def test_role_evidence_summary_rejects_an_inconsistent_target() -> None:
    """Persisted explanations cannot disagree with their declared comparison rule."""

    with pytest.raises(ValidationError, match="match the declared comparison target"):
        RoleEvidenceSummary(
            rating=5,
            confidence=ConfidenceLevel.HIGH,
            rationale="Synthetic rationale.",
            evidence=("Synthetic evidence.",),
            comparison_target=ComparisonTarget.INVERSE_ROLE_RATING,
            comparison_rating=5,
        )


def test_missing_approved_question_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A library gap never falls back to generated or unreviewed content."""

    monkeypatch.setattr(matching_module, "APPROVED_INTERVIEW_QUESTIONS_BY_KEY", {})
    with pytest.raises(MatchingError) as error:
        match_construct(
            role_rating(ConstructKey.AUTONOMY),
            candidate_score(ConstructKey.AUTONOMY),
            role_profile_approved=True,
        )
    assert error.value.code is MatchingErrorCode.QUESTION_NOT_FOUND

"""Pure, deterministic role-to-candidate matching for interview preparation.

The module deliberately produces one result per construct. It does not compute
an aggregate, rank candidates, or make an employment recommendation. Callers
remain responsible for consent and report-access policy at the API boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .assessment import ITEMS_PER_CONSTRUCT, AssessmentScoreResult, CandidateConstructScore
from .constructs import (
    CONSTRUCT_DEFINITIONS_BY_KEY,
    CONSTRUCT_KEYS,
    AlignmentClassification,
    ComparisonTarget,
    ConfidenceLevel,
    ConstructKey,
    Rating,
)
from .role_extraction import RoleConstructRating
from .scoring_config import Version

MATCHING_ALGORITHM_VERSION: Final = "1.0.0"

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
QuestionIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$",
    ),
]


class MatchingRule(StrEnum):
    """Stable identifiers for the rule that produced a classification."""

    ROLE_PROFILE_NOT_APPROVED = "role_profile_not_approved"
    LOW_CONFIDENCE = "low_confidence"
    DIFFERENCE_AT_MOST_ONE = "difference_at_most_one"
    DIFFERENCE_EQUALS_TWO = "difference_equals_two"
    DIFFERENCE_AT_LEAST_THREE = "difference_at_least_three"


class MatchingErrorCode(StrEnum):
    """Stable codes for cross-document inputs that cannot be compared."""

    CONSTRUCT_MISMATCH = "construct_mismatch"
    QUESTION_NOT_FOUND = "question_not_found"


class MatchingError(ValueError):
    """Raised when valid snapshots cannot be combined into a matching result."""

    code: MatchingErrorCode

    def __init__(self, code: MatchingErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class MatchingRoleProfile(BaseModel):
    """The approved-state flag and complete role-rating snapshot used by the engine."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approved: bool
    constructs: Annotated[
        tuple[RoleConstructRating, ...],
        Field(min_length=len(CONSTRUCT_KEYS), max_length=len(CONSTRUCT_KEYS)),
    ]

    @model_validator(mode="after")
    def require_every_construct(self) -> Self:
        """Reject incomplete or ambiguous role snapshots before matching."""

        keys = [construct.key for construct in self.constructs]
        if len(set(keys)) != len(keys) or set(keys) != set(CONSTRUCT_KEYS):
            raise ValueError("constructs must contain each version 1 construct exactly once")
        return self


class InterviewQuestion(BaseModel):
    """One reviewed, stable interview question suitable for persistence by id."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: QuestionIdentifier
    text: NonEmptyString


class InterviewQuestionPair(BaseModel):
    """A deterministic primary question and optional interviewer follow-up."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary: InterviewQuestion
    follow_up: InterviewQuestion


class InterviewQuestionLibraryEntry(BaseModel):
    """An approved question pair keyed by construct and engine classification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    construct_key: ConstructKey
    classification: AlignmentClassification
    review_status: Literal["approved"]
    questions: InterviewQuestionPair


class CandidateResponseSummary(BaseModel):
    """Traceable assessment evidence behind one candidate construct rating."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rating: Rating
    confidence: ConfidenceLevel
    raw_score: int
    assigned_item_count: Annotated[int, Field(ge=0)]
    answered_item_count: Annotated[int, Field(ge=0)]
    skipped_item_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def require_consistent_counts(self) -> Self:
        """Reject trace summaries that cannot come from the pilot instrument."""

        if self.assigned_item_count != self.answered_item_count + self.skipped_item_count:
            raise ValueError("assigned item count must equal answered plus skipped items")
        if self.assigned_item_count != ITEMS_PER_CONSTRUCT:
            raise ValueError(
                f"each construct summary must account for {ITEMS_PER_CONSTRUCT} assigned items"
            )
        if abs(self.raw_score) > self.answered_item_count:
            raise ValueError("raw score cannot exceed the number of answered items")
        return self


class RoleEvidenceSummary(BaseModel):
    """Role evidence and the inspectable target used for comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rating: Rating
    confidence: ConfidenceLevel
    rationale: NonEmptyString
    evidence: Annotated[tuple[NonEmptyString, ...], Field(min_length=1)]
    comparison_target: ComparisonTarget
    comparison_rating: Rating

    @model_validator(mode="after")
    def require_consistent_target(self) -> Self:
        """Keep the stored target reproducible from its declared rule."""

        expected = (
            6 - self.rating
            if self.comparison_target is ComparisonTarget.INVERSE_ROLE_RATING
            else self.rating
        )
        if self.comparison_rating != expected:
            raise ValueError("comparison rating must match the declared comparison target")
        return self


class RuleExplanation(BaseModel):
    """Machine-readable and plain-language account of the applied boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: MatchingRule
    absolute_difference: Annotated[int, Field(ge=0, le=4)]
    description: NonEmptyString


class AlignmentExplanation(BaseModel):
    """Evidence payload required to understand one construct classification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: RoleEvidenceSummary
    candidate_response: CandidateResponseSummary
    applied_rule: RuleExplanation
    uncertainty: str | None


class AlignmentItem(BaseModel):
    """One explainable interview-preparation signal; never a hiring decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    construct_key: ConstructKey
    classification: AlignmentClassification
    confidence: ConfidenceLevel
    explanation: AlignmentExplanation
    interview_questions: InterviewQuestionPair


class MatchingResult(BaseModel):
    """Versioned set of six independent construct comparisons."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    algorithm_version: Literal["1.0.0"]
    role_profile_approved: bool
    assessment_definition_id: str
    assessment_definition_version: Version
    scoring_version: Version
    items: Annotated[
        tuple[AlignmentItem, ...],
        Field(min_length=len(CONSTRUCT_KEYS), max_length=len(CONSTRUCT_KEYS)),
    ]

    @model_validator(mode="after")
    def require_every_construct(self) -> Self:
        """Keep persisted result snapshots complete and unambiguous."""

        keys = [item.construct_key for item in self.items]
        if len(set(keys)) != len(keys) or set(keys) != set(CONSTRUCT_KEYS):
            raise ValueError("items must contain each version 1 construct exactly once")
        return self


def _question(
    construct_key: ConstructKey,
    classification: AlignmentClassification,
    primary: str,
    follow_up: str,
) -> InterviewQuestionLibraryEntry:
    """Build one approved library entry with stable, derivable question ids."""

    prefix = f"{construct_key.value}.{classification.value}"
    return InterviewQuestionLibraryEntry(
        construct_key=construct_key,
        classification=classification,
        review_status="approved",
        questions=InterviewQuestionPair(
            primary=InterviewQuestion(id=f"{prefix}.primary.v1", text=primary),
            follow_up=InterviewQuestion(id=f"{prefix}.follow-up.v1", text=follow_up),
        ),
    )


# Every construct/classification pair is explicit so selection is total and
# deterministic, including insufficient-evidence cases.
APPROVED_INTERVIEW_QUESTION_LIBRARY_V1: Final[tuple[InterviewQuestionLibraryEntry, ...]] = (
    _question(
        ConstructKey.AUTONOMY,
        AlignmentClassification.ALIGNED,
        "Tell me about a role where the level of day-to-day ownership worked well for you.",
        "What decisions did you make independently, and when did you seek direction?",
    ),
    _question(
        ConstructKey.AUTONOMY,
        AlignmentClassification.WORTH_DISCUSSING,
        (
            "Tell me about a time the amount of direction you received differed "
            "from what you preferred."
        ),
        "How did you clarify decision boundaries and stay effective?",
    ),
    _question(
        ConstructKey.AUTONOMY,
        AlignmentClassification.POTENTIAL_FRICTION,
        (
            "Describe a project where you had to work with substantially more or "
            "less autonomy than usual."
        ),
        "What support or working agreement helped you deliver effectively?",
    ),
    _question(
        ConstructKey.AUTONOMY,
        AlignmentClassification.INSUFFICIENT_EVIDENCE,
        "Tell me how you prefer decisions and ownership to be divided in your day-to-day work.",
        "Can you share a recent example of that arrangement working well?",
    ),
    _question(
        ConstructKey.STRUCTURE,
        AlignmentClassification.ALIGNED,
        "Tell me about a role where the level of process and clarity supported your best work.",
        "Which routines or expectations were most useful?",
    ),
    _question(
        ConstructKey.STRUCTURE,
        AlignmentClassification.WORTH_DISCUSSING,
        "Describe a time the available process or direction differed from what you preferred.",
        "How did you create enough clarity to move forward?",
    ),
    _question(
        ConstructKey.STRUCTURE,
        AlignmentClassification.POTENTIAL_FRICTION,
        (
            "Tell me about a time you worked with much more or less structure than "
            "you normally prefer."
        ),
        "What support, information, or routines helped you work effectively?",
    ),
    _question(
        ConstructKey.STRUCTURE,
        AlignmentClassification.INSUFFICIENT_EVIDENCE,
        "Tell me what kinds of goals, routines, and direction help you work effectively.",
        "How do you respond when those conditions are not available?",
    ),
    _question(
        ConstructKey.AMBIGUITY,
        AlignmentClassification.ALIGNED,
        (
            "Tell me about a time you worked effectively while requirements were "
            "incomplete or changing."
        ),
        "How did you decide what to clarify and what to act on?",
    ),
    _question(
        ConstructKey.AMBIGUITY,
        AlignmentClassification.WORTH_DISCUSSING,
        "Describe a project where uncertainty affected how you planned your work.",
        "What information or checkpoints helped you maintain progress?",
    ),
    _question(
        ConstructKey.AMBIGUITY,
        AlignmentClassification.POTENTIAL_FRICTION,
        (
            "Tell me about a time requirements were incomplete or changed quickly. "
            "How did you decide what to do next?"
        ),
        "What support, information, or routines helped you work effectively?",
    ),
    _question(
        ConstructKey.AMBIGUITY,
        AlignmentClassification.INSUFFICIENT_EVIDENCE,
        "Tell me how you approach work when important details are not yet known.",
        "Can you share an example and the outcome?",
    ),
    _question(
        ConstructKey.COLLABORATION,
        AlignmentClassification.ALIGNED,
        "Tell me about a team interaction pattern that helped you do strong work.",
        "How did you contribute while preserving time for individual work?",
    ),
    _question(
        ConstructKey.COLLABORATION,
        AlignmentClassification.WORTH_DISCUSSING,
        "Describe a time a role required more or less coordination than you expected.",
        "How did you adapt your communication and working habits?",
    ),
    _question(
        ConstructKey.COLLABORATION,
        AlignmentClassification.POTENTIAL_FRICTION,
        (
            "Tell me about a project whose collaboration demands differed greatly "
            "from your preference."
        ),
        "What agreements or boundaries helped the team and your own work?",
    ),
    _question(
        ConstructKey.COLLABORATION,
        AlignmentClassification.INSUFFICIENT_EVIDENCE,
        "Tell me how you prefer to balance independent work with coordination and discussion.",
        "What recent example best illustrates that preference?",
    ),
    _question(
        ConstructKey.MASTERY,
        AlignmentClassification.ALIGNED,
        "Tell me about a technically difficult problem that kept you engaged.",
        "How did you deepen your knowledge while delivering the work?",
    ),
    _question(
        ConstructKey.MASTERY,
        AlignmentClassification.WORTH_DISCUSSING,
        (
            "Describe a time a role offered a different level of technical challenge "
            "than you expected."
        ),
        "How did you find or create useful learning opportunities?",
    ),
    _question(
        ConstructKey.MASTERY,
        AlignmentClassification.POTENTIAL_FRICTION,
        (
            "Tell me about a period when the depth of technical learning available "
            "differed greatly from what motivated you."
        ),
        "What made the work sustainable or helped you remain effective?",
    ),
    _question(
        ConstructKey.MASTERY,
        AlignmentClassification.INSUFFICIENT_EVIDENCE,
        (
            "Tell me what kinds of learning and problem-solving opportunities are "
            "most engaging for you."
        ),
        "Can you share a recent example?",
    ),
    _question(
        ConstructKey.PACE,
        AlignmentClassification.ALIGNED,
        "Tell me about a work pace and mix of priorities that helped you be effective.",
        "How did you protect quality while maintaining momentum?",
    ),
    _question(
        ConstructKey.PACE,
        AlignmentClassification.WORTH_DISCUSSING,
        "Describe a time the pace or amount of context switching differed from what you expected.",
        "How did you organize the work and communicate tradeoffs?",
    ),
    _question(
        ConstructKey.PACE,
        AlignmentClassification.POTENTIAL_FRICTION,
        (
            "Tell me about a role with substantially more or less urgency and context "
            "switching than you preferred."
        ),
        "What boundaries or practices helped you remain effective?",
    ),
    _question(
        ConstructKey.PACE,
        AlignmentClassification.INSUFFICIENT_EVIDENCE,
        (
            "Tell me what pace and balance between focus and shifting priorities "
            "supports your best work."
        ),
        "How have you handled a different pace when the role required it?",
    ),
)

APPROVED_INTERVIEW_QUESTIONS_BY_KEY: Final[
    Mapping[tuple[ConstructKey, AlignmentClassification], InterviewQuestionLibraryEntry]
] = MappingProxyType(
    {
        (entry.construct_key, entry.classification): entry
        for entry in APPROVED_INTERVIEW_QUESTION_LIBRARY_V1
    }
)

_CONFIDENCE_ORDER: Final[Mapping[ConfidenceLevel, int]] = MappingProxyType(
    {
        ConfidenceLevel.LOW: 0,
        ConfidenceLevel.MEDIUM: 1,
        ConfidenceLevel.HIGH: 2,
    }
)


def comparison_rating(construct_key: ConstructKey, role_rating: int) -> int:
    """Return the inspectable role target, applying structure's inverse rule."""

    definition = CONSTRUCT_DEFINITIONS_BY_KEY[construct_key]
    if definition.comparison_target is ComparisonTarget.INVERSE_ROLE_RATING:
        return 6 - role_rating
    return role_rating


def lower_confidence(
    role_confidence: ConfidenceLevel,
    candidate_confidence: ConfidenceLevel,
) -> ConfidenceLevel:
    """Return the lower evidence confidence using the documented ordinal scale."""

    return min((role_confidence, candidate_confidence), key=_CONFIDENCE_ORDER.__getitem__)


def _classify(
    *,
    approved: bool,
    confidence: ConfidenceLevel,
    difference: int,
) -> tuple[AlignmentClassification, MatchingRule, str, str | None]:
    """Apply approval, confidence, and distance gates in fail-closed order."""

    if not approved:
        return (
            AlignmentClassification.INSUFFICIENT_EVIDENCE,
            MatchingRule.ROLE_PROFILE_NOT_APPROVED,
            "The role profile is not approved, so no alignment or friction label is produced.",
            "Role ratings require human approval before interpretation.",
        )
    if confidence is ConfidenceLevel.LOW:
        return (
            AlignmentClassification.INSUFFICIENT_EVIDENCE,
            MatchingRule.LOW_CONFIDENCE,
            (
                "At least one evidence source has low confidence, so no alignment or "
                "friction label is produced."
            ),
            "The lower of role and candidate confidence is low.",
        )
    if difference <= 1:
        return (
            AlignmentClassification.ALIGNED,
            MatchingRule.DIFFERENCE_AT_MOST_ONE,
            "The absolute rating difference is at most 1.",
            None,
        )
    if difference == 2:
        return (
            AlignmentClassification.WORTH_DISCUSSING,
            MatchingRule.DIFFERENCE_EQUALS_TWO,
            "The absolute rating difference is exactly 2.",
            None,
        )
    return (
        AlignmentClassification.POTENTIAL_FRICTION,
        MatchingRule.DIFFERENCE_AT_LEAST_THREE,
        "The absolute rating difference is at least 3.",
        None,
    )


def _select_questions(
    construct_key: ConstructKey,
    classification: AlignmentClassification,
) -> InterviewQuestionPair:
    """Select the sole approved pair for a construct/classification key."""

    entry = APPROVED_INTERVIEW_QUESTIONS_BY_KEY.get((construct_key, classification))
    if entry is None:
        raise MatchingError(
            MatchingErrorCode.QUESTION_NOT_FOUND,
            f"No approved questions exist for {construct_key.value}/{classification.value}",
        )
    return entry.questions


def match_construct(
    role: RoleConstructRating,
    candidate: CandidateConstructScore,
    *,
    role_profile_approved: bool,
) -> AlignmentItem:
    """Compare one construct without I/O, randomness, mutation, or hidden weighting."""

    if role.key is not candidate.construct_key:
        raise MatchingError(
            MatchingErrorCode.CONSTRUCT_MISMATCH,
            (
                f"Role construct {role.key.value} cannot be compared with "
                f"candidate construct {candidate.construct_key.value}"
            ),
        )

    definition = CONSTRUCT_DEFINITIONS_BY_KEY[role.key]
    target_rating = comparison_rating(role.key, role.rating)
    difference = abs(target_rating - candidate.rating)
    confidence = lower_confidence(role.confidence, candidate.confidence)
    classification, rule, description, uncertainty = _classify(
        approved=role_profile_approved,
        confidence=confidence,
        difference=difference,
    )

    return AlignmentItem(
        construct_key=role.key,
        classification=classification,
        confidence=confidence,
        explanation=AlignmentExplanation(
            role=RoleEvidenceSummary(
                rating=role.rating,
                confidence=role.confidence,
                rationale=role.rationale,
                evidence=tuple(role.evidence),
                comparison_target=definition.comparison_target,
                comparison_rating=target_rating,
            ),
            candidate_response=CandidateResponseSummary(
                rating=candidate.rating,
                confidence=candidate.confidence,
                raw_score=candidate.raw_score,
                assigned_item_count=candidate.assigned_item_count,
                answered_item_count=candidate.answered_item_count,
                skipped_item_count=candidate.skipped_item_count,
            ),
            applied_rule=RuleExplanation(
                rule=rule,
                absolute_difference=difference,
                description=description,
            ),
            uncertainty=uncertainty,
        ),
        interview_questions=_select_questions(role.key, classification),
    )


def match_role_profile(
    role_profile: MatchingRoleProfile,
    candidate_scores: AssessmentScoreResult,
) -> MatchingResult:
    """Compare all six constructs in canonical order and retain input versions."""

    roles_by_key = {construct.key: construct for construct in role_profile.constructs}
    candidates_by_key = {score.construct_key: score for score in candidate_scores.construct_scores}
    items = tuple(
        match_construct(
            roles_by_key[key],
            candidates_by_key[key],
            role_profile_approved=role_profile.approved,
        )
        for key in CONSTRUCT_KEYS
    )

    return MatchingResult(
        algorithm_version=MATCHING_ALGORITHM_VERSION,
        role_profile_approved=role_profile.approved,
        assessment_definition_id=candidate_scores.assessment_definition_id,
        assessment_definition_version=candidate_scores.assessment_definition_version,
        scoring_version=candidate_scores.scoring_version,
        items=items,
    )

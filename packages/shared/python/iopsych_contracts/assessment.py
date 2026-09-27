"""Pure versioned assessment contracts and deterministic scoring."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .constructs import CONSTRUCT_KEYS, ConfidenceLevel, ConstructKey, Rating
from .scoring_config import ScoringConfig, Version

ASSESSMENT_BLOCK_COUNT = 6
ITEMS_PER_BLOCK = 4
ITEMS_PER_CONSTRUCT = 4

DomainIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$",
    ),
]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
StatementText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class AssessmentDefinitionStatus(StrEnum):
    """Lifecycle states for an immutable assessment definition snapshot."""

    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class AssessmentItem(BaseModel):
    """One behaviorally worded work-preference statement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: DomainIdentifier
    construct_key: ConstructKey
    statement: StatementText


class AssessmentBlock(BaseModel):
    """A forced-choice block containing four distinct constructs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: DomainIdentifier
    position: Annotated[int, Field(strict=True, ge=1, le=ASSESSMENT_BLOCK_COUNT)]
    items: Annotated[
        tuple[AssessmentItem, ...],
        Field(min_length=ITEMS_PER_BLOCK, max_length=ITEMS_PER_BLOCK),
    ]


class AssessmentDefinition(BaseModel):
    """Versioned assessment content plus the exact scoring policy it uses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: DomainIdentifier
    version: Version
    status: AssessmentDefinitionStatus
    title: ShortText
    blocks: Annotated[
        tuple[AssessmentBlock, ...],
        Field(min_length=ASSESSMENT_BLOCK_COUNT, max_length=ASSESSMENT_BLOCK_COUNT),
    ]
    scoring: ScoringConfig

    @model_validator(mode="after")
    def require_balanced_unique_content(self) -> Self:
        """Enforce the six-block balanced design and reachable score range."""

        block_ids = [block.id for block in self.blocks]
        if len(set(block_ids)) != ASSESSMENT_BLOCK_COUNT:
            raise ValueError("block ids must be unique")

        positions = {block.position for block in self.blocks}
        if positions != set(range(1, ASSESSMENT_BLOCK_COUNT + 1)):
            raise ValueError("block positions must contain every position from 1 through 6")

        item_ids = [item.id for block in self.blocks for item in block.items]
        if len(set(item_ids)) != ASSESSMENT_BLOCK_COUNT * ITEMS_PER_BLOCK:
            raise ValueError("item ids must be unique across the assessment")

        for block in self.blocks:
            block_constructs = {item.construct_key for item in block.items}
            if len(block_constructs) != ITEMS_PER_BLOCK:
                raise ValueError("a construct may appear at most once in a block")

        exposure = Counter(item.construct_key for block in self.blocks for item in block.items)
        for construct_key in CONSTRUCT_KEYS:
            if exposure[construct_key] != ITEMS_PER_CONSTRUCT:
                raise ValueError(
                    f"construct {construct_key.value} must appear exactly "
                    f"{ITEMS_PER_CONSTRUCT} times"
                )

        ordered_thresholds = sorted(
            self.scoring.rating_thresholds,
            key=lambda threshold: threshold.minimum_raw_score,
        )
        if (
            ordered_thresholds[0].minimum_raw_score != -ITEMS_PER_CONSTRUCT
            or ordered_thresholds[-1].maximum_raw_score != ITEMS_PER_CONSTRUCT
        ):
            raise ValueError("rating thresholds must cover the complete reachable raw-score range")
        return self


class AnsweredBlockResponse(BaseModel):
    """A candidate's distinct most-like and least-like selections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    block_id: DomainIdentifier
    skipped: Literal[False]
    most_like_item_id: DomainIdentifier
    least_like_item_id: DomainIdentifier

    @model_validator(mode="after")
    def require_distinct_selections(self) -> Self:
        """One statement cannot be both most and least like the candidate."""

        if self.most_like_item_id == self.least_like_item_id:
            raise ValueError("most-like and least-like selections must be different items")
        return self


class SkippedBlockResponse(BaseModel):
    """An explicit prefer-not-to-answer choice for one block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    block_id: DomainIdentifier
    skipped: Literal[True]
    most_like_item_id: None
    least_like_item_id: None


AssessmentBlockResponse = Annotated[
    AnsweredBlockResponse | SkippedBlockResponse,
    Field(discriminator="skipped"),
]


class AssessmentResponseSet(BaseModel):
    """Persistable save/resume snapshot tied to one definition version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_definition_id: DomainIdentifier
    assessment_definition_version: Version
    responses: Annotated[
        tuple[AssessmentBlockResponse, ...],
        Field(max_length=ASSESSMENT_BLOCK_COUNT),
    ]

    @model_validator(mode="after")
    def require_unique_blocks(self) -> Self:
        """Prevent ambiguous replacement semantics inside a snapshot."""

        block_ids = [response.block_id for response in self.responses]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("a response set may contain at most one response per block")
        return self


class CandidateConstructScore(BaseModel):
    """Traceable result for one construct."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    construct_key: ConstructKey
    raw_score: int = Field(strict=True)
    rating: Rating
    confidence: ConfidenceLevel
    assigned_item_count: int = Field(strict=True, ge=0)
    answered_item_count: int = Field(strict=True, ge=0)
    skipped_item_count: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def require_consistent_counts(self) -> Self:
        """Reject score snapshots that cannot come from this instrument."""

        if self.assigned_item_count != self.answered_item_count + self.skipped_item_count:
            raise ValueError("assigned item count must equal answered plus skipped items")
        if self.assigned_item_count != ITEMS_PER_CONSTRUCT:
            raise ValueError(
                f"each construct score must account for {ITEMS_PER_CONSTRUCT} assigned items"
            )
        if abs(self.raw_score) > self.answered_item_count:
            raise ValueError("raw score cannot exceed the number of answered items")
        return self


class AssessmentScoreResult(BaseModel):
    """Version-stamped scoring output suitable for immutable persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_definition_id: DomainIdentifier
    assessment_definition_version: Version
    scoring_version: Version
    construct_scores: Annotated[
        tuple[CandidateConstructScore, ...],
        Field(min_length=len(CONSTRUCT_KEYS), max_length=len(CONSTRUCT_KEYS)),
    ]

    @model_validator(mode="after")
    def require_every_construct(self) -> Self:
        """Require exactly one persisted score for each version 1 construct."""

        score_keys = [score.construct_key for score in self.construct_scores]
        if set(score_keys) != set(CONSTRUCT_KEYS):
            raise ValueError("construct scores must contain every construct exactly once")
        return self


class AssessmentScoringErrorCode(StrEnum):
    """Stable failure codes for definition/response combinations."""

    DEFINITION_MISMATCH = "definition_mismatch"
    INCOMPLETE_ASSESSMENT = "incomplete_assessment"
    UNKNOWN_BLOCK = "unknown_block"
    INVALID_ITEM_SELECTION = "invalid_item_selection"
    UNMAPPED_RAW_SCORE = "unmapped_raw_score"
    UNMAPPED_CONFIDENCE = "unmapped_confidence"


class AssessmentScoringError(ValueError):
    """Domain error raised when otherwise valid snapshots cannot be scored."""

    code: AssessmentScoringErrorCode

    def __init__(self, code: AssessmentScoringErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _rating_for_raw_score(raw_score: int, config: ScoringConfig) -> int:
    """Resolve one raw score through inclusive configured thresholds."""

    for threshold in config.rating_thresholds:
        if threshold.minimum_raw_score <= raw_score <= threshold.maximum_raw_score:
            return threshold.rating
    raise AssessmentScoringError(
        AssessmentScoringErrorCode.UNMAPPED_RAW_SCORE,
        f"No rating threshold contains raw score {raw_score}",
    )


def _confidence_for_skips(skipped_items: int, config: ScoringConfig) -> ConfidenceLevel:
    """Resolve per-construct confidence from skipped assigned statements."""

    rules = (
        config.candidate_confidence.high,
        config.candidate_confidence.medium,
        config.candidate_confidence.low,
    )
    for rule in rules:
        maximum = rule.maximum_skipped_items
        if skipped_items >= rule.minimum_skipped_items and (
            maximum is None or skipped_items <= maximum
        ):
            return ConfidenceLevel(rule.level)
    raise AssessmentScoringError(
        AssessmentScoringErrorCode.UNMAPPED_CONFIDENCE,
        f"No confidence rule contains {skipped_items} skipped items",
    )


def score_assessment(
    definition: AssessmentDefinition,
    response_set: AssessmentResponseSet,
) -> AssessmentScoreResult:
    """Score a complete forced-choice response set without I/O or mutable state."""

    if (
        response_set.assessment_definition_id != definition.id
        or response_set.assessment_definition_version != definition.version
    ):
        raise AssessmentScoringError(
            AssessmentScoringErrorCode.DEFINITION_MISMATCH,
            "Response set does not reference the supplied assessment definition version",
        )

    blocks_by_id = {block.id: block for block in definition.blocks}
    responses_by_block = {response.block_id: response for response in response_set.responses}
    unknown_blocks = responses_by_block.keys() - blocks_by_id.keys()
    if unknown_blocks:
        unknown_block = sorted(unknown_blocks)[0]
        raise AssessmentScoringError(
            AssessmentScoringErrorCode.UNKNOWN_BLOCK,
            f"Response references unknown block {unknown_block}",
        )
    if len(responses_by_block) != len(blocks_by_id):
        raise AssessmentScoringError(
            AssessmentScoringErrorCode.INCOMPLETE_ASSESSMENT,
            "Every assessment block must be answered or explicitly skipped before scoring",
        )

    raw_scores = dict.fromkeys(CONSTRUCT_KEYS, 0)
    answered_counts = dict.fromkeys(CONSTRUCT_KEYS, 0)
    skipped_counts = dict.fromkeys(CONSTRUCT_KEYS, 0)

    for block in definition.blocks:
        response = responses_by_block[block.id]
        if isinstance(response, SkippedBlockResponse):
            for item in block.items:
                skipped_counts[item.construct_key] += 1
            continue

        items_by_id = {item.id: item for item in block.items}
        most_like = items_by_id.get(response.most_like_item_id)
        least_like = items_by_id.get(response.least_like_item_id)
        if most_like is None or least_like is None:
            raise AssessmentScoringError(
                AssessmentScoringErrorCode.INVALID_ITEM_SELECTION,
                f"Selections for block {block.id} must reference items in that block",
            )

        for item in block.items:
            answered_counts[item.construct_key] += 1
        raw_scores[most_like.construct_key] += definition.scoring.choice_weights.most_like
        raw_scores[least_like.construct_key] += definition.scoring.choice_weights.least_like

    construct_scores = tuple(
        CandidateConstructScore(
            construct_key=construct_key,
            raw_score=raw_scores[construct_key],
            rating=_rating_for_raw_score(raw_scores[construct_key], definition.scoring),
            confidence=_confidence_for_skips(skipped_counts[construct_key], definition.scoring),
            assigned_item_count=(answered_counts[construct_key] + skipped_counts[construct_key]),
            answered_item_count=answered_counts[construct_key],
            skipped_item_count=skipped_counts[construct_key],
        )
        for construct_key in CONSTRUCT_KEYS
    )
    return AssessmentScoreResult(
        assessment_definition_id=definition.id,
        assessment_definition_version=definition.version,
        scoring_version=definition.scoring.version,
        construct_scores=construct_scores,
    )

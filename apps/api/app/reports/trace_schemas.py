"""Additive v1 item-level evidence resource."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from iopsych_contracts.constructs import AlignmentClassification, ConstructKey
from iopsych_contracts.scoring_config import (
    HighConfidenceRule,
    LowConfidenceRule,
    MediumConfidenceRule,
    RawScoreThreshold,
    ScoringConfig,
)


class TraceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ItemTrace(TraceModel):
    block_id: str
    block_position: Literal[1, 2, 3, 4, 5, 6]
    item_id: str
    statement: str
    choice: Literal["most_like", "least_like", "not_selected", "block_skipped"]
    most_like_item_id: str | None
    least_like_item_id: str | None
    contribution: Literal[-1, 0, 1]


class QuestionSelection(TraceModel):
    algorithm_version: Literal["1.0.0"]
    construct_key: ConstructKey
    classification: AlignmentClassification
    primary_question_id: str
    follow_up_question_id: str


class ConstructTrace(TraceModel):
    construct_key: ConstructKey
    items: Annotated[tuple[ItemTrace, ...], Field(min_length=4, max_length=4)]
    rating_threshold: RawScoreThreshold
    confidence_rule: HighConfidenceRule | MediumConfidenceRule | LowConfidenceRule
    question_selection: QuestionSelection


class ReportTraceV1(TraceModel):
    trace_version: Literal["1.0.0"] = "1.0.0"
    report_id: UUID
    assessment_id: UUID
    role_profile_id: UUID
    role_profile_version: Annotated[int, Field(strict=True, gt=0)]
    algorithm_version: Literal["1.0.0"]
    assessment_definition_id: str
    assessment_definition_version: str
    scoring_version: str
    definition_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    source: Literal["stored_assessment"] = "stored_assessment"
    scoring: ScoringConfig
    constructs: Annotated[tuple[ConstructTrace, ...], Field(min_length=6, max_length=6)]

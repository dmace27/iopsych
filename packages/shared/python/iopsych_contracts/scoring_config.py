"""Versioned forced-choice scoring configuration contracts."""

from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .constructs import Rating

Version = Annotated[str, StringConstraints(pattern=r"^\d+\.\d+\.\d+$")]


class ChoiceWeights(BaseModel):
    """Fixed section 5 weights for most-like and least-like selections."""

    model_config = ConfigDict(extra="forbid")

    most_like: Literal[1]
    least_like: Literal[-1]


class RawScoreThreshold(BaseModel):
    """Inclusive raw-score range mapped to one 1-5 rating."""

    model_config = ConfigDict(extra="forbid")

    rating: Rating
    minimum_raw_score: int = Field(strict=True)
    maximum_raw_score: int = Field(strict=True)

    @model_validator(mode="after")
    def require_ordered_bounds(self) -> Self:
        """Prevent an empty or reversed score range."""

        if self.minimum_raw_score > self.maximum_raw_score:
            raise ValueError("minimum_raw_score must not exceed maximum_raw_score")
        return self


class HighConfidenceRule(BaseModel):
    """High confidence requires every assigned item to be answered."""

    model_config = ConfigDict(extra="forbid")

    level: Literal["high"]
    minimum_skipped_items: Literal[0]
    maximum_skipped_items: Literal[0]


class MediumConfidenceRule(BaseModel):
    """Medium confidence represents exactly one skipped assigned item."""

    model_config = ConfigDict(extra="forbid")

    level: Literal["medium"]
    minimum_skipped_items: Literal[1]
    maximum_skipped_items: Literal[1]


class LowConfidenceRule(BaseModel):
    """Low confidence begins at two skipped items and has no upper bound."""

    model_config = ConfigDict(extra="forbid")

    level: Literal["low"]
    minimum_skipped_items: Literal[2]
    maximum_skipped_items: None


class CandidateConfidenceRules(BaseModel):
    """Candidate confidence boundaries fixed by specification section 7."""

    model_config = ConfigDict(extra="forbid")

    high: HighConfidenceRule
    medium: MediumConfidenceRule
    low: LowConfidenceRule


class ScoringConfig(BaseModel):
    """A versioned mapping from forced-choice raw scores to ratings."""

    model_config = ConfigDict(extra="forbid")

    version: Version
    choice_weights: ChoiceWeights
    rating_thresholds: Annotated[list[RawScoreThreshold], Field(min_length=5, max_length=5)]
    candidate_confidence: CandidateConfidenceRules

    @model_validator(mode="after")
    def require_complete_contiguous_thresholds(self) -> Self:
        """Require exactly one contiguous range for each rating from 1 through 5."""

        ordered_thresholds = sorted(self.rating_thresholds, key=lambda threshold: threshold.rating)
        if [threshold.rating for threshold in ordered_thresholds] != [1, 2, 3, 4, 5]:
            raise ValueError("rating_thresholds must define ratings 1 through 5 exactly once")

        for previous, current in pairwise(ordered_thresholds):
            if current.minimum_raw_score != previous.maximum_raw_score + 1:
                raise ValueError("rating_thresholds must be contiguous and non-overlapping")
        return self

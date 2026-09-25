"""Construct keys, enums, and behaviorally worded metadata."""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CONTRACT_VERSION: Final = "1.0.0"


class ConstructKey(StrEnum):
    """The six job-related constructs approved for version 1."""

    AUTONOMY = "autonomy"
    STRUCTURE = "structure"
    AMBIGUITY = "ambiguity"
    COLLABORATION = "collaboration"
    MASTERY = "mastery"
    PACE = "pace"


class ConfidenceLevel(StrEnum):
    """Ordered evidence-confidence labels used by role and candidate data."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlignmentClassification(StrEnum):
    """Explainable per-construct outcomes; none is an employment decision."""

    ALIGNED = "aligned"
    WORTH_DISCUSSING = "worth_discussing"
    POTENTIAL_FRICTION = "potential_friction"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ComparisonTarget(StrEnum):
    """How to derive the target used by a later deterministic matcher."""

    ROLE_RATING = "role_rating"
    INVERSE_ROLE_RATING = "inverse_role_rating"


Rating = Annotated[int, Field(strict=True, ge=1, le=5)]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ConstructDefinition(BaseModel):
    """Behaviorally concrete construct metadata from specification section 5."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: ConstructKey
    label: NonEmptyString
    role_prompt: NonEmptyString
    candidate_prompt: NonEmptyString
    comparison_target: ComparisonTarget


CONSTRUCT_KEYS: Final[tuple[ConstructKey, ...]] = tuple(ConstructKey)
CONFIDENCE_LEVELS: Final[tuple[ConfidenceLevel, ...]] = tuple(ConfidenceLevel)
ALIGNMENT_CLASSIFICATIONS: Final[tuple[AlignmentClassification, ...]] = tuple(
    AlignmentClassification
)

CONSTRUCT_DEFINITIONS: Final[tuple[ConstructDefinition, ...]] = (
    ConstructDefinition(
        key=ConstructKey.AUTONOMY,
        label="Autonomy",
        role_prompt="How independently the work must be organized",
        candidate_prompt="How strongly the candidate prefers self-direction",
        comparison_target=ComparisonTarget.ROLE_RATING,
    ),
    ConstructDefinition(
        key=ConstructKey.STRUCTURE,
        label="Structure",
        role_prompt="How defined goals, routines, and requirements are",
        candidate_prompt="How strongly the candidate prefers predictable direction",
        comparison_target=ComparisonTarget.INVERSE_ROLE_RATING,
    ),
    ConstructDefinition(
        key=ConstructKey.AMBIGUITY,
        label="Ambiguity tolerance",
        role_prompt="How often priorities or requirements are unclear or changing",
        candidate_prompt="How comfortable the candidate is acting amid uncertainty",
        comparison_target=ComparisonTarget.ROLE_RATING,
    ),
    ConstructDefinition(
        key=ConstructKey.COLLABORATION,
        label="Collaboration",
        role_prompt="How much coordination, pairing, and stakeholder work the role needs",
        candidate_prompt="How much the candidate prefers collaborative work",
        comparison_target=ComparisonTarget.ROLE_RATING,
    ),
    ConstructDefinition(
        key=ConstructKey.MASTERY,
        label="Technical mastery",
        role_prompt="How much deep learning and complex problem solving the role offers",
        candidate_prompt=("How energizing the candidate finds skill development and hard problems"),
        comparison_target=ComparisonTarget.ROLE_RATING,
    ),
    ConstructDefinition(
        key=ConstructKey.PACE,
        label="Pace/context switching",
        role_prompt="How often work requires urgency or shifting between priorities",
        candidate_prompt=("How comfortable the candidate is with variety and shifting priorities"),
        comparison_target=ComparisonTarget.ROLE_RATING,
    ),
)

CONSTRUCT_DEFINITIONS_BY_KEY: Final[Mapping[ConstructKey, ConstructDefinition]] = MappingProxyType(
    {definition.key: definition for definition in CONSTRUCT_DEFINITIONS}
)

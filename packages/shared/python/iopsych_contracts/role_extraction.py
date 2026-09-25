"""Strict role-extraction contracts and source-evidence validation."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .constructs import CONSTRUCT_KEYS, ConfidenceLevel, ConstructKey, Rating

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RoleConstructRating(BaseModel):
    """An LLM-proposed rating that remains subject to human review."""

    model_config = ConfigDict(extra="forbid")

    key: ConstructKey
    rating: Rating
    confidence: ConfidenceLevel
    rationale: NonEmptyString
    evidence: Annotated[list[NonEmptyString], Field(min_length=1)]


class RoleExtraction(BaseModel):
    """Complete draft-only extraction output for all six constructs."""

    model_config = ConfigDict(extra="forbid")

    constructs: Annotated[
        list[RoleConstructRating],
        Field(min_length=len(CONSTRUCT_KEYS), max_length=len(CONSTRUCT_KEYS)),
    ]
    assumptions: list[NonEmptyString]
    needs_human_review: Literal[True]

    @model_validator(mode="after")
    def require_all_constructs_and_review(self) -> Self:
        """Reject duplicate/missing constructs and any attempt to bypass review."""

        observed_keys = {construct.key for construct in self.constructs}
        if observed_keys != set(CONSTRUCT_KEYS):
            raise ValueError("constructs must contain each version 1 construct exactly once")
        return self

    def validate_evidence(self, job_description: str) -> Self:
        """Require every excerpt to occur verbatim in the submitted description."""

        if not job_description.strip():
            raise ValueError("a non-empty job description is required")

        for construct in self.constructs:
            for excerpt in construct.evidence:
                if excerpt not in job_description:
                    raise ValueError(
                        f"evidence for {construct.key.value} is not present in the job description"
                    )
        return self


def parse_role_extraction(payload: object, job_description: str) -> RoleExtraction:
    """Validate both the serialized structure and its trusted source context."""

    return RoleExtraction.model_validate(payload).validate_evidence(job_description)

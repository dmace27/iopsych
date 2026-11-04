"""Retained v1 readers; adding a release must never replace a historical entry."""

import json
from functools import partial
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.auth.errors import resource_conflict
from iopsych_contracts.assessment import (
    AssessmentDefinition,
    AssessmentDefinitionStatus,
    AssessmentResponseSet,
    AssessmentScoreResult,
    score_assessment,
)
from iopsych_contracts.matching import (
    MatchingAlgorithmVersion,
    MatchingResult,
    MatchingRoleProfile,
    match_role_profile,
)

LEGACY_DEFINITION_PATH = Path(__file__).parent / "definitions/legacy-v1.json"
LEGACY_SHA256 = "021233ca4dab9c86b87aeabca88f503bf7c70fd0b0d324c64e788b620aeb6e3c"
# No actual reviewed assessment exists. A future approval requires a new reviewed entry.
REVIEWED_DEFINITIONS: frozenset[tuple[str, str, str]] = frozenset()
RETIRED_DEFINITIONS: frozenset[tuple[str, str, str]] = frozenset()
SCORERS = MappingProxyType({"1.0.0": score_assessment})
MATCHERS = MappingProxyType(
    {
        version.value: partial(match_role_profile, algorithm_version=version)
        for version in MatchingAlgorithmVersion
    }
)
REPORT_READERS = MappingProxyType(
    {version.value: MatchingResult.model_validate for version in MatchingAlgorithmVersion}
)


def definition_hash(payload: dict[str, Any]) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()


class AssignmentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal[1] = 1
    definition: AssessmentDefinition
    definition_sha256: str
    matching_algorithm_version: str


class AssignmentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    assessment_definition_id: str
    assessment_definition_version: str
    scoring_version: str
    matching_algorithm_version: str
    definition_sha256: str


class AssignedDefinitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignment: AssignmentMetadata
    definition: AssessmentDefinition


def legacy_definition() -> AssessmentDefinition:
    payload = json.loads(LEGACY_DEFINITION_PATH.read_text(encoding="utf-8"))
    if definition_hash(payload) != LEGACY_SHA256:
        raise RuntimeError("Frozen legacy definition checksum mismatch")
    return AssessmentDefinition.model_validate(payload)


def snapshot(definition: AssessmentDefinition, *, algorithm: str = "1.0.0") -> dict[str, Any]:
    return AssignmentSnapshot(
        definition=definition,
        definition_sha256=definition_hash(definition.model_dump(mode="json")),
        matching_algorithm_version=algorithm,
    ).model_dump(mode="json")


def new_assignment(*, allow_synthetic: bool) -> dict[str, Any]:
    definition = legacy_definition()
    key = (definition.id, definition.version, LEGACY_SHA256)
    if (
        definition.status is AssessmentDefinitionStatus.RETIRED
        or key in RETIRED_DEFINITIONS
        or (key not in REVIEWED_DEFINITIONS and not allow_synthetic)
    ):
        raise resource_conflict(
            code="assessment_definition_not_assignable",
            detail="No eligible reviewed assessment definition is configured.",
        )
    return snapshot(definition)


def read_assignment(payload: dict[str, Any] | None) -> AssignmentSnapshot:
    try:
        assignment = AssignmentSnapshot.model_validate(payload)
        definition = assignment.definition
        legacy = legacy_definition()
        if (
            definition.id != legacy.id
            or definition.version != legacy.version
            or definition.scoring.version not in SCORERS
            or definition.scoring != legacy.scoring
            or assignment.matching_algorithm_version not in MATCHERS
            or assignment.definition_sha256 != LEGACY_SHA256
            or definition_hash(definition.model_dump(mode="json")) != assignment.definition_sha256
        ):
            raise ValueError("Unknown or inconsistent assignment")
        return assignment
    except (ValidationError, ValueError) as exc:
        raise resource_conflict(
            code="unsupported_assessment_version",
            detail="The assigned assessment version is unavailable.",
        ) from exc


def definition_response(payload: dict[str, Any] | None) -> AssignedDefinitionResponse:
    assignment = read_assignment(payload)
    definition = assignment.definition
    return AssignedDefinitionResponse(
        assignment=AssignmentMetadata(
            assessment_definition_id=definition.id,
            assessment_definition_version=definition.version,
            scoring_version=definition.scoring.version,
            matching_algorithm_version=assignment.matching_algorithm_version,
            definition_sha256=assignment.definition_sha256,
        ),
        definition=definition,
    )


def score_assignment(
    assignment: AssignmentSnapshot, responses: AssessmentResponseSet
) -> AssessmentScoreResult:
    return SCORERS[assignment.definition.scoring.version](assignment.definition, responses)


def read_scores(payload: dict[str, Any]) -> AssessmentScoreResult:
    try:
        return AssessmentScoreResult.model_validate(payload)
    except ValidationError as exc:
        raise resource_conflict(
            code="unsupported_assessment_version",
            detail="The stored assessment scores are unavailable.",
        ) from exc


def match_assignment(
    assignment: AssignmentSnapshot,
    role: MatchingRoleProfile,
    scores: AssessmentScoreResult,
    *,
    algorithm: str | None = None,
) -> MatchingResult:
    definition = assignment.definition
    if (
        scores.assessment_definition_id != definition.id
        or scores.assessment_definition_version != definition.version
        or scores.scoring_version != definition.scoring.version
    ):
        raise resource_conflict(
            code="unsupported_assessment_version",
            detail="Stored scores do not match the assigned assessment.",
        )
    selected_algorithm = assignment.matching_algorithm_version if algorithm is None else algorithm
    if selected_algorithm not in MATCHERS:
        raise resource_conflict(
            code="unsupported_report_version", detail="The report algorithm is unavailable."
        )
    return MATCHERS[selected_algorithm](role, scores)


def read_report(algorithm: str, payload: object) -> MatchingResult:
    try:
        if not isinstance(payload, dict) or payload.get("algorithm_version") != algorithm:
            raise ValueError("Report version mismatch")
        return REPORT_READERS[algorithm](payload)
    except (KeyError, ValidationError, ValueError) as exc:
        raise resource_conflict(
            code="unsupported_report_version", detail="The stored report version is unavailable."
        ) from exc

"""Read retained evidence without repairing or rematching saved reports."""

from typing import Any
from uuid import UUID

from app.assignments.registry import (
    LEGACY_SHA256,
    SCORERS,
    definition_hash,
    legacy_definition,
    read_assignment,
    read_report,
    read_scores,
)
from app.auth.errors import AccessProblemError, resource_conflict
from app.reports.trace_schemas import ConstructTrace, ItemTrace, QuestionSelection, ReportTraceV1
from iopsych_contracts.assessment import AssessmentResponseSet
from iopsych_contracts.constructs import CONSTRUCT_KEYS
from iopsych_contracts.matching import APPROVED_INTERVIEW_QUESTION_LIBRARY_V1

_QUESTIONS_V1 = {
    (entry.construct_key, entry.classification): (
        entry.questions.primary.id,
        entry.questions.follow_up.id,
    )
    for entry in APPROVED_INTERVIEW_QUESTION_LIBRARY_V1
}


def build_trace(
    *,
    report_id: UUID,
    assessment_id: UUID,
    role_profile_id: UUID,
    role_profile_version: int,
    algorithm_version: str,
    result_json: dict[str, Any],
    definition_json: dict[str, Any] | None,
    responses_json: dict[str, Any] | None,
    scores_json: dict[str, Any] | None,
    assignment_json: dict[str, Any] | None,
) -> ReportTraceV1:
    result = read_report(algorithm_version, result_json)
    if not definition_json or not responses_json or not scores_json:
        raise resource_conflict(
            code="report_trace_unavailable", detail="Saved item-level evidence is unavailable."
        )
    if not all(isinstance(value, dict) for value in (definition_json, responses_json, scores_json)):
        raise resource_conflict(
            code="report_trace_inconsistent", detail="Saved item-level evidence is inconsistent."
        )
    definition = legacy_definition()
    if (
        definition_json.get("id") != definition.id
        or definition_json.get("version") != definition.version
        or (
            isinstance(definition_json.get("scoring"), dict)
            and definition_json["scoring"].get("version") != definition.scoring.version
        )
    ):
        raise resource_conflict(
            code="unsupported_assessment_version", detail="The assessment version is unavailable."
        )
    try:
        if definition_hash(definition_json) != LEGACY_SHA256:
            raise ValueError("Definition content mismatch")
        if assignment_json is not None:
            # Assignment provenance remains frozen when a separate report uses
            # a newer matching algorithm over the same definition and scores.
            if not isinstance(assignment_json, dict):
                raise ValueError("Assignment shape mismatch")
            if (
                assignment_json.get("definition") != definition_json
                or assignment_json.get("definition_sha256") != LEGACY_SHA256
            ):
                raise ValueError("Assignment mismatch")
            read_assignment(assignment_json)
        responses = AssessmentResponseSet.model_validate(responses_json)
        scores = read_scores(scores_json)
        verified = SCORERS[definition.scoring.version](definition, responses)
        if scores != verified:
            raise ValueError("Score mismatch")
        if any(
            getattr(result, field) != getattr(scores, field)
            for field in (
                "assessment_definition_id",
                "assessment_definition_version",
                "scoring_version",
            )
        ):
            raise ValueError("Report version mismatch")
        by_block = {response.block_id: response for response in responses.responses}
        by_score = {score.construct_key: score for score in scores.construct_scores}
        by_result = {item.construct_key: item for item in result.items}
        constructs = []
        for key in CONSTRUCT_KEYS:
            score = by_score[key]
            saved = by_result[key]
            if saved.explanation.candidate_response.model_dump() != score.model_dump(
                exclude={"construct_key"}
            ):
                raise ValueError("Report summary mismatch")
            question_ids = (
                saved.interview_questions.primary.id,
                saved.interview_questions.follow_up.id,
            )
            if question_ids != _QUESTIONS_V1[key, saved.classification]:
                raise ValueError("Question provenance mismatch")
            items = []
            for block in sorted(definition.blocks, key=lambda block: block.position):
                response = by_block[block.id]
                for item in block.items:
                    if item.construct_key != key:
                        continue
                    choice = "not_selected"
                    contribution = 0
                    if response.skipped:
                        choice = "block_skipped"
                    elif item.id == response.most_like_item_id:
                        choice = "most_like"
                        contribution = definition.scoring.choice_weights.most_like
                    elif item.id == response.least_like_item_id:
                        choice = "least_like"
                        contribution = definition.scoring.choice_weights.least_like
                    items.append(
                        ItemTrace.model_validate(
                            {
                                "block_id": block.id,
                                "block_position": block.position,
                                "item_id": item.id,
                                "statement": item.statement,
                                "choice": choice,
                                "contribution": contribution,
                                "most_like_item_id": response.most_like_item_id,
                                "least_like_item_id": response.least_like_item_id,
                            }
                        )
                    )
            threshold = next(
                band
                for band in definition.scoring.rating_thresholds
                if band.minimum_raw_score <= score.raw_score <= band.maximum_raw_score
            )
            rule = getattr(definition.scoring.candidate_confidence, score.confidence.value)
            constructs.append(
                ConstructTrace(
                    construct_key=key,
                    items=tuple(items),
                    rating_threshold=threshold,
                    confidence_rule=rule,
                    question_selection=QuestionSelection(
                        algorithm_version=result.algorithm_version,
                        construct_key=key,
                        classification=saved.classification,
                        primary_question_id=question_ids[0],
                        follow_up_question_id=question_ids[1],
                    ),
                )
            )
        return ReportTraceV1(
            report_id=report_id,
            assessment_id=assessment_id,
            role_profile_id=role_profile_id,
            role_profile_version=role_profile_version,
            algorithm_version=result.algorithm_version,
            assessment_definition_id=definition.id,
            assessment_definition_version=definition.version,
            scoring_version=definition.scoring.version,
            definition_sha256=LEGACY_SHA256,
            scoring=definition.scoring,
            constructs=tuple(constructs),
        )
    except (AccessProblemError, ValueError, KeyError, TypeError, StopIteration) as exc:
        raise resource_conflict(
            code="report_trace_inconsistent", detail="Saved item-level evidence is inconsistent."
        ) from exc

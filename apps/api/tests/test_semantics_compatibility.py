"""Pure retained-reader and report/assignment algorithm independence checks."""

import copy
import json
from pathlib import Path

import pytest

from app.assignments import registry
from app.auth.errors import AccessProblemError
from app.reports.trace import build_trace
from iopsych_contracts.assessment import AssessmentScoreResult
from iopsych_contracts.matching import MatchingRoleProfile

FIXTURES = Path(__file__).parent / "fixtures/report_trace"
SHARED = Path(__file__).resolve().parents[3] / "packages/shared/fixtures"


def test_registry_v1_replay_and_reader_preserve_complete_frozen_result() -> None:
    fixture = json.loads((SHARED / "v1/matching-result/legacy-structure.json").read_text())
    expected = fixture["payload"]
    role = MatchingRoleProfile.model_validate(fixture["context"]["role_profile"])
    scores = AssessmentScoreResult.model_validate(fixture["context"]["candidate_scores"])
    assert registry.MATCHERS["1.0.0"](role, scores).model_dump(mode="json") == expected
    assert registry.read_report("1.0.0", expected).model_dump(mode="json") == expected
    with pytest.raises(AccessProblemError):
        registry.read_report("2.0.0", expected)


@pytest.mark.parametrize("name", ["complete", "skipped", "two-skipped", "all-skipped"])
def test_v2_report_trace_preserves_v1_assignment_and_evidence(name: str) -> None:
    source = json.loads((FIXTURES / f"{name}.source.json").read_text())
    historical = copy.deepcopy(source)
    assignment_payload = registry.snapshot(registry.legacy_definition())
    assignment_before = copy.deepcopy(assignment_payload)
    assignment = registry.read_assignment(assignment_payload)
    scores = AssessmentScoreResult.model_validate(source["scores_json"])
    role = MatchingRoleProfile.model_validate(
        {
            "approved": source["result_json"]["role_profile_approved"],
            "constructs": [
                {
                    "key": item["construct_key"],
                    **{
                        key: item["explanation"]["role"][key]
                        for key in ("rating", "confidence", "rationale", "evidence")
                    },
                }
                for item in source["result_json"]["items"]
            ],
        }
    )
    assert registry.match_assignment(assignment, role, scores).algorithm_version == "1.0.0"
    result = registry.match_assignment(assignment, role, scores, algorithm="2.0.0")
    assert registry.read_report("2.0.0", result.model_dump(mode="json")) == result
    upgraded = {
        **source,
        "algorithm_version": "2.0.0",
        "result_json": result.model_dump(mode="json"),
        "assignment_json": assignment_payload,
    }
    trace = build_trace(**upgraded)
    assert trace.algorithm_version == "2.0.0"
    assert trace.trace_version == "1.0.0"
    assert trace.scoring_version == "1.0.0"
    assert trace.definition_sha256 == registry.LEGACY_SHA256
    assert all(item.question_selection.algorithm_version == "2.0.0" for item in trace.constructs)
    assert source == historical
    assert assignment_payload == assignment_before
    # The historical source remains exactly readable after constructing the upgrade.
    assert build_trace(**source).model_dump(mode="json") == json.loads(
        (FIXTURES / f"{name}.trace.json").read_text()
    )
    upgraded["assignment_json"] = {**assignment_payload, "matching_algorithm_version": "99.0.0"}
    with pytest.raises(AccessProblemError):
        build_trace(**upgraded)
    with pytest.raises(AccessProblemError):
        registry.match_assignment(assignment, role, scores, algorithm="99.0.0")
    with pytest.raises(AccessProblemError):
        registry.match_assignment(
            assignment,
            role,
            scores.model_copy(update={"scoring_version": "99.0.0"}),
            algorithm="2.0.0",
        )


@pytest.mark.parametrize("algorithm", ["1.0.0", "2.0.0", "99.0.0"])
def test_readers_reject_algorithm_target_tampering(algorithm: str) -> None:
    source = json.loads((FIXTURES / "complete.source.json").read_text())
    result = source["result_json"]
    result["algorithm_version"] = algorithm
    structure = next(item for item in result["items"] if item["construct_key"] == "structure")
    structure["explanation"]["role"]["comparison_target"] = (
        "role_rating" if algorithm == "1.0.0" else "inverse_role_rating"
    )
    with pytest.raises(AccessProblemError):
        registry.read_report(algorithm, result)

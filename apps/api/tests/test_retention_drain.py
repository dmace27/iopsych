"""Bounded CLI orchestration and isolated synthetic retention integration."""

import json
import runpy
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Engine, select

from app.database.models import (
    Assessment,
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    CandidateConsent,
    ConsentDecision,
)
from app.database.seed import ALPHA_PROFILE_ID, BEACON_PROFILE_ID, seed_database
from app.database.session import create_session_factory
from app.privacy.config import PrivacySettings
from app.privacy.retention import main

DRAIN = ["--drain", "--max-batches", "3", "--max-seconds", "10"]


@pytest.fixture
def mocked_batch() -> Generator[MagicMock]:
    with (
        patch("app.privacy.retention.create_database_engine"),
        patch("app.privacy.retention.create_session_factory") as factory,
        patch("app.privacy.retention.PrivacyService") as service,
    ):
        service.factory = factory.return_value
        yield service


def test_default_preserves_single_batch(
    mocked_batch: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mocked_batch.return_value.run_retention.return_value.anonymized_assessment_ids = [uuid4()]
    main()
    assert mocked_batch.call_count == 1
    assert capsys.readouterr().out == "Retention complete: 1 assessments anonymized\n"


@pytest.mark.parametrize(
    ("counts", "reason", "attempts", "total"),
    [([2, 2, 2], "max_batches", 3, 6), ([1, 0], "no_progress", 2, 1), ([0], "no_progress", 1, 0)],
)
def test_drain_stops_safely(
    mocked_batch: MagicMock,
    capsys: pytest.CaptureFixture[str],
    counts: list[int],
    reason: str,
    attempts: int,
    total: int,
) -> None:
    mocked_batch.return_value.run_retention.side_effect = [
        MagicMock(anonymized_assessment_ids=[uuid4() for _ in range(count)]) for count in counts
    ]
    main(DRAIN)
    assert json.loads(capsys.readouterr().out) == {
        "attempted_batches": attempts,
        "completed_batches": attempts,
        "assessments_anonymized": total,
        "stop_reason": reason,
    }
    assert mocked_batch.factory.call_count == attempts
    assert mocked_batch.factory.return_value.__exit__.call_count == attempts


@pytest.mark.parametrize(("times", "attempts"), [([0, 10], 0), ([0, 9, 10], 1)])
def test_monotonic_budget_prevents_new_batches(
    mocked_batch: MagicMock,
    capsys: pytest.CaptureFixture[str],
    times: list[int],
    attempts: int,
) -> None:
    mocked_batch.return_value.run_retention.return_value.anonymized_assessment_ids = [uuid4()]
    with patch("app.privacy.retention.time.monotonic", side_effect=times):
        main(DRAIN)
    result = json.loads(capsys.readouterr().out)
    assert result["stop_reason"] == "time_budget"
    assert result["completed_batches"] == attempts
    assert mocked_batch.call_count == attempts


@pytest.mark.parametrize(
    "args",
    [
        ["--drain"],
        ["--max-batches", "2"],
        ["--max-seconds", "2"],
        ["--drain", "--max-batches", "0", "--max-seconds", "1"],
        ["--drain", "--max-batches", "-1", "--max-seconds", "1"],
        ["--drain", "--max-batches", "1", "--max-seconds", "0"],
        ["--drain", "--max-batches", "1", "--max-seconds", "-1"],
        ["--drain", "--max-batches", "1", "--max-seconds", "nan"],
        ["--drain", "--max-batches", "1", "--max-seconds", "inf"],
        ["--max-batches", "private@example.invalid"],
        ["--private-token"],
    ],
)
def test_invalid_bounds_never_open_database(
    mocked_batch: MagicMock, capsys: pytest.CaptureFixture[str], args: list[str]
) -> None:
    with patch("app.privacy.retention.create_database_engine") as engine:
        with pytest.raises(SystemExit) as error:
            main(args)
        assert error.value.code == 2
        engine.assert_not_called()
    assert capsys.readouterr().err == (
        "Retention arguments invalid; use --help for supported bounds.\n"
    )


def test_partial_failure_has_safe_nonzero_summary(
    mocked_batch: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mocked_batch.return_value.run_retention.side_effect = [
        MagicMock(anonymized_assessment_ids=[uuid4()]),
        RuntimeError("private@example.invalid secret-token"),
    ]
    with pytest.raises(SystemExit) as error:
        main(DRAIN)
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "attempted_batches": 2,
        "completed_batches": 1,
        "assessments_anonymized": 1,
        "stop_reason": "error",
    }
    assert "private" not in captured.out + captured.err
    assert "secret" not in captured.out + captured.err


@pytest.mark.parametrize("failure", ["PrivacySettings", "create_database_engine"])
def test_initialization_failure_is_safe(
    mocked_batch: MagicMock, capsys: pytest.CaptureFixture[str], failure: str
) -> None:
    with (
        patch(f"app.privacy.retention.{failure}", side_effect=ValueError("secret")),
        pytest.raises(SystemExit) as error,
    ):
        main(DRAIN)
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out)["attempted_batches"] == 0
    assert "secret" not in captured.out + captured.err


def test_disposal_failure_is_safe(
    mocked_batch: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mocked_batch.return_value.run_retention.return_value.anonymized_assessment_ids = []
    with patch("app.privacy.retention.create_database_engine") as engine:
        engine.return_value.dispose.side_effect = RuntimeError("secret")
        with pytest.raises(SystemExit) as error:
            main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out)["stop_reason"] == "error"
    assert "secret" not in captured.out + captured.err


def test_module_entrypoint_help_never_connects(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("sys.argv", ["retention", "--help"]),
        patch("app.database.session.create_database_engine") as engine,
        pytest.raises(SystemExit) as error,
    ):
        runpy.run_path(main.__code__.co_filename, run_name="__main__")
    assert error.value.code == 0
    engine.assert_not_called()
    output = capsys.readouterr().out
    assert "--max-batches" in output
    assert "--max-seconds" in output


def test_isolated_sqlite_backlog_and_idempotency(
    database_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    factory = create_session_factory(database_engine)
    now = datetime.now(UTC)
    with factory() as session:
        seed_database(session)
        for index in range(6):
            invite = AssessmentInvite(
                role_profile_id=ALPHA_PROFILE_ID if index % 2 else BEACON_PROFILE_ID,
                email=f"synthetic-{index}@example.invalid",
                token_hash=str(uuid4()),
                expires_at=now + timedelta(days=1),
                status=AssessmentInviteStatus.CONSENTED,
            )
            session.add(invite)
            session.flush()
            consent = CandidateConsent(
                invite_id=invite.id, decision=ConsentDecision.CONSENT, notice_version="pilot-v1"
            )
            session.add(consent)
            session.flush()
            session.add(
                Assessment(
                    invite_id=invite.id,
                    consent_id=consent.id,
                    submitted_at=now - timedelta(days=100) if index < 5 else None,
                    retention_expires_at=now - timedelta(days=1)
                    if index < 4
                    else now + timedelta(days=1),
                    definition_json={"synthetic": True},
                    responses_json={"synthetic": True},
                    scores_json={"synthetic": True},
                )
            )
        session.commit()
    with (
        patch("app.privacy.retention.create_database_engine", return_value=database_engine),
        patch.object(database_engine, "dispose"),
        patch(
            "app.privacy.retention.PrivacySettings",
            return_value=PrivacySettings(retention_batch_size=1),
        ),
    ):
        main(DRAIN)
        first = json.loads(capsys.readouterr().out)
        assert first["assessments_anonymized"] == 3
        assert first["stop_reason"] == "max_batches"
        main(DRAIN)
        second = json.loads(capsys.readouterr().out)
        assert second["assessments_anonymized"] == 1
        assert second["stop_reason"] == "no_progress"
        main(DRAIN)
        assert json.loads(capsys.readouterr().out)["assessments_anonymized"] == 0
    with factory() as session:
        assessments = list(session.scalars(select(Assessment)))
        assert sum(row.anonymized_at is not None for row in assessments) == 4
        assert sum(row.responses_json == {"synthetic": True} for row in assessments) == 2
        events = list(
            session.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "candidate_data.anonymized")
            )
        )
        assert len(events) == 4

"""Persisted corruption and disappearing-row boundaries for report traces."""

import copy
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import Select, delete, event, select
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker

from app.auth.errors import AccessProblemError
from app.database.models import (
    AlignmentReport,
    AlignmentReportItem,
    Assessment,
    AssessmentInvite,
    AuditEvent,
    RoleProfile,
    RoleProfileStatus,
)
from app.database.seed import ALPHA_ROLE_ID, ALPHA_USER_ID
from app.reports.trace import build_trace
from tests.test_report_trace import create_report, source
from tests.test_reports import anyio_backend as anyio_backend
from tests.test_reports import headers
from tests.test_reports import report_app as report_app
from tests.test_reports import report_client as report_client
from tests.test_reports import report_factory as report_factory


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["definition_json", "responses_json", "scores_json"])
@pytest.mark.parametrize("corrupt", [["synthetic-corruption"], "synthetic-corruption", 7])
async def test_persisted_non_object_evidence_fails_without_changing_report(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
    field: str,
    corrupt: Any,
) -> None:
    report = await create_report(report_client, report_factory)
    with report_factory() as session:
        assessment = session.get(Assessment, UUID(report["assessment_id"]))
        assert assessment is not None
        setattr(assessment, field, corrupt)
        session.commit()
    auth = headers(report_factory)
    path = f"/v1/reports/{report['id']}"
    denied = await report_client.get(path + "/trace", headers=auth)
    assert denied.status_code == 409
    assert denied.json()["code"] == "report_trace_inconsistent"
    assert denied.json()["detail"] == "Saved item-level evidence is inconsistent."
    assert denied.headers["Cache-Control"] == "no-store"
    assert "constructs" not in denied.json()
    assert "synthetic-corruption" not in denied.text
    assert (await report_client.get(path, headers=auth)).json() == report
    with report_factory() as session:
        saved_source = session.get(Assessment, UUID(report["assessment_id"]))
        assert saved_source is not None
        assert getattr(saved_source, field) == corrupt
        saved = session.get(AlignmentReport, UUID(report["id"]))
        assert saved is not None and saved.result_json == report["result"]
        audits = session.scalars(
            select(AuditEvent).where(
                AuditEvent.entity_id == saved.id,
                AuditEvent.event_type == "alignment_report.trace_read",
            )
        ).all()
        assert len(audits) == 1
        assert audits[0].metadata_json == {
            "http_method": "GET",
            "http_status": 409,
            "outcome": "rejected",
        }


@pytest.mark.anyio
async def test_invitation_profile_mismatch_preserves_historical_report(
    report_client: AsyncClient, report_factory: sessionmaker[Session]
) -> None:
    report = await create_report(report_client, report_factory)
    with report_factory() as session:
        profile = RoleProfile(
            role_id=ALPHA_ROLE_ID,
            version=2,
            status=RoleProfileStatus.DRAFT,
            created_by=ALPHA_USER_ID,
        )
        session.add(profile)
        session.flush()
        assessment = session.get(Assessment, UUID(report["assessment_id"]))
        assert assessment is not None
        invite = session.get(AssessmentInvite, assessment.invite_id)
        assert invite is not None
        invite.role_profile_id = profile.id
        changed_profile_id = profile.id
        invite_id = invite.id
        session.commit()
    auth = headers(report_factory)
    path = f"/v1/reports/{report['id']}"
    denied = await report_client.get(path + "/trace", headers=auth)
    assert denied.status_code == 409
    assert denied.json()["code"] == "report_trace_inconsistent"
    assert denied.headers["Cache-Control"] == "no-store"
    assert "constructs" not in denied.json()
    assert (await report_client.get(path, headers=auth)).json() == report
    with report_factory() as session:
        invite = session.get(AssessmentInvite, invite_id)
        assert invite is not None and invite.role_profile_id == changed_profile_id
        saved = session.get(AlignmentReport, UUID(report["id"]))
        assert saved is not None and saved.result_json == report["result"]


@pytest.mark.anyio
async def test_report_deleted_between_trace_reads_returns_not_found(
    report_client: AsyncClient, report_factory: sessionmaker[Session]
) -> None:
    report = await create_report(report_client, report_factory)
    report_id = UUID(report["id"])
    deleted = False

    def delete_before_report_read(state: ORMExecuteState) -> None:
        nonlocal deleted
        if deleted or not isinstance(state.statement, Select):
            return
        if [entry["entity"] for entry in state.statement.column_descriptions] != [
            AlignmentReport,
            RoleProfile,
        ]:
            return
        deleted = True
        state.session.execute(
            delete(AlignmentReportItem).where(AlignmentReportItem.report_id == report_id)
        )
        state.session.execute(delete(AlignmentReport).where(AlignmentReport.id == report_id))
        assert state.session.get(AlignmentReport, report_id) is None

    auth = headers(report_factory)
    event.listen(Session, "do_orm_execute", delete_before_report_read)
    try:
        denied = await report_client.get(f"/v1/reports/{report_id}/trace", headers=auth)
    finally:
        event.remove(Session, "do_orm_execute", delete_before_report_read)
    assert deleted
    assert denied.status_code == 404
    assert denied.json()["code"] == "resource_not_found"
    assert denied.headers["Cache-Control"] == "no-store"
    assert "constructs" not in denied.json()
    assert (await report_client.get(f"/v1/reports/{report_id}", headers=auth)).status_code == 404
    with report_factory() as session:
        assert session.get(AlignmentReport, report_id) is None
        assert not session.scalars(
            select(AlignmentReportItem).where(AlignmentReportItem.report_id == report_id)
        ).all()
        assessment = session.get(Assessment, UUID(report["assessment_id"]))
        assert assessment is not None and assessment.responses_json


@pytest.mark.parametrize("corrupt", [["synthetic-corruption"], "synthetic-corruption", 7])
def test_malformed_retained_assignment_fails_without_mutating_snapshot(corrupt: Any) -> None:
    payload = source()
    payload["assignment_json"] = corrupt
    before = copy.deepcopy(payload)
    with pytest.raises(AccessProblemError) as error:
        build_trace(**payload)
    assert error.value.code == "report_trace_inconsistent"
    assert error.value.detail == "Saved item-level evidence is inconsistent."
    assert payload == before

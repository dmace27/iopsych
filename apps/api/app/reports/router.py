"""Authenticated report endpoints with mandatory access audits."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.audit import audited, set_audit_entity
from app.auth.context import AuthorizationContext
from app.auth.dependencies import get_database_session, require_roles
from app.database.models import InternalUserRole
from app.reports.schemas import ReportCreateRequest, ReportResponse, SubmittedAssessmentResponse
from app.reports.service import ReportService

router = APIRouter(prefix="/v1/reports", tags=["reports"])
ReportContext = Annotated[
    AuthorizationContext,
    Depends(
        require_roles(
            InternalUserRole.RECRUITER,
            InternalUserRole.HIRING_MANAGER,
            InternalUserRole.ADMIN,
        )
    ),
]
DatabaseSession = Annotated[Session, Depends(get_database_session)]


@router.post("", response_model=ReportResponse, status_code=201)
@audited("alignment_report.generation_requested", "alignment_report")
def generate_report(
    payload: ReportCreateRequest,
    request: Request,
    context: ReportContext,
    session: DatabaseSession,
    response: Response,
) -> ReportResponse:
    """Generate or return the existing immutable report for the same inputs."""

    response.headers["Cache-Control"] = "no-store"
    report = ReportService(session, context).generate(payload)
    set_audit_entity(request, report.id)
    return report


@router.get("/{report_id}", response_model=ReportResponse)
@audited("alignment_report.read", "alignment_report", entity_id_path_parameter="report_id")
def read_report(
    report_id: UUID, context: ReportContext, session: DatabaseSession, response: Response
) -> ReportResponse:
    """Read a historical report with the exact stored matching explanation."""

    response.headers["Cache-Control"] = "no-store"
    return ReportService(session, context).read(report_id)


submission_router = APIRouter(tags=["reports"])


@submission_router.get(
    "/v1/roles/{role_id}/assessments", response_model=list[SubmittedAssessmentResponse]
)
@audited("assessment.submissions_read", "role", entity_id_path_parameter="role_id")
def list_submitted_assessments(
    role_id: UUID,
    context: ReportContext,
    session: DatabaseSession,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SubmittedAssessmentResponse]:
    """Find report inputs in one tenant-owned role, ordered by submission time."""

    response.headers["Cache-Control"] = "no-store"
    return ReportService(session, context).list_submissions(role_id, limit=limit, offset=offset)

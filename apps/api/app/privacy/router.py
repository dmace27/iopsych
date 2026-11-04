"""Administrator-only candidate data-rights and retention endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.audit import audited
from app.auth.context import AuthorizationContext
from app.auth.dependencies import get_database_session, require_roles
from app.database.models import InternalUserRole
from app.privacy.discovery import discover_assessments
from app.privacy.schemas import (
    CandidateDataExportResponse,
    CandidateDeletionResponse,
    PrivacyAuditEventResponse,
    PrivacyDiscoveryResponse,
    PrivacyStatusResponse,
    RetentionRunResponse,
)
from app.privacy.service import PrivacyService

candidate_router = APIRouter(prefix="/v1/candidates", tags=["candidate privacy"])
privacy_router = APIRouter(prefix="/v1/privacy", tags=["candidate privacy"])
AdminContext = Annotated[
    AuthorizationContext,
    Depends(require_roles(InternalUserRole.ADMIN)),
]
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _service(
    request: Request,
    session: Session,
    context: AuthorizationContext,
) -> PrivacyService:
    """Bind privacy work to the authenticated administrator's organization."""

    return PrivacyService(
        session=session,
        settings=request.app.state.privacy_settings,
        context=context,
    )


@candidate_router.post(
    "/{assessment_id}/export",
    response_model=CandidateDataExportResponse,
    response_model_exclude_unset=True,
)
@audited("candidate_data.exported", "assessment", entity_id_path_parameter="assessment_id")
def export_candidate_data(
    assessment_id: UUID,
    request: Request,
    response: Response,
    context: AdminContext,
    session: DatabaseSession,
) -> CandidateDataExportResponse:
    """Create a no-store JSON export for one tenant-owned assessment."""

    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="candidate-data-{assessment_id}.json"'
    )
    exported = _service(request, session, context).export(assessment_id)
    # Revalidate the projection so legacy clients retain their exact strict keyset.
    if request.headers.get("X-IOPsych-Notice-Snapshot") == "1":
        return CandidateDataExportResponse.model_validate(exported.model_dump())
    return CandidateDataExportResponse.model_validate(
        exported.model_dump(
            exclude={
                "consent": {
                    "notice_snapshot",
                    "notice_sha256",
                    "notice_snapshot_origin",
                    "notice_snapshot_recorded_at",
                    "presented_notice_sha256",
                    "notice_history",
                }
            }
        )
    )


@candidate_router.delete(
    "/{assessment_id}",
    response_model=CandidateDeletionResponse,
)
@audited(
    "candidate_data.deletion_requested",
    "assessment",
    entity_id_path_parameter="assessment_id",
)
def delete_candidate_data(
    assessment_id: UUID,
    request: Request,
    context: AdminContext,
    session: DatabaseSession,
) -> CandidateDeletionResponse:
    """Anonymize one candidate's data and derived reports idempotently."""

    return _service(request, session, context).anonymize(assessment_id)


@privacy_router.get("/status", response_model=PrivacyStatusResponse)
@audited("privacy.retention_status_read", "user")
def privacy_status(
    request: Request,
    context: AdminContext,
    session: DatabaseSession,
) -> PrivacyStatusResponse:
    """Return tenant retention counts and the next scheduled deadline."""

    return _service(request, session, context).status()


@privacy_router.get("/audit-events", response_model=list[PrivacyAuditEventResponse])
@audited("privacy.audit_history_read", "user")
def privacy_audit_events(
    request: Request,
    response: Response,
    context: AdminContext,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    entity_id: UUID | None = None,
    event_type: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    before: UUID | None = None,
    assessment_id: UUID | None = None,
) -> list[PrivacyAuditEventResponse]:
    """Read immutable organization audit history with bounded filtering."""

    response.headers["Cache-Control"] = "no-store"
    return _service(request, session, context).list_audit_events(
        limit=limit,
        offset=offset,
        entity_id=entity_id,
        event_type=event_type,
        before=before,
        assessment_id=assessment_id,
    )


@privacy_router.post("/retention/run", response_model=RetentionRunResponse)
@audited("privacy.retention_run", "user")
def run_retention(
    request: Request,
    context: AdminContext,
    session: DatabaseSession,
) -> RetentionRunResponse:
    """Run one bounded retention batch for the administrator's organization."""

    return _service(request, session, context).run_retention()


@privacy_router.get("/assessments", response_model=PrivacyDiscoveryResponse)
@audited("privacy.assessments_discovered", "user")
def privacy_assessments(
    response: Response,
    context: AdminContext,
    session: DatabaseSession,
    invitation_id: UUID | None = None,
    role_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=104)] = None,
) -> PrivacyDiscoveryResponse:
    """Find assessment IDs using exactly one tenant-owned invitation or role UUID."""

    response.headers["Cache-Control"] = "no-store"
    return discover_assessments(
        session,
        context,
        invitation_id=invitation_id,
        role_id=role_id,
        limit=limit,
        cursor=cursor,
    )

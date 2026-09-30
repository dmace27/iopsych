"""Authenticated recruiter routes and bearer-scoped candidate consent routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import audited, set_audit_entity
from app.auth.context import AuthorizationContext
from app.auth.dependencies import get_database_session, require_roles
from app.auth.errors import rate_limit_exceeded
from app.database.models import InternalUserRole
from app.invitations.rate_limit import InMemoryRateLimiter
from app.invitations.schemas import (
    CandidateInviteResponse,
    ConsentRequest,
    InvitationCreateRequest,
    InvitationResponse,
)
from app.invitations.service import CandidateInvitationService, InternalInvitationService
from app.invitations.tokens import opaque_rate_limit_key
from iopsych_contracts.assessment import AssessmentResponseSet

router = APIRouter(tags=["candidate invitations"])

InviteContext = Annotated[
    AuthorizationContext,
    Depends(require_roles(InternalUserRole.ADMIN, InternalUserRole.RECRUITER)),
]
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _internal_service(
    request: Request, session: Session, context: AuthorizationContext
) -> InternalInvitationService:
    """Build the internal service from application-owned secure dependencies."""

    return InternalInvitationService(
        session=session,
        context=context,
        settings=request.app.state.invitation_settings,
        token_codec=request.app.state.invite_token_codec,
        delivery=request.app.state.invitation_delivery,
    )


def _candidate_service(request: Request, session: Session) -> CandidateInvitationService:
    """Build the anonymous bearer-token service."""

    return CandidateInvitationService(
        session=session,
        settings=request.app.state.invitation_settings,
        token_codec=request.app.state.invite_token_codec,
        privacy_settings=request.app.state.privacy_settings,
    )


def _enforce_rate_limit(request: Request, key: str, *, internal: bool) -> None:
    """Apply configured limits without placing raw tokens or email in limiter keys."""

    limiter: InMemoryRateLimiter = request.app.state.invitation_rate_limiter
    settings = request.app.state.invitation_settings
    limit = settings.internal_rate_limit if internal else settings.candidate_rate_limit
    result = limiter.check(
        key,
        limit=limit,
        window_seconds=settings.rate_window_seconds,
    )
    if not result.allowed:
        raise rate_limit_exceeded(retry_after_seconds=result.retry_after_seconds)


@router.post(
    "/v1/roles/{role_id}/invites",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
@audited("assessment_invite.created", "assessment_invite")
async def create_invitation(
    role_id: UUID,
    payload: InvitationCreateRequest,
    request: Request,
    context: InviteContext,
    session: DatabaseSession,
) -> InvitationResponse:
    """Email a signed, expiring invitation for an approved profile."""

    _enforce_rate_limit(request, f"invite-create:{context.user_id}", internal=True)
    invite = _internal_service(request, session, context).create(role_id, payload)
    set_audit_entity(request, invite.id)
    return InvitationResponse.model_validate(invite)


@router.post(
    "/v1/roles/{role_id}/invites/{invite_id}/revoke",
    response_model=InvitationResponse,
)
@audited(
    "assessment_invite.revoked",
    "assessment_invite",
    entity_id_path_parameter="invite_id",
)
async def revoke_invitation(
    role_id: UUID,
    invite_id: UUID,
    request: Request,
    context: InviteContext,
    session: DatabaseSession,
) -> InvitationResponse:
    """Immediately invalidate a tenant-owned candidate invitation."""

    _enforce_rate_limit(request, f"invite-revoke:{context.user_id}", internal=True)
    invite = _internal_service(request, session, context).revoke(role_id, invite_id)
    return InvitationResponse.model_validate(invite)


@router.get(
    "/v1/candidate/invites/{token}",
    response_model=CandidateInviteResponse,
)
async def read_candidate_invitation(
    token: str,
    request: Request,
    session: DatabaseSession,
) -> CandidateInviteResponse:
    """Show consent information without exposing assessment questions or PII."""

    _candidate_rate_limit(request, token, action="read")
    return _candidate_service(request, session).read(token)


@router.post(
    "/v1/candidate/invites/{token}/consent",
    response_model=CandidateInviteResponse,
)
async def record_candidate_consent(
    token: str,
    payload: ConsentRequest,
    request: Request,
    session: DatabaseSession,
) -> CandidateInviteResponse:
    """Record explicit affirmative consent or decline without requiring an account."""

    _candidate_rate_limit(request, token, action="consent")
    return _candidate_service(request, session).record_consent(token, payload)


class SubmissionResponse(BaseModel):
    """Candidate-safe acknowledgement without scores or report labels."""

    assessment_id: UUID


@router.post(
    "/v1/candidate/invites/{token}/submit", response_model=SubmissionResponse, status_code=201
)
def submit_candidate_assessment(
    token: str, payload: AssessmentResponseSet, request: Request, session: DatabaseSession
) -> SubmissionResponse:
    """Persist a consented assessment with scores calculated on the server."""

    _candidate_rate_limit(request, token, action="submit")
    return SubmissionResponse(
        assessment_id=_candidate_service(request, session).submit(token, payload)
    )


def _candidate_rate_limit(request: Request, token: str, *, action: str) -> None:
    """Throttle by remote peer and opaque token digest to resist probing and abuse."""

    client_host = request.client.host if request.client is not None else "unknown"
    token_key = opaque_rate_limit_key(token)
    _enforce_rate_limit(
        request,
        f"candidate-{action}-ip:{client_host}",
        internal=False,
    )
    _enforce_rate_limit(
        request,
        f"candidate-{action}:{client_host}:{token_key}",
        internal=False,
    )

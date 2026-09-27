"""FastAPI routes for organization-scoped role and profile management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.audit import audited, set_audit_entity
from app.auth.context import AuthorizationContext
from app.auth.dependencies import get_database_session, require_roles
from app.database.models import InternalUserRole, Role
from app.roles.schemas import (
    RoleCreateRequest,
    RoleProfileCreateRequest,
    RoleProfileResponse,
    RoleProfileUpdateRequest,
    RoleResponse,
    RoleUpdateRequest,
)
from app.roles.service import RoleProfileService

router = APIRouter(prefix="/v1/roles", tags=["roles"])

ReadContext = Annotated[
    AuthorizationContext,
    Depends(
        require_roles(
            InternalUserRole.ADMIN,
            InternalUserRole.RECRUITER,
            InternalUserRole.HIRING_MANAGER,
        )
    ),
]
EditContext = Annotated[
    AuthorizationContext,
    Depends(require_roles(InternalUserRole.ADMIN, InternalUserRole.RECRUITER)),
]
ApprovalContext = Annotated[
    AuthorizationContext,
    Depends(require_roles(InternalUserRole.HIRING_MANAGER)),
]
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _service(session: Session, context: AuthorizationContext) -> RoleProfileService:
    """Construct the transaction service from request-scoped dependencies."""

    return RoleProfileService(session, context)


@router.get("", response_model=list[RoleResponse])
@audited("role.listed", "user")
async def list_roles(context: ReadContext, session: DatabaseSession) -> list[RoleResponse]:
    """List roles visible to the authenticated organization."""

    return _service(session, context).list_roles()


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
@audited("role.created", "role")
async def create_role(
    payload: RoleCreateRequest,
    request: Request,
    context: EditContext,
    session: DatabaseSession,
) -> Role:
    """Create a draft role as a recruiter or explicit administrator."""

    role = _service(session, context).create_role(payload)
    set_audit_entity(request, role.id)
    return role


@router.get("/{role_id}", response_model=RoleResponse)
@audited("role.read", "role", entity_id_path_parameter="role_id")
async def get_role(role_id: UUID, context: ReadContext, session: DatabaseSession) -> Role:
    """Read one role without exposing cross-organization existence."""

    return _service(session, context).get_role(role_id)


@router.patch("/{role_id}", response_model=RoleResponse)
@audited("role.updated", "role", entity_id_path_parameter="role_id")
async def update_role(
    role_id: UUID,
    payload: RoleUpdateRequest,
    context: EditContext,
    session: DatabaseSession,
) -> Role:
    """Update editable role metadata as a recruiter or administrator."""

    return _service(session, context).update_role(role_id, payload)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
@audited("role.archived", "role", entity_id_path_parameter="role_id")
async def archive_role(
    role_id: UUID,
    context: EditContext,
    session: DatabaseSession,
) -> Response:
    """Archive a role while preserving profiles and audit history."""

    _service(session, context).archive_role(role_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{role_id}/profiles",
    response_model=RoleProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
@audited("role_profile.created", "role_profile")
async def create_profile(
    role_id: UUID,
    payload: RoleProfileCreateRequest,
    request: Request,
    context: EditContext,
    session: DatabaseSession,
) -> RoleProfileResponse:
    """Create a complete draft profile for a tenant-owned role."""

    profile = _service(session, context).create_profile(role_id, payload)
    set_audit_entity(request, profile.id)
    return profile


@router.get("/{role_id}/profiles", response_model=list[RoleProfileResponse])
@audited("role_profile.listed", "role", entity_id_path_parameter="role_id")
async def list_profiles(
    role_id: UUID,
    context: ReadContext,
    session: DatabaseSession,
) -> list[RoleProfileResponse]:
    """List complete immutable profile history in ascending version order."""

    return _service(session, context).list_profiles(role_id)


@router.get("/{role_id}/profiles/{profile_id}", response_model=RoleProfileResponse)
@audited("role_profile.read", "role_profile", entity_id_path_parameter="profile_id")
async def get_profile(
    role_id: UUID,
    profile_id: UUID,
    context: ReadContext,
    session: DatabaseSession,
) -> RoleProfileResponse:
    """Read an immutable profile version and all construct ratings."""

    return _service(session, context).get_profile(role_id, profile_id)


@router.patch("/{role_id}/profiles/{profile_id}", response_model=RoleProfileResponse)
@audited("role_profile.version_created", "role_profile")
async def revise_profile(
    role_id: UUID,
    profile_id: UUID,
    payload: RoleProfileUpdateRequest,
    request: Request,
    context: EditContext,
    session: DatabaseSession,
) -> RoleProfileResponse:
    """Create a new draft version from edits to the current draft."""

    profile = _service(session, context).revise_profile(role_id, profile_id, payload)
    set_audit_entity(request, profile.id)
    return profile


@router.post(
    "/{role_id}/profiles/{profile_id}/approve",
    response_model=RoleProfileResponse,
)
@audited("role_profile.approved", "role_profile", entity_id_path_parameter="profile_id")
async def approve_profile(
    role_id: UUID,
    profile_id: UUID,
    context: ApprovalContext,
    session: DatabaseSession,
) -> RoleProfileResponse:
    """Approve the latest draft as a hiring manager and activate the role."""

    return _service(session, context).approve_profile(role_id, profile_id)

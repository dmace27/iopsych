"""Tenant-scoped administrator provisioning and account lifecycle endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import audited, set_audit_entity
from app.auth.context import AuthorizationContext
from app.auth.dependencies import get_database_session, require_roles
from app.auth.errors import organization_resource_not_found, permission_denied, resource_conflict
from app.database.models import InternalUserRole, Organization, User

router = APIRouter(prefix="/v1/users", tags=["accounts"])
Admin = Annotated[AuthorizationContext, Depends(require_roles(InternalUserRole.ADMIN))]
Database = Annotated[Session, Depends(get_database_session)]


class UserInput(BaseModel):
    """Bind a known provider subject explicitly; never identify users by email."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    auth_subject: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    name: str = Field(min_length=1, max_length=160)
    role: InternalUserRole


class UserUpdate(BaseModel):
    """Require an explicit permission and activation decision for each update."""

    model_config = ConfigDict(extra="forbid")
    role: InternalUserRole
    is_active: bool


class UserResponse(UserInput):
    """Administrator-only account details, with no credentials."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    is_active: bool


def _lock_administrator(session: Session, context: AuthorizationContext) -> None:
    """Serialize tenant account changes and recheck the actor after waiting.

    This prevents concurrent administrators from disabling/demoting each other
    using stale authorization. Self-demotion/deactivation is prohibited below.
    """

    session.execute(
        select(Organization)
        .where(Organization.id == context.organization.organization_id)
        .with_for_update()
    ).scalar_one()
    actor = session.get(User, context.user_id, populate_existing=True)
    assert actor is not None
    if not actor.is_active or actor.role != InternalUserRole.ADMIN:
        raise permission_denied()


@router.get("", response_model=list[UserResponse])
@audited("internal_user.list", "user")
def list_users(
    context: Admin,
    session: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserResponse]:
    """Return a bounded, stable page of accounts from the active tenant."""

    users = session.scalars(
        select(User)
        .where(User.organization_id == context.organization.organization_id)
        .order_by(User.created_at, User.id)
        .limit(limit)
        .offset(offset)
    )
    return [UserResponse.model_validate(user) for user in users]


@router.post("", response_model=UserResponse, status_code=201)
@audited("internal_user.provision", "user")
def create_user(
    payload: UserInput, request: Request, context: Admin, session: Database
) -> UserResponse:
    """Provision an existing provider account within the administrator's tenant."""

    _lock_administrator(session, context)
    user = User(organization_id=context.organization.organization_id, **payload.model_dump())
    try:
        session.add(user)
        session.flush()
    except IntegrityError as exc:
        # This endpoint has staged no other mutations. Roll back its failed
        # insert, then let middleware persist the rejected-action audit in a new
        # transaction. Avoid savepoints: SQLite's legacy driver may commit a
        # top-level savepoint before the mandatory audit is committed.
        session.rollback()
        raise resource_conflict(
            code="account_conflict",
            detail="This account cannot be provisioned. Check the subject and email.",
        ) from exc
    set_audit_entity(request, user.id)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
@audited("internal_user.update", "user", entity_id_path_parameter="user_id")
def update_user(
    user_id: UUID, payload: UserUpdate, context: Admin, session: Database
) -> UserResponse:
    """Change permissions or disable access for another tenant-owned user."""

    _lock_administrator(session, context)
    user = session.scalar(
        select(User).where(
            User.id == user_id, User.organization_id == context.organization.organization_id
        )
    )
    if user is None:
        raise organization_resource_not_found()
    if user.id == context.user_id:
        raise resource_conflict(
            code="self_account_change", detail="Ask another administrator to change your account."
        )
    user.role = payload.role
    user.is_active = payload.is_active
    session.flush()
    return UserResponse.model_validate(user)

"""Tenant-scoped existing-account discovery and serialized access changes."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounts.schemas import AccountListResponse, AccountResponse, AccountUpdateRequest
from app.auth.context import AuthorizationContext
from app.auth.errors import (
    authentication_required,
    organization_resource_not_found,
    permission_denied,
    resource_conflict,
)
from app.database.models import AuditEvent, InternalUserRole, Organization, User
from app.database.session import commit_or_flush


def discover_accounts(
    session: Session,
    context: AuthorizationContext,
    *,
    limit: int = 25,
    after: UUID | None = None,
) -> AccountListResponse:
    """Return a bounded tenant-only UUID keyset page."""

    if context.role != InternalUserRole.ADMIN:
        raise permission_denied()
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    tenant = context.organization.organization_id
    statement = select(User).where(User.organization_id == tenant)
    if after is not None:
        anchor = session.scalar(statement.where(User.id == after))
        if anchor is None:
            raise organization_resource_not_found()
        statement = statement.where(User.id > after)
    rows = list(session.scalars(statement.order_by(User.id).limit(limit + 1)))
    return AccountListResponse(
        items=[AccountResponse.model_validate(row) for row in rows[:limit]],
        next_cursor=rows[limit - 1].id if len(rows) > limit else None,
    )


def update_account(
    session: Session,
    context: AuthorizationContext,
    user_id: UUID,
    update: AccountUpdateRequest,
) -> AccountResponse:
    """Lock tenant before users and reauthorize the actor after acquiring the lock."""

    tenant = context.organization.organization_id
    organization = session.scalar(
        select(Organization).where(Organization.id == tenant).with_for_update()
    )
    if organization is None:
        raise authentication_required()
    actor = session.scalar(
        select(User)
        .where(User.id == context.user_id, User.organization_id == tenant)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if actor is None or not actor.is_active:
        raise authentication_required()
    if actor.role != InternalUserRole.ADMIN:
        raise permission_denied()
    target = session.scalar(
        select(User)
        .where(User.id == user_id, User.organization_id == tenant)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if target is None:
        raise organization_resource_not_found()
    if target.id == actor.id:
        raise permission_denied()
    if target.version != update.expected_version:
        raise resource_conflict(
            code="account_version_conflict", detail="Refresh the account state."
        )
    new_role = update.role if update.role is not None else target.role
    new_active = update.is_active if update.is_active is not None else target.is_active
    if target.role == new_role and target.is_active == new_active:
        return AccountResponse.model_validate(target)
    if (
        target.role == InternalUserRole.ADMIN
        and target.is_active
        and (new_role != InternalUserRole.ADMIN or not new_active)
    ):
        count = session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.organization_id == tenant,
                User.role == InternalUserRole.ADMIN,
                User.is_active.is_(True),
            )
        )
        if count is None or count <= 1:
            raise resource_conflict(
                code="last_active_admin", detail="An active administrator must remain."
            )
    before = {"role": target.role.value, "is_active": target.is_active, "version": target.version}
    target.role = new_role
    target.is_active = new_active
    target.version += 1
    session.add(
        AuditEvent(
            organization_id=tenant,
            actor_id=actor.id,
            event_type="account.access_changed",
            entity_type="user",
            entity_id=target.id,
            metadata_json={
                "before": before,
                "after": {
                    "role": target.role.value,
                    "is_active": target.is_active,
                    "version": target.version,
                },
            },
        )
    )
    commit_or_flush(session)
    return AccountResponse.model_validate(target)

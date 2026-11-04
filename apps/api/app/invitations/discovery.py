"""Bounded invitation history independent of delivery and signing configuration."""

from __future__ import annotations

import base64
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth.context import AuthorizationContext
from app.auth.errors import organization_resource_not_found, resource_validation_failed
from app.database.models import AssessmentInvite, Role, RoleProfile
from app.database.repositories import OrganizationDataAccess
from app.invitations.schemas import InvitationListResponse, InvitationResponse

# Version byte + three UUIDs + a fixed-width UTC timestamp, base64url without padding.
_CURSOR_SHAPE = re.compile(r"[A-Za-z0-9_-]{102}")


def _timestamp(value: datetime) -> bytes:
    """Normalize SQLite naive UTC and PostgreSQL aware timestamps identically."""

    return (
        (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
        .encode("ascii")
    )


def _encode_cursor(organization_id: UUID, role_id: UUID, invite: AssessmentInvite) -> str:
    payload = (
        b"\x01"
        + organization_id.bytes
        + role_id.bytes
        + invite.id.bytes
        + _timestamp(invite.created_at)
    )
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def discover_invitations(
    session: Session,
    context: AuthorizationContext,
    role_id: UUID,
    *,
    limit: int,
    cursor: str | None,
) -> InvitationListResponse:
    """Read one keyset page; validate cursor anchors against current tenant data.

    Cursors are opaque references, not credentials. Database validation prevents
    fabricated ordering keys without introducing a delivery-key dependency.
    A deleted anchor invalidates its cursor; clients can restart from page one.
    """

    organization_id = context.organization.organization_id
    if OrganizationDataAccess(session, organization_id).get_role(role_id) is None:
        raise organization_resource_not_found()

    statement = (
        select(AssessmentInvite)
        .join(RoleProfile, RoleProfile.id == AssessmentInvite.role_profile_id)
        .join(Role, Role.id == RoleProfile.role_id)
        .where(Role.organization_id == organization_id, Role.id == role_id)
    )
    if cursor is not None:
        invalid = resource_validation_failed(
            code="invalid_invitation_cursor", detail="The invitation cursor is invalid."
        )
        if _CURSOR_SHAPE.fullmatch(cursor) is None:
            raise invalid
        payload = base64.b64decode(cursor + "==", altchars=b"-_", validate=True)
        if (
            payload[:1] != b"\x01"
            or payload[1:17] != organization_id.bytes
            or payload[17:33] != role_id.bytes
        ):
            raise invalid
        anchor = session.scalar(statement.where(AssessmentInvite.id == UUID(bytes=payload[33:49])))
        if anchor is None or _encode_cursor(organization_id, role_id, anchor) != cursor:
            raise invalid
        statement = statement.where(
            or_(
                AssessmentInvite.created_at < anchor.created_at,
                and_(
                    AssessmentInvite.created_at == anchor.created_at,
                    AssessmentInvite.id < anchor.id,
                ),
            )
        )

    rows = session.scalars(
        statement.order_by(AssessmentInvite.created_at.desc(), AssessmentInvite.id.desc()).limit(
            limit + 1
        )
    ).all()
    items = rows[:limit]
    return InvitationListResponse(
        items=[InvitationResponse.model_validate(invite) for invite in items],
        next_cursor=(
            _encode_cursor(organization_id, role_id, items[-1]) if len(rows) > limit else None
        ),
    )

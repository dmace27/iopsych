"""Minimal, tenant-scoped assessment discovery for privacy administrators."""

import base64
import re
from datetime import UTC
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth.context import AuthorizationContext
from app.auth.errors import resource_validation_failed
from app.database.models import Assessment, AssessmentInvite, Role, RoleProfile
from app.privacy.schemas import PrivacyAssessmentResponse, PrivacyDiscoveryResponse

# Version + selector kind + tenant/filter/anchor UUIDs + fixed-width UTC timestamp.
_CURSOR_SHAPE = re.compile(r"[A-Za-z0-9_-]{103}")


def _encode_cursor(
    organization_id: UUID, selector: UUID, kind: bytes, item: PrivacyAssessmentResponse
) -> str:
    created_at = item.created_at
    timestamp = (
        (
            created_at.replace(tzinfo=UTC)
            if created_at.tzinfo is None
            else created_at.astimezone(UTC)
        )
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    payload = (
        b"\x01"
        + kind
        + organization_id.bytes
        + selector.bytes
        + item.assessment_id.bytes
        + timestamp.encode("ascii")
    )
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def discover_assessments(
    session: Session,
    context: AuthorizationContext,
    *,
    invitation_id: UUID | None,
    role_id: UUID | None,
    limit: int,
    cursor: str | None,
) -> PrivacyDiscoveryResponse:
    """Select only ID/timestamps; at most one anchor and limit+1 result rows.

    The cursor is a reference, not authorization. Revalidate its canonical bytes,
    scope and current anchor on every request. Deleted anchors require restarting.
    """
    if (invitation_id is None) == (role_id is None) or not 1 <= limit <= 50:
        raise resource_validation_failed(
            code="invalid_privacy_lookup",
            detail="Supply exactly one invitation_id or role_id and a limit from 1 to 50.",
        )
    selector = invitation_id if invitation_id is not None else role_id
    assert selector is not None
    kind = b"i" if invitation_id is not None else b"r"
    organization_id = context.organization.organization_id
    statement = (
        select(
            Assessment.id.label("assessment_id"),
            Assessment.created_at,
            Assessment.submitted_at,
            Assessment.retention_expires_at,
            Assessment.anonymized_at,
        )
        .join(AssessmentInvite, AssessmentInvite.id == Assessment.invite_id)
        .join(RoleProfile, RoleProfile.id == AssessmentInvite.role_profile_id)
        .join(Role, Role.id == RoleProfile.role_id)
        .where(
            Role.organization_id == organization_id,
            AssessmentInvite.id == selector if invitation_id is not None else Role.id == selector,
        )
    )
    if cursor is not None:
        invalid = resource_validation_failed(
            code="invalid_privacy_cursor", detail="The privacy cursor is invalid."
        )
        if _CURSOR_SHAPE.fullmatch(cursor) is None:
            raise invalid
        payload = base64.b64decode(cursor + "=", altchars=b"-_", validate=True)
        if payload[:34] != b"\x01" + kind + organization_id.bytes + selector.bytes:
            raise invalid
        anchor_row = (
            session.execute(statement.where(Assessment.id == UUID(bytes=payload[34:50])))
            .mappings()
            .one_or_none()
        )
        if anchor_row is None:
            raise invalid
        anchor = PrivacyAssessmentResponse.model_validate(dict(anchor_row))
        if _encode_cursor(organization_id, selector, kind, anchor) != cursor:
            raise invalid
        statement = statement.where(
            or_(
                Assessment.created_at < anchor.created_at,
                and_(
                    Assessment.created_at == anchor.created_at, Assessment.id < anchor.assessment_id
                ),
            )
        )
    rows = (
        session.execute(
            statement.order_by(Assessment.created_at.desc(), Assessment.id.desc()).limit(limit + 1)
        )
        .mappings()
        .all()
    )
    items = [PrivacyAssessmentResponse.model_validate(dict(row)) for row in rows[:limit]]
    return PrivacyDiscoveryResponse(
        items=items,
        next_cursor=(
            _encode_cursor(organization_id, selector, kind, items[-1])
            if len(rows) > limit
            else None
        ),
    )

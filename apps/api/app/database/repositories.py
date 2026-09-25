"""Organization-scoped database reads.

Every internal read enters through an organization context. Tables that do
not duplicate ``organization_id`` are scoped by joining back to ``roles``.
This keeps the section 9 model normalized while preventing ID-based tenant
boundary bypasses.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    AuditEvent,
    Role,
    RoleConstructRating,
    RoleProfile,
    User,
)
from iopsych_contracts import ConstructKey


class OrganizationDataAccess:
    """Read data visible to exactly one organization."""

    def __init__(self, session: Session, organization_id: UUID) -> None:
        self._session = session
        self.organization_id = organization_id

    def list_users(self) -> list[User]:
        """Return users in the active organization."""

        statement = select(User).where(User.organization_id == self.organization_id)
        return list(self._session.scalars(statement))

    def get_user(self, user_id: UUID) -> User | None:
        """Read a user only when its tenant matches the active tenant."""

        statement = select(User).where(
            User.id == user_id,
            User.organization_id == self.organization_id,
        )
        return self._session.scalar(statement)

    def list_roles(self) -> list[Role]:
        """Return roles in the active organization."""

        statement = select(Role).where(Role.organization_id == self.organization_id)
        return list(self._session.scalars(statement))

    def get_role(self, role_id: UUID) -> Role | None:
        """Read a role only when its tenant matches the active tenant."""

        statement = select(Role).where(
            Role.id == role_id,
            Role.organization_id == self.organization_id,
        )
        return self._session.scalar(statement)

    def get_role_profile(self, profile_id: UUID) -> RoleProfile | None:
        """Read a profile through its owning role's tenant boundary."""

        statement = (
            select(RoleProfile)
            .join(Role, Role.id == RoleProfile.role_id)
            .where(
                RoleProfile.id == profile_id,
                Role.organization_id == self.organization_id,
            )
        )
        return self._session.scalar(statement)

    def get_role_construct_rating(
        self, profile_id: UUID, construct_key: ConstructKey
    ) -> RoleConstructRating | None:
        """Read a construct rating through profile and role ownership."""

        statement = (
            select(RoleConstructRating)
            .join(RoleProfile, RoleProfile.id == RoleConstructRating.profile_id)
            .join(Role, Role.id == RoleProfile.role_id)
            .where(
                RoleConstructRating.profile_id == profile_id,
                RoleConstructRating.construct_key == construct_key,
                Role.organization_id == self.organization_id,
            )
        )
        return self._session.scalar(statement)

    def list_audit_events(self) -> list[AuditEvent]:
        """Return audit events in the active organization, oldest first."""

        statement = (
            select(AuditEvent)
            .where(AuditEvent.organization_id == self.organization_id)
            .order_by(AuditEvent.created_at, AuditEvent.id)
        )
        return list(self._session.scalars(statement))

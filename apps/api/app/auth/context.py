"""Request-local identity and organization-isolation value objects."""

from dataclasses import dataclass
from uuid import UUID

from app.auth.errors import organization_resource_not_found
from app.database.models import InternalUserRole


@dataclass(frozen=True)
class OrganizationScope:
    """Tenant boundary inherited from verified identity and database state."""

    organization_id: UUID

    def require_matches(self, resource_organization_id: UUID) -> None:
        """Reject cross-tenant resources without confirming their existence."""

        if resource_organization_id != self.organization_id:
            raise organization_resource_not_found()


@dataclass(frozen=True)
class AuthorizationContext:
    """Database-authoritative internal user identity for one request."""

    user_id: UUID
    organization: OrganizationScope
    email: str
    name: str
    role: InternalUserRole

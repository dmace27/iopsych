"""Existing-account administration contracts."""

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.database.models import InternalUserRole


class AccountResponse(BaseModel):
    """Tenant-visible account details without provider identifiers."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    email: str
    name: str
    role: InternalUserRole
    is_active: bool
    version: int = Field(ge=1)


class AccountListResponse(BaseModel):
    """Bounded keyset page of accounts."""

    items: list[AccountResponse]
    next_cursor: UUID | None


class AccountUpdateRequest(BaseModel):
    """An optimistic-concurrency guarded role or activation update."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1, strict=True)
    role: InternalUserRole | None = None
    is_active: StrictBool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        """Reject empty updates and explicit null mutation fields."""

        changed = self.model_fields_set - {"expected_version"}
        if not changed or any(getattr(self, field) is None for field in changed):
            raise ValueError("Provide a non-null role or is_active change.")
        return self

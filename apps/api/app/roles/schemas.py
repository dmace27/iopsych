"""Strict request and response contracts for roles and profile versions."""

from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.database.models import RoleProfileStatus, RoleStatus
from iopsych_contracts import CONSTRUCT_KEYS, RoleConstructRating

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
JobDescriptionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100_000),
]


class RoleCreateRequest(BaseModel):
    """Validated fields required to create an organization-owned role."""

    model_config = ConfigDict(extra="forbid")

    title: ShortText
    department: ShortText
    location: ShortText
    job_description: JobDescriptionText


class RoleUpdateRequest(BaseModel):
    """A non-empty partial update to editable role metadata."""

    model_config = ConfigDict(extra="forbid")

    title: ShortText | None = None
    department: ShortText | None = None
    location: ShortText | None = None
    job_description: JobDescriptionText | None = None

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> Self:
        """Reject empty PATCH documents and explicit null values."""

        supplied = self.model_fields_set
        if not supplied:
            raise ValueError("at least one role field must be supplied")
        if any(getattr(self, field_name) is None for field_name in supplied):
            raise ValueError("role fields cannot be null")
        return self


class RoleResponse(BaseModel):
    """Organization-scoped role metadata returned to internal users."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    title: str
    department: str
    location: str
    job_description: str
    status: RoleStatus
    created_at: datetime


class RoleProfileCreateRequest(BaseModel):
    """A complete first or replacement draft containing all six constructs."""

    model_config = ConfigDict(extra="forbid")

    constructs: Annotated[
        list[RoleConstructRating],
        Field(min_length=len(CONSTRUCT_KEYS), max_length=len(CONSTRUCT_KEYS)),
    ]

    @model_validator(mode="after")
    def require_each_construct_once(self) -> Self:
        """Require exactly one rating for every version-one construct."""

        keys = [construct.key for construct in self.constructs]
        if len(set(keys)) != len(keys) or set(keys) != set(CONSTRUCT_KEYS):
            raise ValueError("constructs must contain each version 1 construct exactly once")
        return self


class RoleProfileUpdateRequest(BaseModel):
    """One or more construct changes used to create the next draft version."""

    model_config = ConfigDict(extra="forbid")

    constructs: Annotated[
        list[RoleConstructRating], Field(min_length=1, max_length=len(CONSTRUCT_KEYS))
    ]

    @model_validator(mode="after")
    def reject_duplicate_constructs(self) -> Self:
        """Prevent ambiguous repeated updates for one construct."""

        keys = [construct.key for construct in self.constructs]
        if len(set(keys)) != len(keys):
            raise ValueError("construct updates must use unique keys")
        return self


class RoleProfileResponse(BaseModel):
    """One immutable, fully expanded role-profile snapshot."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    role_id: UUID
    version: int
    status: RoleProfileStatus
    created_by: UUID
    approved_by: UUID | None
    approved_at: datetime | None
    created_at: datetime
    constructs: list[RoleConstructRating]

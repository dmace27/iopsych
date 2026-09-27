"""Strict API contracts for internal invitations and candidate consent."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.database.models import AssessmentInviteStatus, ConsentDecision

EmailText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)]
_EMAIL_SHAPE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class InvitationCreateRequest(BaseModel):
    """Fields an internal recruiter may supply when issuing an invitation."""

    model_config = ConfigDict(extra="forbid")

    role_profile_id: UUID
    email: EmailText
    expires_in_hours: int | None = Field(default=None, ge=1, le=720)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Apply a deliberately conservative mailbox shape check without DNS lookup."""

        if _EMAIL_SHAPE.fullmatch(value) is None:
            raise ValueError("email must be a valid address")
        local, domain = value.split("@")
        return f"{local}@{domain.casefold()}"


class InvitationResponse(BaseModel):
    """Internal invitation state; the bearer token is intentionally absent."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role_profile_id: UUID
    email: str
    expires_at: datetime
    status: AssessmentInviteStatus
    sent_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ConsentNotice(BaseModel):
    """Versioned plain-language content shown before any assessment questions."""

    model_config = ConfigDict(extra="forbid")

    version: str
    purpose: str
    data_use: str
    retention: str
    accommodation_contact_email: str
    privacy_contact_email: str
    decline_without_penalty: bool = True


class CandidateInviteResponse(BaseModel):
    """Token-scoped landing state with no candidate email or assessment data."""

    model_config = ConfigDict(extra="forbid")

    invitation_id: UUID
    organization_name: str
    role_title: str
    expires_at: datetime
    status: AssessmentInviteStatus
    consent_notice: ConsentNotice
    decision: ConsentDecision | None
    decision_recorded_at: datetime | None
    can_start_assessment: bool


class ConsentRequest(BaseModel):
    """An explicit affirmative consent or decline; omission is never consent."""

    model_config = ConfigDict(extra="forbid")

    decision: ConsentDecision

"""Strict API contracts for internal invitations and candidate consent."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.database.models import AssessmentInviteStatus, ConsentDecision, InvitationDeliveryStatus
from app.invitations.recovery import DeliveryState

EmailText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)]
NoticeHistory = Literal["not_recorded", "digest_recorded", "legacy_unverified", "legacy_unknown"]
NoticeDigest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$", strict=True)]
_EMAIL_SHAPE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class InvitationCreateRequest(BaseModel):
    """Fields an internal recruiter may supply when issuing an invitation."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID | None = None
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
    delivery_state: DeliveryState | None = None
    sent_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class InvitationListResponse(BaseModel):
    """A bounded page of existing internal invitation representations."""

    items: list[InvitationResponse]
    next_cursor: str | None


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
    notice_sha256: str | None = None
    notice_history: NoticeHistory = "not_recorded"
    decision: ConsentDecision | None
    decision_recorded_at: datetime | None
    can_start_assessment: bool
    assessment_id: UUID | None = None


class ConsentRequest(BaseModel):
    """An explicit affirmative consent or decline; omission is never consent."""

    model_config = ConfigDict(extra="forbid")

    decision: ConsentDecision
    presented_notice_sha256: NoticeDigest | None = None


class InvitationReissueRequest(BaseModel):
    """A new explicit issuance action; retries must keep the same request identifier."""

    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    expires_in_hours: int | None = Field(default=None, ge=1, le=720)


class InvitationDeliveryResponse(BaseModel):
    """Safe delivery state; no encrypted payload or provider credentials are exposed."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    invite_id: UUID
    status: InvitationDeliveryStatus
    attempt_count: int
    next_attempt_at: datetime
    retry_until: datetime
    last_error_code: str | None

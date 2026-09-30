"""Strict response contracts for candidate data-rights administration."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import AssessmentInviteStatus, ConsentDecision


class ExportOrganization(BaseModel):
    """Organization and role context included in a candidate export."""

    name: str
    role_title: str
    role_profile_version: int


class ExportInvitation(BaseModel):
    """Candidate-identifying invitation fields included in an export."""

    id: UUID
    email: str
    status: AssessmentInviteStatus
    created_at: datetime
    sent_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None


class ExportConsent(BaseModel):
    """The candidate's recorded consent decision and notice version."""

    id: UUID
    decision: ConsentDecision
    notice_version: str
    recorded_at: datetime


class ExportAssessment(BaseModel):
    """Submitted source, response, and deterministic score snapshots."""

    id: UUID
    created_at: datetime
    submitted_at: datetime | None
    retention_expires_at: datetime | None
    definition: dict[str, Any]
    responses: dict[str, Any]
    scores: dict[str, Any]


class ExportReport(BaseModel):
    """One derived report snapshot included before anonymization."""

    id: UUID
    generated_at: datetime
    algorithm_version: str
    result: dict[str, Any]


class ExportActivity(BaseModel):
    """Candidate-scoped processing history without internal actor identity."""

    event_type: str
    entity_type: str
    entity_id: UUID
    occurred_at: datetime
    details: dict[str, Any]


class CandidateDataExportResponse(BaseModel):
    """Portable JSON export of all retained candidate MVP data."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    organization: ExportOrganization
    invitation: ExportInvitation
    consent: ExportConsent
    assessment: ExportAssessment
    reports: list[ExportReport]
    activity: list[ExportActivity]


class CandidateDeletionResponse(BaseModel):
    """Idempotent confirmation that candidate data was anonymized."""

    assessment_id: UUID
    anonymized_at: datetime
    already_anonymized: bool
    reports_deleted: int = Field(ge=0)


class PrivacyStatusResponse(BaseModel):
    """Tenant-scoped retention posture shown to administrators."""

    retention_days: int
    total_assessments: int = Field(ge=0)
    active_assessments: int = Field(ge=0)
    anonymized_assessments: int = Field(ge=0)
    due_assessments: int = Field(ge=0)
    next_retention_at: datetime | None


class PrivacyAuditEventResponse(BaseModel):
    """Safe immutable audit row for the admin privacy history."""

    id: UUID
    actor_id: UUID | None
    event_type: str
    entity_type: str
    entity_id: UUID
    occurred_at: datetime
    details: dict[str, Any]


class RetentionRunResponse(BaseModel):
    """Bounded retention-job result for one organization or system run."""

    completed_at: datetime
    anonymized_assessment_ids: list[UUID]

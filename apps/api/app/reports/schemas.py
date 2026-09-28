"""Version-preserving API envelopes around the shared matching contract."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from iopsych_contracts.matching import MatchingResult


class ReportCreateRequest(BaseModel):
    """Only identifiers are accepted; clients cannot supply scores or approval."""

    model_config = ConfigDict(extra="forbid")
    assessment_id: UUID
    role_profile_id: UUID


class SubmittedAssessmentResponse(BaseModel):
    """Internal source discovery without scores, labels, or rankings."""

    assessment_id: UUID
    invitation_id: UUID
    candidate_email: str
    role_profile_id: UUID
    role_profile_version: int
    submitted_at: datetime | None
    report_id: UUID | None


class ReportResponse(BaseModel):
    """Immutable result with reproducible source versions and evidence."""

    id: UUID
    assessment_id: UUID
    role_profile_id: UUID
    role_profile_version: int
    generated_at: datetime
    result: MatchingResult
    usage_warning: str = (
        "For human-reviewed interview preparation only. This report must not be used "
        "to rank candidates or make automated employment decisions."
    )

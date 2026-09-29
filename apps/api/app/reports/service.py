"""Tenant-scoped generation from submitted, consented, approved inputs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import AuthorizationContext
from app.auth.errors import organization_resource_not_found, resource_conflict
from app.database.models import (
    AlignmentReport,
    AlignmentReportItem,
    Assessment,
    AssessmentInvite,
    AuditEvent,
    CandidateConsent,
    ConsentDecision,
    Role,
    RoleConstructRating,
    RoleProfile,
    RoleProfileStatus,
)
from app.database.session import commit_or_flush
from app.reports.schemas import ReportCreateRequest, ReportResponse, SubmittedAssessmentResponse
from iopsych_contracts import RoleConstructRating as RatingContract
from iopsych_contracts.assessment import AssessmentScoreResult
from iopsych_contracts.matching import (
    MATCHING_ALGORITHM_VERSION,
    MatchingResult,
    MatchingRoleProfile,
    match_role_profile,
)


class ReportService:
    """Generate one stored result per assessment/profile/algorithm combination."""

    def __init__(self, session: Session, context: AuthorizationContext) -> None:
        self.session = session
        self.context = context

    def generate(self, payload: ReportCreateRequest) -> ReportResponse:
        """Lock the submission to serialize duplicate generation requests."""

        assessment = self.session.scalar(
            select(Assessment)
            .join(AssessmentInvite, AssessmentInvite.id == Assessment.invite_id)
            .join(RoleProfile, RoleProfile.id == AssessmentInvite.role_profile_id)
            .join(Role, Role.id == RoleProfile.role_id)
            .where(
                Assessment.id == payload.assessment_id,
                Role.organization_id == self.context.organization.organization_id,
            )
            .with_for_update(of=Assessment)
        )
        profile = self.session.scalar(
            select(RoleProfile)
            .join(Role, Role.id == RoleProfile.role_id)
            .where(
                RoleProfile.id == payload.role_profile_id,
                Role.organization_id == self.context.organization.organization_id,
            )
            .with_for_update(of=RoleProfile)
        )
        if assessment is None or profile is None:
            raise organization_resource_not_found()
        invite = self.session.get(AssessmentInvite, assessment.invite_id)
        consent = self.session.get(CandidateConsent, assessment.consent_id)
        if invite is None or invite.role_profile_id != profile.id:
            raise resource_conflict(
                code="report_profile_mismatch",
                detail="Reports must use the invitation's profile version.",
            )
        if assessment.submitted_at is None:
            raise resource_conflict(
                code="assessment_not_submitted", detail="Reports require a submitted assessment."
            )
        if (
            consent is None
            or consent.invite_id != invite.id
            or consent.decision != ConsentDecision.CONSENT
        ):
            raise resource_conflict(
                code="candidate_consent_required",
                detail="Reports require affirmative candidate consent.",
            )
        if (
            profile.status not in (RoleProfileStatus.APPROVED, RoleProfileStatus.SUPERSEDED)
            or profile.approved_at is None
            or profile.approved_by is None
        ):
            raise resource_conflict(
                code="profile_not_approved",
                detail="Reports require a human-approved profile version.",
            )
        report = self.session.scalar(
            select(AlignmentReport).where(
                AlignmentReport.assessment_id == assessment.id,
                AlignmentReport.role_profile_id == profile.id,
                AlignmentReport.algorithm_version == MATCHING_ALGORITHM_VERSION,
            )
        )
        if report is None:
            ratings = self.session.scalars(
                select(RoleConstructRating).where(RoleConstructRating.profile_id == profile.id)
            ).all()
            result = match_role_profile(
                MatchingRoleProfile(
                    approved=True,
                    constructs=tuple(
                        RatingContract(
                            key=r.construct_key,
                            rating=r.rating,
                            confidence=r.confidence,
                            rationale=r.rationale,
                            evidence=r.evidence_json,
                        )
                        for r in ratings
                    ),
                ),
                AssessmentScoreResult.model_validate(assessment.scores_json),
            )
            report = AlignmentReport(
                assessment_id=assessment.id,
                role_profile_id=profile.id,
                algorithm_version=result.algorithm_version,
                result_json=result.model_dump(mode="json"),
            )
            self.session.add(report)
            self.session.flush()
            for item in result.items:
                self.session.add(
                    AlignmentReportItem(
                        report_id=report.id,
                        construct_key=item.construct_key.value,
                        classification=item.classification.value,
                        confidence=item.confidence.value,
                        explanation_json=item.explanation.model_dump(mode="json"),
                        questions_json=item.interview_questions.model_dump(mode="json"),
                    )
                )
            # Commit the result and its required creation audit atomically.
            self.session.add(
                AuditEvent(
                    organization_id=self.context.organization.organization_id,
                    actor_id=self.context.user_id,
                    event_type="alignment_report.generated",
                    entity_type="alignment_report",
                    entity_id=report.id,
                    metadata_json={"algorithm_version": result.algorithm_version},
                )
            )
        commit_or_flush(self.session)
        return self._response(report, profile)

    def read(self, report_id: UUID) -> ReportResponse:
        """Hide report existence from every other organization."""

        row = self.session.execute(
            select(AlignmentReport, RoleProfile)
            .join(RoleProfile, RoleProfile.id == AlignmentReport.role_profile_id)
            .join(Role, Role.id == RoleProfile.role_id)
            .where(
                AlignmentReport.id == report_id,
                Role.organization_id == self.context.organization.organization_id,
            )
        ).one_or_none()
        if row is None:
            raise organization_resource_not_found()
        return self._response(row[0], row[1])

    @staticmethod
    def _response(report: AlignmentReport, profile: RoleProfile) -> ReportResponse:
        return ReportResponse(
            id=report.id,
            assessment_id=report.assessment_id,
            role_profile_id=profile.id,
            role_profile_version=profile.version,
            generated_at=report.created_at,
            result=MatchingResult.model_validate(report.result_json),
        )

    def list_submissions(
        self, role_id: UUID, *, limit: int, offset: int
    ) -> list[SubmittedAssessmentResponse]:
        """Expose chronological, score-free source IDs for the report workflow."""

        role = self.session.scalar(
            select(Role).where(
                Role.id == role_id,
                Role.organization_id == self.context.organization.organization_id,
            )
        )
        if role is None:
            raise organization_resource_not_found()
        rows = self.session.execute(
            select(Assessment, AssessmentInvite, RoleProfile, AlignmentReport.id)
            .join(AssessmentInvite, AssessmentInvite.id == Assessment.invite_id)
            .join(RoleProfile, RoleProfile.id == AssessmentInvite.role_profile_id)
            .outerjoin(
                AlignmentReport,
                (
                    (AlignmentReport.assessment_id == Assessment.id)
                    & (AlignmentReport.role_profile_id == RoleProfile.id)
                    & (AlignmentReport.algorithm_version == MATCHING_ALGORITHM_VERSION)
                ),
            )
            .where(RoleProfile.role_id == role_id, Assessment.submitted_at.is_not(None))
            .order_by(Assessment.submitted_at, Assessment.id)
            .limit(limit)
            .offset(offset)
        )
        return [
            SubmittedAssessmentResponse(
                assessment_id=assessment.id,
                invitation_id=invite.id,
                candidate_email=invite.email,
                role_profile_id=profile.id,
                role_profile_version=profile.version,
                submitted_at=assessment.submitted_at,
                report_id=report_id,
            )
            for assessment, invite, profile, report_id in rows
        ]

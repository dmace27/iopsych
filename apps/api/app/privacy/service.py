"""Tenant-scoped candidate export, anonymization, and retention service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.auth.context import AuthorizationContext
from app.auth.errors import organization_resource_not_found, resource_unavailable
from app.database.models import (
    AlignmentReport,
    AlignmentReportItem,
    Assessment,
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    CandidateConsent,
    Organization,
    Role,
    RoleProfile,
)
from app.database.session import commit_or_flush
from app.privacy.config import PrivacySettings
from app.privacy.schemas import (
    CandidateDataExportResponse,
    CandidateDeletionResponse,
    ExportActivity,
    ExportAssessment,
    ExportConsent,
    ExportInvitation,
    ExportOrganization,
    ExportReport,
    PrivacyAuditEventResponse,
    PrivacyStatusResponse,
    RetentionRunResponse,
)


@dataclass(frozen=True)
class _CandidateRecord:
    """One assessment and its complete tenant/consent ownership chain."""

    assessment: Assessment
    invite: AssessmentInvite
    consent: CandidateConsent
    profile: RoleProfile
    role: Role
    organization: Organization


class PrivacyService:
    """Perform privacy operations within an admin's organization boundary."""

    def __init__(
        self,
        session: Session,
        settings: PrivacySettings,
        context: AuthorizationContext | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._context = context

    def export(
        self, assessment_id: UUID, *, now: datetime | None = None
    ) -> CandidateDataExportResponse:
        """Return every retained candidate datum in a portable JSON envelope."""

        record = self._get_record(assessment_id)
        if record.assessment.anonymized_at is not None:
            raise resource_unavailable(
                code="candidate_data_anonymized",
                detail="Candidate data has already been anonymized and cannot be exported.",
            )
        reports = list(
            self._session.scalars(
                select(AlignmentReport)
                .where(AlignmentReport.assessment_id == assessment_id)
                .order_by(AlignmentReport.created_at, AlignmentReport.id)
            )
        )
        entity_ids = [record.invite.id, record.consent.id, assessment_id]
        entity_ids.extend(report.id for report in reports)
        events = list(
            self._session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.organization_id == record.organization.id,
                    AuditEvent.entity_id.in_(entity_ids),
                )
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
        )
        return CandidateDataExportResponse(
            generated_at=now or datetime.now(UTC),
            organization=ExportOrganization(
                name=record.organization.name,
                role_title=record.role.title,
                role_profile_version=record.profile.version,
            ),
            invitation=ExportInvitation(
                id=record.invite.id,
                email=record.invite.email,
                status=record.invite.status,
                created_at=record.invite.created_at,
                sent_at=record.invite.sent_at,
                expires_at=record.invite.expires_at,
                revoked_at=record.invite.revoked_at,
            ),
            consent=ExportConsent(
                id=record.consent.id,
                decision=record.consent.decision,
                notice_version=record.consent.notice_version,
                recorded_at=record.consent.created_at,
            ),
            assessment=ExportAssessment(
                id=record.assessment.id,
                created_at=record.assessment.created_at,
                submitted_at=record.assessment.submitted_at,
                retention_expires_at=self._retention_deadline(record.assessment),
                definition=record.assessment.definition_json,
                responses=record.assessment.responses_json,
                scores=record.assessment.scores_json,
            ),
            reports=[
                ExportReport(
                    id=report.id,
                    generated_at=report.created_at,
                    algorithm_version=report.algorithm_version,
                    result=report.result_json,
                )
                for report in reports
            ],
            activity=[
                ExportActivity(
                    event_type=event.event_type,
                    entity_type=event.entity_type,
                    entity_id=event.entity_id,
                    occurred_at=event.created_at,
                    details=event.metadata_json,
                )
                for event in events
            ],
        )

    def anonymize(
        self,
        assessment_id: UUID,
        *,
        now: datetime | None = None,
    ) -> CandidateDeletionResponse:
        """Anonymize candidate data idempotently for an administrator request."""

        record = self._get_record(assessment_id, lock=True)
        result = self._anonymize_record(record, reason="admin_request", now=now)
        commit_or_flush(self._session)
        return result

    def status(self, *, now: datetime | None = None) -> PrivacyStatusResponse:
        """Summarize tenant retention deadlines without exposing candidate payloads."""

        organization_id = self._organization_id()
        assessments = list(
            self._session.scalars(
                select(Assessment)
                .join(AssessmentInvite, AssessmentInvite.id == Assessment.invite_id)
                .join(RoleProfile, RoleProfile.id == AssessmentInvite.role_profile_id)
                .join(Role, Role.id == RoleProfile.role_id)
                .where(Role.organization_id == organization_id)
            )
        )
        current_time = now or datetime.now(UTC)
        active = [item for item in assessments if item.anonymized_at is None]
        deadlines = [
            deadline for item in active if (deadline := self._retention_deadline(item)) is not None
        ]
        return PrivacyStatusResponse(
            retention_days=self._settings.retention_days,
            total_assessments=len(assessments),
            active_assessments=len(active),
            anonymized_assessments=len(assessments) - len(active),
            due_assessments=sum(deadline <= current_time for deadline in deadlines),
            next_retention_at=min(deadlines, default=None),
        )

    def list_audit_events(
        self,
        *,
        limit: int,
        offset: int,
        entity_id: UUID | None,
        event_type: str | None,
        before: UUID | None,
    ) -> list[PrivacyAuditEventResponse]:
        """Return newest-first tenant audit history with optional exact filters."""

        organization_id = self._organization_id()
        statement = select(AuditEvent).where(AuditEvent.organization_id == organization_id)
        if entity_id is not None:
            statement = statement.where(AuditEvent.entity_id == entity_id)
        if event_type is not None:
            statement = statement.where(AuditEvent.event_type == event_type)
        if before is not None:
            cursor_statement = select(AuditEvent).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.id == before,
            )
            cursor = self._session.scalar(cursor_statement)
            if cursor is None:
                raise organization_resource_not_found()
            # Compare against a database-native timestamp subquery. This avoids
            # SQLite text-precision differences while retaining PostgreSQL's
            # exact timestamp semantics.
            cursor_created_at = (
                select(AuditEvent.created_at)
                .where(
                    AuditEvent.organization_id == organization_id,
                    AuditEvent.id == before,
                )
                .scalar_subquery()
            )
            statement = statement.where(
                or_(
                    AuditEvent.created_at < cursor_created_at,
                    and_(
                        AuditEvent.created_at == cursor_created_at,
                        AuditEvent.id < cursor.id,
                    ),
                )
            )
        events = self._session.scalars(
            statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [
            PrivacyAuditEventResponse(
                id=event.id,
                actor_id=event.actor_id,
                event_type=event.event_type,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                occurred_at=event.created_at,
                details=event.metadata_json,
            )
            for event in events
        ]

    def run_retention(
        self,
        *,
        now: datetime | None = None,
    ) -> RetentionRunResponse:
        """Anonymize one bounded batch due under the configured retention policy."""

        current_time = now or datetime.now(UTC)
        legacy_cutoff = current_time - timedelta(days=self._settings.retention_days)
        statement = (
            select(Assessment.id)
            .join(AssessmentInvite, AssessmentInvite.id == Assessment.invite_id)
            .join(RoleProfile, RoleProfile.id == AssessmentInvite.role_profile_id)
            .join(Role, Role.id == RoleProfile.role_id)
            .where(
                Assessment.anonymized_at.is_(None),
                Assessment.submitted_at.is_not(None),
                or_(
                    Assessment.retention_expires_at <= current_time,
                    (
                        Assessment.retention_expires_at.is_(None)
                        & (Assessment.submitted_at <= legacy_cutoff)
                    ),
                ),
            )
            .order_by(Assessment.submitted_at, Assessment.id)
            .limit(self._settings.retention_batch_size)
            # Lock only assessment rows. Locking every joined role/profile row
            # would unnecessarily serialize workers processing the same role.
            .with_for_update(of=Assessment, skip_locked=True)
        )
        if self._context is not None:
            statement = statement.where(
                Role.organization_id == self._context.organization.organization_id
            )
        assessment_ids = list(self._session.scalars(statement))
        anonymized_ids: list[UUID] = []
        for assessment_id in assessment_ids:
            record = self._get_record(assessment_id, lock=False)
            result = self._anonymize_record(record, reason="retention_expired", now=current_time)
            if not result.already_anonymized:
                anonymized_ids.append(assessment_id)
        commit_or_flush(self._session)
        return RetentionRunResponse(
            completed_at=current_time,
            anonymized_assessment_ids=anonymized_ids,
        )

    def _get_record(self, assessment_id: UUID, *, lock: bool = False) -> _CandidateRecord:
        """Resolve an assessment through its complete tenant ownership chain."""

        statement = (
            select(
                Assessment,
                AssessmentInvite,
                CandidateConsent,
                RoleProfile,
                Role,
                Organization,
            )
            .join(AssessmentInvite, AssessmentInvite.id == Assessment.invite_id)
            .join(CandidateConsent, CandidateConsent.id == Assessment.consent_id)
            .join(RoleProfile, RoleProfile.id == AssessmentInvite.role_profile_id)
            .join(Role, Role.id == RoleProfile.role_id)
            .join(Organization, Organization.id == Role.organization_id)
            .where(Assessment.id == assessment_id)
        )
        if self._context is not None:
            statement = statement.where(
                Role.organization_id == self._context.organization.organization_id
            )
        if lock:
            statement = statement.with_for_update(of=Assessment)
        row = self._session.execute(statement).one_or_none()
        if row is None:
            raise organization_resource_not_found()
        return _CandidateRecord(*row)

    def _anonymize_record(
        self,
        record: _CandidateRecord,
        *,
        reason: str,
        now: datetime | None,
    ) -> CandidateDeletionResponse:
        """Erase identifying and derived data while preserving an audit tombstone."""

        assessment = record.assessment
        if assessment.anonymized_at is not None:
            return CandidateDeletionResponse(
                assessment_id=assessment.id,
                anonymized_at=assessment.anonymized_at,
                already_anonymized=True,
                reports_deleted=0,
            )
        anonymized_at = now or datetime.now(UTC)
        report_ids = list(
            self._session.scalars(
                select(AlignmentReport.id).where(AlignmentReport.assessment_id == assessment.id)
            )
        )
        if report_ids:
            self._session.execute(
                delete(AlignmentReportItem).where(AlignmentReportItem.report_id.in_(report_ids))
            )
            self._session.execute(delete(AlignmentReport).where(AlignmentReport.id.in_(report_ids)))

        assessment.definition_json = {"anonymized": True}
        assessment.responses_json = {"anonymized": True}
        assessment.scores_json = {"anonymized": True}
        assessment.anonymized_at = anonymized_at
        record.invite.email = f"deleted-{record.invite.id.hex}@privacy.invalid"
        record.invite.token_hash = sha256(f"anonymized:{record.invite.id}".encode()).hexdigest()
        record.invite.status = AssessmentInviteStatus.REVOKED
        record.invite.revoked_at = anonymized_at
        record.invite.revoked_by = self._context.user_id if self._context is not None else None
        self._session.add(
            AuditEvent(
                organization_id=record.organization.id,
                actor_id=self._context.user_id if self._context is not None else None,
                event_type="candidate_data.anonymized",
                entity_type="assessment",
                entity_id=assessment.id,
                metadata_json={
                    "reason": reason,
                    "reports_deleted": len(report_ids),
                },
            )
        )
        return CandidateDeletionResponse(
            assessment_id=assessment.id,
            anonymized_at=anonymized_at,
            already_anonymized=False,
            reports_deleted=len(report_ids),
        )

    def _organization_id(self) -> UUID:
        """Require a tenant context for interactive admin operations."""

        if self._context is None:
            raise RuntimeError("an organization context is required")
        return self._context.organization.organization_id

    def _retention_deadline(self, assessment: Assessment) -> datetime | None:
        """Use a stored deadline or derive one for pre-migration submissions."""

        if assessment.retention_expires_at is not None:
            return assessment.retention_expires_at
        if assessment.submitted_at is None:
            return None
        return assessment.submitted_at + timedelta(days=self._settings.retention_days)

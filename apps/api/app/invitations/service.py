"""Tenant-scoped invitation issuance and token-scoped candidate consent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import AuthorizationContext
from app.auth.errors import (
    organization_resource_not_found,
    resource_conflict,
    resource_unavailable,
    resource_validation_failed,
    service_unavailable,
    upstream_delivery_failed,
)
from app.database.models import (
    Assessment,
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    CandidateConsent,
    ConsentDecision,
    Organization,
    Role,
    RoleProfile,
    RoleProfileStatus,
    RoleStatus,
)
from app.database.repositories import OrganizationDataAccess
from app.invitations.config import InvitationSettings
from app.invitations.delivery import (
    InvitationDeliveryAdapter,
    InvitationDeliveryError,
    build_invitation_email,
)
from app.invitations.schemas import (
    CandidateInviteResponse,
    ConsentNotice,
    ConsentRequest,
    InvitationCreateRequest,
)
from app.invitations.tokens import InvalidInviteTokenError, InviteTokenCodec
from iopsych_contracts.assessment import (
    AssessmentDefinition,
    AssessmentResponseSet,
    AssessmentScoringError,
    score_assessment,
)

PILOT_DEFINITION_PATH = (
    Path(__file__).resolve().parents[4] / "packages/shared/definitions/v1/pilot-assessment.json"
)


@dataclass(frozen=True)
class _CandidateInvite:
    """A validated invite plus the only public role/tenant display fields."""

    invite: AssessmentInvite
    role_title: str
    organization_name: str
    organization_id: UUID


class InternalInvitationService:
    """Issue and revoke invitations inside one authenticated organization."""

    def __init__(
        self,
        session: Session,
        context: AuthorizationContext,
        settings: InvitationSettings,
        token_codec: InviteTokenCodec | None,
        delivery: InvitationDeliveryAdapter,
    ) -> None:
        self._session = session
        self._context = context
        self._settings = settings
        self._token_codec = token_codec
        self._delivery = delivery
        self._data = OrganizationDataAccess(session, context.organization.organization_id)

    def create(self, role_id: UUID, request: InvitationCreateRequest) -> AssessmentInvite:
        """Create, deliver, and activate an invite for an approved profile only."""

        codec = self._require_codec()
        role = self._data.get_role(role_id)
        profile = self._data.get_role_profile_for_role(role_id, request.role_profile_id)
        if role is None or profile is None:
            raise organization_resource_not_found()
        if role.status is RoleStatus.ARCHIVED:
            raise resource_conflict(
                code="role_archived", detail="Archived roles cannot issue invitations."
            )
        if profile.status is not RoleProfileStatus.APPROVED:
            raise resource_conflict(
                code="profile_not_approved",
                detail="Candidate invitations require an approved role profile.",
            )

        expiry_hours = request.expires_in_hours or self._settings.default_expiry_hours
        if expiry_hours > self._settings.maximum_expiry_hours:
            raise resource_conflict(
                code="invite_expiry_exceeds_policy",
                detail="The requested invitation expiry exceeds organization policy.",
            )
        now = datetime.now(UTC)
        generated = codec.generate()
        invite = AssessmentInvite(
            role_profile_id=profile.id,
            email=request.email,
            token_hash=generated.token_hash,
            expires_at=now + timedelta(hours=expiry_hours),
            status=AssessmentInviteStatus.PENDING_DELIVERY,
        )
        self._session.add(invite)
        self._session.flush()

        organization = self._session.get(Organization, self._context.organization.organization_id)
        if organization is None:
            # Authentication already proved this tenant. Treat disappearance as
            # unavailable instead of exposing an impossible storage race.
            self._session.rollback()
            raise service_unavailable(
                code="invitation_service_unavailable",
                detail="Candidate invitations are temporarily unavailable.",
            )
        invite_url = f"{self._settings.candidate_base_url}/{generated.raw_token}"
        message = build_invitation_email(
            recipient_email=request.email,
            organization_name=organization.name,
            invite_url=invite_url,
            expires_at=invite.expires_at,
            privacy_contact_email=self._settings.privacy_contact_email,
        )
        try:
            self._delivery.send(message)
        except InvitationDeliveryError as exc:
            self._session.rollback()
            raise upstream_delivery_failed() from exc

        invite.status = AssessmentInviteStatus.ACTIVE
        invite.sent_at = now
        self._session.commit()
        return invite

    def revoke(self, role_id: UUID, invite_id: UUID) -> AssessmentInvite:
        """Revoke a tenant-owned invite without revealing foreign identifiers."""

        invite = self._data.get_assessment_invite_for_role(role_id, invite_id)
        if invite is None:
            raise organization_resource_not_found()
        if invite.status is AssessmentInviteStatus.REVOKED:
            return invite
        invite.status = AssessmentInviteStatus.REVOKED
        invite.revoked_at = datetime.now(UTC)
        invite.revoked_by = self._context.user_id
        self._session.commit()
        return invite

    def _require_codec(self) -> InviteTokenCodec:
        """Fail closed when hosted configuration omitted the signing key."""

        if self._token_codec is None:
            raise service_unavailable(
                code="invitation_service_unavailable",
                detail="Candidate invitations are not configured.",
            )
        return self._token_codec


class CandidateInvitationService:
    """Resolve bearer links and atomically record a terminal consent decision."""

    def __init__(
        self,
        session: Session,
        settings: InvitationSettings,
        token_codec: InviteTokenCodec | None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._token_codec = token_codec

    def read(self, raw_token: str) -> CandidateInviteResponse:
        """Return consent content and public context, never assessment questions."""

        candidate_invite = self._resolve(raw_token, lock=False)
        self._append_audit(candidate_invite, "candidate_invite.accessed")
        self._session.commit()
        return self._response(candidate_invite)

    def record_consent(self, raw_token: str, request: ConsentRequest) -> CandidateInviteResponse:
        """Record one explicit choice; repeated identical choices are idempotent."""

        candidate_invite = self._resolve(raw_token, lock=True)
        invite = candidate_invite.invite
        existing = self._session.scalar(
            select(CandidateConsent).where(CandidateConsent.invite_id == invite.id)
        )
        if existing is not None and existing.decision is not request.decision:
            raise resource_conflict(
                code="consent_already_recorded",
                detail="A different consent decision has already been recorded.",
            )
        if existing is None:
            existing = CandidateConsent(
                invite_id=invite.id,
                decision=request.decision,
                notice_version=self._settings.consent_notice_version,
            )
            self._session.add(existing)
            self._session.flush()
            invite.status = (
                AssessmentInviteStatus.CONSENTED
                if request.decision is ConsentDecision.CONSENT
                else AssessmentInviteStatus.DECLINED
            )
        self._append_audit(
            candidate_invite,
            "candidate_consent.recorded",
            metadata={"decision": request.decision.value},
        )
        self._session.commit()
        return self._response(candidate_invite, consent=existing)

    def _resolve(self, raw_token: str, *, lock: bool) -> _CandidateInvite:
        """Verify the signature, hash for lookup, and enforce terminal states."""

        if self._token_codec is None:
            raise service_unavailable(
                code="invitation_service_unavailable",
                detail="Candidate invitations are not configured.",
            )
        try:
            token_hash = self._token_codec.validate_and_hash(raw_token)
        except InvalidInviteTokenError as exc:
            raise organization_resource_not_found() from exc

        statement = (
            select(AssessmentInvite, Role.title, Organization.name, Role.organization_id)
            .join(RoleProfile, RoleProfile.id == AssessmentInvite.role_profile_id)
            .join(Role, Role.id == RoleProfile.role_id)
            .join(Organization, Organization.id == Role.organization_id)
            .where(AssessmentInvite.token_hash == token_hash)
        )
        if lock:
            statement = statement.with_for_update()
        row = self._session.execute(statement).one_or_none()
        if row is None:
            raise organization_resource_not_found()
        candidate_invite = _CandidateInvite(
            invite=row[0],
            role_title=row[1],
            organization_name=row[2],
            organization_id=row[3],
        )
        self._require_available(candidate_invite)
        return candidate_invite

    def submit(self, raw_token: str, responses: AssessmentResponseSet) -> UUID:
        """Validate and score a complete response set once, after explicit consent."""

        candidate = self._resolve(raw_token, lock=True)
        invite = require_consented_invite(self._session, candidate.invite.id)
        existing = self._session.scalar(select(Assessment).where(Assessment.invite_id == invite.id))
        if existing is not None:
            if existing.responses_json == responses.model_dump(mode="json"):
                return existing.id
            raise resource_conflict(
                code="assessment_already_submitted",
                detail="This assessment has already been submitted.",
            )
        consent = self._session.scalar(
            select(CandidateConsent).where(
                CandidateConsent.invite_id == invite.id,
                CandidateConsent.decision == ConsentDecision.CONSENT,
            )
        )
        assert consent is not None
        definition = AssessmentDefinition.model_validate_json(
            PILOT_DEFINITION_PATH.read_text(encoding="utf-8")
        )
        try:
            scores = score_assessment(definition, responses)
        except AssessmentScoringError as exc:
            raise resource_validation_failed(
                code="invalid_assessment_responses", detail=str(exc)
            ) from exc
        assessment = Assessment(
            invite_id=invite.id,
            consent_id=consent.id,
            submitted_at=datetime.now(UTC),
            definition_json=definition.model_dump(mode="json"),
            responses_json=responses.model_dump(mode="json"),
            scores_json=scores.model_dump(mode="json"),
        )
        self._session.add(assessment)
        self._session.flush()
        self._session.add(
            AuditEvent(
                organization_id=candidate.organization_id,
                actor_id=None,
                event_type="assessment.submitted",
                entity_type="assessment",
                entity_id=assessment.id,
                metadata_json={"scoring_version": scores.scoring_version},
            )
        )
        self._session.commit()
        return assessment.id

    def _require_available(self, candidate_invite: _CandidateInvite) -> None:
        """Expire stale links and reject revoked or undelivered credentials."""

        invite = candidate_invite.invite
        if invite.status is AssessmentInviteStatus.REVOKED:
            raise resource_unavailable(
                code="invitation_unavailable",
                detail="This invitation is no longer available.",
            )
        if invite.status is AssessmentInviteStatus.PENDING_DELIVERY:
            raise organization_resource_not_found()
        if invite.status is AssessmentInviteStatus.EXPIRED:
            raise resource_unavailable(
                code="invitation_expired",
                detail="This invitation has expired.",
            )
        if invite.expires_at <= datetime.now(UTC):
            invite.status = AssessmentInviteStatus.EXPIRED
            self._append_audit(candidate_invite, "candidate_invite.expired")
            self._session.commit()
            raise resource_unavailable(
                code="invitation_expired",
                detail="This invitation has expired.",
            )

    def _response(
        self,
        candidate_invite: _CandidateInvite,
        *,
        consent: CandidateConsent | None = None,
    ) -> CandidateInviteResponse:
        """Build candidate-safe state with the current immutable decision."""

        if consent is None:
            consent = self._session.scalar(
                select(CandidateConsent).where(
                    CandidateConsent.invite_id == candidate_invite.invite.id
                )
            )
        decision = consent.decision if consent is not None else None
        assessment = self._session.scalar(
            select(Assessment).where(
                Assessment.invite_id == candidate_invite.invite.id,
                Assessment.submitted_at.is_not(None),
            )
        )
        return CandidateInviteResponse(
            invitation_id=candidate_invite.invite.id,
            organization_name=candidate_invite.organization_name,
            role_title=candidate_invite.role_title,
            expires_at=candidate_invite.invite.expires_at,
            status=candidate_invite.invite.status,
            consent_notice=ConsentNotice(
                version=self._settings.consent_notice_version,
                purpose=self._settings.purpose_statement,
                data_use=self._settings.data_use_statement,
                retention=self._settings.retention_statement,
                accommodation_contact_email=self._settings.accommodation_contact_email,
                privacy_contact_email=self._settings.privacy_contact_email,
            ),
            decision=decision,
            decision_recorded_at=consent.created_at if consent is not None else None,
            can_start_assessment=decision is ConsentDecision.CONSENT,
            assessment_id=assessment.id if assessment is not None else None,
        )

    def _append_audit(
        self,
        candidate_invite: _CandidateInvite,
        event_type: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Append token-safe candidate activity in the invite's organization."""

        self._session.add(
            AuditEvent(
                organization_id=candidate_invite.organization_id,
                actor_id=None,
                event_type=event_type,
                entity_type="assessment_invite",
                entity_id=candidate_invite.invite.id,
                metadata_json=metadata or {},
            )
        )


def require_consented_invite(session: Session, invite_id: UUID) -> AssessmentInvite:
    """Reusable package-2A gate: assessment work may begin only after consent."""

    statement = (
        select(AssessmentInvite)
        .join(CandidateConsent, CandidateConsent.invite_id == AssessmentInvite.id)
        .where(
            AssessmentInvite.id == invite_id,
            AssessmentInvite.status == AssessmentInviteStatus.CONSENTED,
            CandidateConsent.decision == ConsentDecision.CONSENT,
        )
    )
    invite = session.scalar(statement)
    if invite is None or invite.expires_at <= datetime.now(UTC):
        raise resource_conflict(
            code="candidate_consent_required",
            detail="Assessment access requires a valid affirmative consent record.",
        )
    return invite

"""Tenant-scoped invitation issuance and token-scoped candidate consent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
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
)
from app.database.models import (
    Assessment,
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    CandidateConsent,
    ConsentDecision,
    InvitationDelivery,
    InvitationDeliveryStatus,
    Organization,
    Role,
    RoleProfile,
    RoleProfileStatus,
    RoleStatus,
)
from app.database.repositories import OrganizationDataAccess
from app.database.session import commit_or_flush
from app.invitations.config import InvitationSettings
from app.invitations.delivery import (
    InvitationDeliveryAdapter,
    UnconfiguredInvitationDelivery,
    build_invitation_email,
)
from app.invitations.encryption import encrypt_message
from app.invitations.outbox import append_delivery_audit, cancel_delivery
from app.invitations.schemas import (
    CandidateInviteResponse,
    ConsentNotice,
    ConsentRequest,
    InvitationCreateRequest,
    InvitationReissueRequest,
)
from app.invitations.tokens import InvalidInviteTokenError, InviteTokenCodec
from app.privacy.config import PrivacySettings
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
        """Commit an idempotent invitation/outbox pair before any delivery is attempted."""
        invite = self._issue(role_id, request)
        commit_or_flush(self._session)
        return invite

    def _issue(
        self, role_id: UUID, request: InvitationCreateRequest, *, replaces: UUID | None = None
    ) -> AssessmentInvite:
        """Freeze the full provider payload and retain the request key permanently."""
        codec = self._require_codec()
        if self._settings.delivery_encryption_key is None or isinstance(
            self._delivery, UnconfiguredInvitationDelivery
        ):
            raise service_unavailable(
                code="invitation_delivery_unconfigured",
                detail="Invitation email delivery is not configured. Contact your administrator.",
            )
        # Serialize issuance keys across all roles in this tenant. NO KEY UPDATE
        # permits worker audit foreign-key checks while blocking another issuer.
        organization = self._session.scalar(
            select(Organization)
            .where(Organization.id == self._context.organization.organization_id)
            .with_for_update(key_share=True)
        )
        if organization is None:
            raise service_unavailable(
                code="invitation_service_unavailable",
                detail="Candidate invitations are temporarily unavailable.",
            )
        canonical = {
            "role_id": str(role_id),
            "replaces": str(replaces),
            **request.model_dump(mode="json", exclude={"request_id"}),
        }
        fingerprint = sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
        existing = self._session.scalar(
            select(InvitationDelivery).where(
                InvitationDelivery.organization_id == organization.id,
                InvitationDelivery.request_id == request.request_id,
            )
        )
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise resource_conflict(
                    code="invitation_request_conflict",
                    detail="This request identifier was used with different invitation details.",
                )
            invite = self._session.get(AssessmentInvite, existing.invite_id)
            assert invite is not None
            return invite
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
        # The row is valid before sending. Only the encrypted queue knows the
        # bearer token, so acceptance followed by a worker crash still yields a
        # usable link whose invitation and issuance audit have already committed.
        invite = AssessmentInvite(
            role_profile_id=profile.id,
            email=request.email,
            token_hash=generated.token_hash,
            expires_at=now + timedelta(hours=expiry_hours),
            status=AssessmentInviteStatus.ACTIVE,
        )
        self._session.add(invite)
        self._session.flush()
        message = build_invitation_email(
            recipient_email=request.email,
            sender_email=self._settings.delivery_from_email,
            organization_name=organization.name,
            invite_url=f"{self._settings.candidate_base_url}/{generated.raw_token}",
            expires_at=invite.expires_at,
            privacy_contact_email=self._settings.privacy_contact_email,
        )
        delivery = InvitationDelivery(
            organization_id=organization.id,
            invite_id=invite.id,
            requested_by=self._context.user_id,
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            replaces_invite_id=replaces,
            encrypted_message=encrypt_message(message, self._settings),
            status=InvitationDeliveryStatus.QUEUED,
            attempt_count=0,
            next_attempt_at=now,
            retry_until=min(invite.expires_at, now + timedelta(hours=23)),
        )
        self._session.add(delivery)
        self._session.flush()
        append_delivery_audit(self._session, delivery, "queued")
        return invite

    def delivery_state(self, role_id: UUID, invite_id: UUID) -> InvitationDelivery:
        """Read tenant-scoped progress without returning queue contents."""
        if self._data.get_assessment_invite_for_role(role_id, invite_id) is None:
            raise organization_resource_not_found()
        delivery = self._session.scalar(
            select(InvitationDelivery).where(InvitationDelivery.invite_id == invite_id)
        )
        if delivery is None:
            raise organization_resource_not_found()
        return delivery

    def revoke(self, role_id: UUID, invite_id: UUID) -> AssessmentInvite:
        """Revoke immediately and remove pending delivery credentials atomically."""
        invite = self._locked_invite(role_id, invite_id)
        if invite.status is AssessmentInviteStatus.REVOKED:
            return invite
        self._revoke(invite)
        commit_or_flush(self._session)
        return invite

    def reissue(
        self, role_id: UUID, invite_id: UUID, request: InvitationReissueRequest
    ) -> AssessmentInvite:
        """Explicitly replace an unused link; retries never mint another replacement."""
        # Match issuance's tenant lock before taking the old invitation lock.
        self._session.execute(
            select(Organization.id)
            .where(Organization.id == self._context.organization.organization_id)
            .with_for_update(key_share=True)
        )
        previous = self._locked_invite(role_id, invite_id)
        if (
            self._session.scalar(
                select(CandidateConsent.id).where(CandidateConsent.invite_id == previous.id)
            )
            is not None
            or self._session.scalar(
                select(Assessment.id).where(Assessment.invite_id == previous.id)
            )
            is not None
        ):
            raise resource_conflict(
                code="invitation_already_used",
                detail="Consented, declined or submitted invitations cannot be reissued.",
            )
        invite = self._issue(
            role_id,
            InvitationCreateRequest(
                request_id=request.request_id,
                role_profile_id=previous.role_profile_id,
                email=previous.email,
                expires_in_hours=request.expires_in_hours,
            ),
            replaces=previous.id,
        )
        self._revoke(previous)
        commit_or_flush(self._session)
        return invite

    def _locked_invite(self, role_id: UUID, invite_id: UUID) -> AssessmentInvite:
        """Resolve scope first, then lock only the invitation, before its delivery row."""
        if self._data.get_assessment_invite_for_role(role_id, invite_id) is None:
            raise organization_resource_not_found()
        invite = self._session.scalar(
            select(AssessmentInvite)
            .where(AssessmentInvite.id == invite_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        assert invite is not None
        return invite

    def _revoke(self, invite: AssessmentInvite) -> None:
        """Preserve the first revocation timestamp and purge any pending payload."""
        if invite.status is not AssessmentInviteStatus.REVOKED:
            invite.status = AssessmentInviteStatus.REVOKED
            invite.revoked_at = datetime.now(UTC)
            invite.revoked_by = self._context.user_id
        cancel_delivery(self._session, invite.id)

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
        privacy_settings: PrivacySettings,
    ) -> None:
        self._session = session
        self._settings = settings
        self._token_codec = token_codec
        self._privacy_settings = privacy_settings

    def read(self, raw_token: str) -> CandidateInviteResponse:
        """Return consent content and public context, never assessment questions."""

        candidate_invite = self._resolve(raw_token, lock=False)
        self._append_audit(candidate_invite, "candidate_invite.accessed")
        commit_or_flush(self._session)
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
        commit_or_flush(self._session)
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
        canonical_responses = _canonical_response_payload(responses)
        existing = self._session.scalar(select(Assessment).where(Assessment.invite_id == invite.id))
        if existing is not None:
            stored_responses = AssessmentResponseSet.model_validate(existing.responses_json)
            if _canonical_response_payload(stored_responses) == canonical_responses:
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
        submitted_at = datetime.now(UTC)
        assessment = Assessment(
            invite_id=invite.id,
            consent_id=consent.id,
            submitted_at=submitted_at,
            retention_expires_at=submitted_at
            + timedelta(days=self._privacy_settings.retention_days),
            definition_json=definition.model_dump(mode="json"),
            responses_json=canonical_responses,
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
        commit_or_flush(self._session)
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
            cancel_delivery(self._session, invite.id)
            self._append_audit(candidate_invite, "candidate_invite.expired")
            commit_or_flush(self._session)
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
                retention=self._settings.retention_statement.format(
                    retention_days=self._privacy_settings.retention_days
                ),
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


def _canonical_response_payload(responses: AssessmentResponseSet) -> dict[str, object]:
    """Serialize responses in block-ID order for stable storage and retries."""

    ordered = tuple(sorted(responses.responses, key=lambda response: response.block_id))
    return responses.model_copy(update={"responses": ordered}).model_dump(mode="json")

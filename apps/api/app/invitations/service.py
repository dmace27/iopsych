"""Tenant-scoped invitation issuance and token-scoped candidate consent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assignments.registry import (
    LEGACY_DEFINITION_PATH,
    AssignedDefinitionResponse,
    definition_response,
    new_assignment,
    read_assignment,
    score_assignment,
)
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
from app.database.session import commit_or_flush
from app.invitations.config import InvitationSettings
from app.invitations.credentials import LocalCredentialCipher
from app.invitations.delivery import (
    InvitationDeliveryAdapter,
    InvitationDeliveryError,
    build_invitation_email,
)
from app.invitations.queue import (
    cancel_delivery,
    issuance_digests,
    replay_invitation,
    require_queue_database,
    require_resolved_prior_delivery,
    stage_delivery,
)
from app.invitations.schemas import (
    CandidateInviteResponse,
    ConsentNotice,
    ConsentRequest,
    InvitationCreateRequest,
    NoticeHistory,
)
from app.invitations.tokens import InvalidInviteTokenError, InviteTokenCodec
from app.privacy.config import PrivacySettings
from app.privacy.notice_snapshot import (
    InvalidNoticeSnapshotError,
    NoticeReviewRequiredError,
    build_notice_snapshot,
    notice_snapshot_hash,
    require_presented_notice,
)
from iopsych_contracts.assessment import (
    AssessmentResponseSet,
    AssessmentScoringError,
)

PILOT_DEFINITION_PATH = LEGACY_DEFINITION_PATH


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
        queue_cipher: LocalCredentialCipher | None = None,
        privacy_settings: PrivacySettings | None = None,
    ) -> None:
        self._session = session
        self._context = context
        self._settings = settings
        self._token_codec = token_codec
        self._delivery = delivery
        self._queue_cipher = queue_cipher
        self._privacy_settings = privacy_settings or PrivacySettings()
        self._data = OrganizationDataAccess(session, context.organization.organization_id)

    def create(
        self, role_id: UUID, request: InvitationCreateRequest, *, idempotency_key: str | None = None
    ) -> AssessmentInvite:
        """Create, deliver, and activate an invite for an approved profile only."""

        codec = self._require_codec()
        role = self._data.get_role(role_id)
        profile = self._data.get_role_profile_for_role(role_id, request.role_profile_id)
        if role is None or profile is None:
            raise organization_resource_not_found()
        digests = None
        if self._settings.local_queue_enabled:
            require_queue_database(self._session)
            if self._queue_cipher is None:
                raise service_unavailable(
                    code="invitation_service_unavailable", detail="Local delivery is unavailable."
                )
            digests = issuance_digests(role_id, request, idempotency_key)
            replay = replay_invitation(
                self._session, self._context.organization.organization_id, role_id, digests
            )
            if replay is not None:
                return replay
            require_resolved_prior_delivery(
                self._session, self._context.organization.organization_id, role_id, request.email
            )
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
        if digests is not None:
            return self._create_queued(role_id, request, expiry_hours, digests, codec)
        assignment = new_assignment(allow_synthetic=self._settings.allow_synthetic_definitions)
        now = datetime.now(UTC)
        generated = codec.generate()
        invite = AssessmentInvite(
            role_profile_id=profile.id,
            assignment_json=assignment,
            email=request.email,
            token_hash=generated.token_hash,
            expires_at=now + timedelta(hours=expiry_hours),
            status=AssessmentInviteStatus.PENDING_DELIVERY,
        )
        self._session.add(invite)
        freeze_notice(invite, self._settings, self._privacy_settings, origin="issued")
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
        commit_or_flush(self._session)
        return invite

    def _create_queued(
        self,
        role_id: UUID,
        request: InvitationCreateRequest,
        expiry_hours: int,
        digests: tuple[str, str],
        codec: InviteTokenCodec,
    ) -> AssessmentInvite:
        assert self._queue_cipher is not None
        organization_id = self._context.organization.organization_id
        try:
            with self._session.begin_nested():
                generated = codec.generate()
                invite = AssessmentInvite(
                    role_profile_id=request.role_profile_id,
                    assignment_json=new_assignment(
                        allow_synthetic=self._settings.allow_synthetic_definitions
                    ),
                    email=request.email,
                    token_hash=generated.token_hash,
                    expires_at=datetime.now(UTC) + timedelta(hours=expiry_hours),
                    status=AssessmentInviteStatus.PENDING_DELIVERY,
                )
                self._session.add(invite)
                freeze_notice(invite, self._settings, self._privacy_settings, origin="issued")
                self._session.flush()
                stage_delivery(
                    self._session,
                    invite=invite,
                    organization_id=organization_id,
                    actor_id=self._context.user_id,
                    digests=digests,
                    raw_token=generated.raw_token,
                    cipher=self._queue_cipher,
                    key_id=self._settings.local_queue_key_id,
                )
        except IntegrityError:
            replay = replay_invitation(self._session, organization_id, role_id, digests)
            if replay is None:
                raise
            return replay
        commit_or_flush(self._session)
        return invite

    def revoke(self, role_id: UUID, invite_id: UUID) -> AssessmentInvite:
        """Revoke a tenant-owned invite without revealing foreign identifiers."""

        invite = self._data.get_assessment_invite_for_role(role_id, invite_id)
        if invite is None:
            raise organization_resource_not_found()
        self._session.refresh(invite, with_for_update=True)
        cancel_delivery(self._session, invite.id)
        if invite.status is AssessmentInviteStatus.REVOKED:
            commit_or_flush(self._session)
            return invite
        invite.status = AssessmentInviteStatus.REVOKED
        invite.revoked_at = datetime.now(UTC)
        invite.revoked_by = self._context.user_id
        commit_or_flush(self._session)
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
        privacy_settings: PrivacySettings,
    ) -> None:
        self._session = session
        self._settings = settings
        self._token_codec = token_codec
        self._privacy_settings = privacy_settings

    def read(self, raw_token: str) -> CandidateInviteResponse:
        """Return consent content and public context, never assessment questions."""

        candidate_invite = self._resolve(raw_token, lock=True)
        consent = self._session.scalar(
            select(CandidateConsent).where(CandidateConsent.invite_id == candidate_invite.invite.id)
        )
        if consent is None:
            freeze_notice(
                candidate_invite.invite,
                self._settings,
                self._privacy_settings,
                origin="first_presented",
            )
        response = self._response(candidate_invite, consent=consent)
        self._append_audit(candidate_invite, "candidate_invite.accessed")
        commit_or_flush(self._session)
        return response

    def record_consent(self, raw_token: str, request: ConsentRequest) -> CandidateInviteResponse:
        """Record one explicit choice; repeated identical choices are idempotent."""

        candidate_invite = self._resolve(raw_token, lock=True)
        invite = candidate_invite.invite
        existing = self._session.scalar(
            select(CandidateConsent).where(CandidateConsent.invite_id == invite.id)
        )
        snapshot = read_notice_snapshot(invite)
        if request.presented_notice_sha256 is not None:
            if snapshot is None:
                raise notice_review_required()
            try:
                require_presented_notice(
                    snapshot,
                    stored_sha256=invite.notice_sha256,
                    presented_sha256=request.presented_notice_sha256,
                )
            except NoticeReviewRequiredError as exc:
                raise notice_review_required() from exc
        if existing is not None and existing.decision is not request.decision:
            raise resource_conflict(
                code="consent_already_recorded",
                detail="A different consent decision has already been recorded.",
            )
        if existing is None:
            if snapshot is None:
                freeze_notice(
                    invite, self._settings, self._privacy_settings, origin="legacy_decision"
                )
                snapshot = read_notice_snapshot(invite)
            assert snapshot is not None
            existing = CandidateConsent(
                invite_id=invite.id,
                decision=request.decision,
                notice_version=snapshot["consent_notice"]["version"],
                presented_notice_sha256=request.presented_notice_sha256,
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
            statement = statement.with_for_update(of=AssessmentInvite).execution_options(
                populate_existing=True
            )
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

    def read_definition(self, raw_token: str) -> AssignedDefinitionResponse:
        """Serve only the invitation's frozen content after affirmative consent."""
        candidate = self._resolve(raw_token, lock=False)
        invite = require_consented_invite(self._session, candidate.invite.id)
        response = definition_response(invite.assignment_json)
        self._append_audit(candidate, "assessment_definition.accessed")
        commit_or_flush(self._session)
        return response

    def submit(self, raw_token: str, responses: AssessmentResponseSet) -> UUID:
        """Validate and score a complete response set once, after explicit consent."""

        candidate = self._resolve(raw_token, lock=True)
        invite = require_consented_invite(self._session, candidate.invite.id)
        assignment = read_assignment(invite.assignment_json)
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
        definition = assignment.definition
        try:
            scores = score_assignment(assignment, responses)
        except AssessmentScoringError as exc:
            raise resource_validation_failed(
                code="invalid_assessment_responses", detail=str(exc)
            ) from exc
        submitted_at = datetime.now(UTC)
        snapshot = read_notice_snapshot(invite)
        retention_days = (
            snapshot["retention_days"]
            if snapshot is not None
            else self._privacy_settings.retention_days
        )
        assessment = Assessment(
            invite_id=invite.id,
            consent_id=consent.id,
            submitted_at=submitted_at,
            retention_expires_at=submitted_at + timedelta(days=retention_days),
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
        snapshot = read_notice_snapshot(candidate_invite.invite)
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
            consent_notice=(
                ConsentNotice.model_validate(snapshot["consent_notice"])
                if snapshot is not None
                else current_notice(self._settings, self._privacy_settings)
            ),
            notice_sha256=candidate_invite.invite.notice_sha256,
            notice_history=notice_history(candidate_invite.invite, consent),
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


def current_notice(settings: InvitationSettings, privacy: PrivacySettings) -> ConsentNotice:
    """Render the existing notice without changing its content or defaults."""

    return ConsentNotice(
        version=settings.consent_notice_version,
        purpose=settings.purpose_statement,
        data_use=settings.data_use_statement,
        retention=settings.retention_statement.format(retention_days=privacy.retention_days),
        accommodation_contact_email=settings.accommodation_contact_email,
        privacy_contact_email=settings.privacy_contact_email,
    )


def read_notice_snapshot(invite: AssessmentInvite) -> dict[str, Any] | None:
    """Reject partial or corrupt evidence instead of replacing it with current content."""

    if all(
        value is None
        for value in (
            invite.notice_snapshot_json,
            invite.notice_sha256,
            invite.notice_snapshot_origin,
            invite.notice_snapshot_recorded_at,
        )
    ):
        return None
    try:
        if (
            invite.notice_snapshot_origin not in {"issued", "first_presented", "legacy_decision"}
            or invite.notice_snapshot_recorded_at is None
        ):
            raise InvalidNoticeSnapshotError("Invalid snapshot provenance")
        return require_presented_notice(
            invite.notice_snapshot_json,
            stored_sha256=invite.notice_sha256,
            presented_sha256=invite.notice_sha256,
        )
    except (InvalidNoticeSnapshotError, NoticeReviewRequiredError) as exc:
        raise resource_conflict(
            code="notice_snapshot_invalid", detail="The saved notice is unavailable."
        ) from exc


def freeze_notice(
    invite: AssessmentInvite,
    settings: InvitationSettings,
    privacy: PrivacySettings,
    *,
    origin: str,
) -> None:
    """Set the first snapshot only while issuing or holding the invitation lock."""

    if read_notice_snapshot(invite) is not None:
        return
    snapshot = build_notice_snapshot(
        current_notice(settings, privacy).model_dump(mode="json"),
        retention_days=privacy.retention_days,
    )
    invite.notice_snapshot_json = snapshot
    invite.notice_sha256 = notice_snapshot_hash(snapshot)
    invite.notice_snapshot_origin = origin
    invite.notice_snapshot_recorded_at = datetime.now(UTC)


def notice_history(invite: AssessmentInvite, consent: CandidateConsent | None) -> NoticeHistory:
    """Describe protocol evidence without claiming that a person read the notice."""

    if consent is None:
        return "not_recorded"
    if invite.notice_snapshot_json is None:
        return "legacy_unknown"
    return "digest_recorded" if consent.presented_notice_sha256 is not None else "legacy_unverified"


def notice_review_required() -> Exception:
    """Require explicit review when a client advertises different notice content."""

    return resource_conflict(
        code="notice_review_required", detail="Reload and review the notice before deciding."
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

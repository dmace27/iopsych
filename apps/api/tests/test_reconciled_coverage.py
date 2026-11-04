"""Reconciled invitation boundaries reject malformed input without side effects."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.auth.errors import AccessProblemError
from app.database.models import (
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    InvitationDeliveryStatus,
    ProviderInvitationDelivery,
)
from app.database.seed import ALPHA_PROFILE_ID, ALPHA_ROLE_ID
from app.invitations.outbox import stop_delivery
from app.invitations.schemas import InvitationCreateRequest
from app.invitations.service import InternalInvitationService, read_notice_snapshot
from app.invitations.tokens import InviteTokenCodec
from tests.test_defensive_service_branches import context, snapshot
from tests.test_invitations import INVITE_SECRET
from tests.test_notice_snapshot_api import candidate, legacy
from tests.test_provider_invitations import RecordingDelivery, invitation_settings


@pytest.mark.parametrize("key", ["", "short", "x" * 129, "spaces are forbidden", "é" * 16])
def test_provider_rejects_invalid_idempotency_key_before_writes(
    seeded_session: Session, key: str
) -> None:
    delivery = RecordingDelivery()
    service = InternalInvitationService(
        seeded_session, context(), invitation_settings(), InviteTokenCodec(INVITE_SECRET), delivery
    )
    before = snapshot(seeded_session)
    with pytest.raises(AccessProblemError) as error:
        service.create(
            ALPHA_ROLE_ID,
            InvitationCreateRequest(
                role_profile_id=ALPHA_PROFILE_ID,
                email="synthetic@example.invalid",
                request_id=uuid4(),
            ),
            idempotency_key=key,
        )
    assert (error.value.status, error.value.code) == (422, "invalid_idempotency_key")
    assert snapshot(seeded_session) == before
    assert not seeded_session.new and not seeded_session.dirty
    assert delivery.messages == []


@pytest.mark.parametrize("status", [AssessmentInviteStatus.REVOKED, AssessmentInviteStatus.EXPIRED])
def test_stopping_delivery_preserves_terminal_invitation_history(
    seeded_session: Session, status: AssessmentInviteStatus
) -> None:
    adapter = RecordingDelivery()
    service = InternalInvitationService(
        seeded_session, context(), invitation_settings(), InviteTokenCodec(INVITE_SECRET), adapter
    )
    invite = service.create(
        ALPHA_ROLE_ID,
        InvitationCreateRequest(
            role_profile_id=ALPHA_PROFILE_ID,
            email="synthetic@example.invalid",
            request_id=uuid4(),
        ),
    )
    delivery = seeded_session.scalar(
        select(ProviderInvitationDelivery).where(ProviderInvitationDelivery.invite_id == invite.id)
    )
    assert delivery is not None and delivery.encrypted_message is not None
    original_revoked_at = datetime.now(UTC) - timedelta(hours=1)
    invite.status = status
    invite.revoked_at = original_revoked_at if status is AssessmentInviteStatus.REVOKED else None
    seeded_session.commit()
    invitation_id, delivery_id = invite.id, delivery.id
    stop_delivery(
        seeded_session,
        delivery,
        invite,
        InvitationDeliveryStatus.REISSUE_REQUIRED,
        "retry_window_closed",
        datetime.now(UTC),
    )
    seeded_session.commit()
    seeded_session.expire_all()
    preserved = seeded_session.get(AssessmentInvite, invitation_id)
    stopped = seeded_session.get(ProviderInvitationDelivery, delivery_id)
    assert preserved is not None and preserved.status is status
    assert preserved.revoked_at == (
        original_revoked_at if status is AssessmentInviteStatus.REVOKED else None
    )
    assert stopped is not None and stopped.status is InvitationDeliveryStatus.REISSUE_REQUIRED
    assert stopped.encrypted_message is None
    assert stopped.last_error_code == "retry_window_closed"
    audit = seeded_session.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_id == invitation_id,
            AuditEvent.event_type == "invitation_delivery.stopped",
        )
    )
    assert audit is not None
    assert audit.metadata_json == {
        "delivery_id": str(delivery_id),
        "status": "reissue_required",
        "attempt_count": 0,
    }
    assert adapter.messages == []


def test_provider_requires_request_id_without_header(seeded_session: Session) -> None:
    delivery = RecordingDelivery()
    service = InternalInvitationService(
        seeded_session, context(), invitation_settings(), InviteTokenCodec(INVITE_SECRET), delivery
    )
    before = snapshot(seeded_session)
    with pytest.raises(AccessProblemError) as error:
        service.create(
            ALPHA_ROLE_ID,
            InvitationCreateRequest(
                role_profile_id=ALPHA_PROFILE_ID, email="synthetic@example.invalid"
            ),
        )
    assert (error.value.status, error.value.code) == (422, "invitation_request_id_required")
    assert snapshot(seeded_session) == before
    assert not seeded_session.new and not seeded_session.dirty
    assert delivery.messages == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("notice_snapshot_origin", "untrusted"),
        ("notice_snapshot_origin", None),
        ("notice_snapshot_recorded_at", None),
    ],
)
def test_partial_notice_provenance_fails_closed_without_replacing_evidence(
    seeded_session: Session, field: str, value: str | None
) -> None:
    invite, token = legacy(seeded_session)
    candidate(seeded_session).read(token)
    assert read_notice_snapshot(invite) is not None
    before = snapshot(seeded_session)
    set_committed_value(invite, field, value)
    with pytest.raises(AccessProblemError) as error:
        read_notice_snapshot(invite)
    assert (error.value.status, error.value.code) == (409, "notice_snapshot_invalid")
    assert getattr(invite, field) == value
    assert snapshot(seeded_session) == before
    assert not seeded_session.new and not seeded_session.dirty

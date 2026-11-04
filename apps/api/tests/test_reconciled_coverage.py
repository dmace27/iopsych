"""Reconciled invitation boundaries reject malformed input without side effects."""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.auth.errors import AccessProblemError
from app.database.seed import ALPHA_PROFILE_ID, ALPHA_ROLE_ID
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

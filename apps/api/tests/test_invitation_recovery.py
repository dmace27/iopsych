"""Failure and replay matrix for the proposed, unwired recovery policy."""

from datetime import UTC, datetime, timedelta

import pytest

from app.invitations.recovery import DeliveryEvent, DeliveryState, decide_delivery

NOW = datetime(2026, 11, 4, tzinfo=UTC)
EXPIRY = NOW + timedelta(minutes=15)
GRACE = NOW + timedelta(seconds=30)


@pytest.mark.parametrize("event", list(DeliveryEvent))
@pytest.mark.parametrize(
    "state",
    [DeliveryState.SENT, DeliveryState.UNCERTAIN, DeliveryState.CANCELLED, DeliveryState.EXPIRED],
)
def test_terminal_replay_never_sends_or_restores_credentials(
    state: DeliveryState, event: DeliveryEvent
) -> None:
    result = decide_delivery(
        state=state,
        event=event,
        now=NOW,
        credential_expires_at=EXPIRY,
        invitation_eligible=True,
    )
    assert result.state is state
    assert result.delete_credential
    assert not result.increment_attempt


@pytest.mark.parametrize("event", list(DeliveryEvent))
@pytest.mark.parametrize("state", [DeliveryState.QUEUED, DeliveryState.SENDING])
def test_revocation_wins_even_over_late_acceptance(
    state: DeliveryState, event: DeliveryEvent
) -> None:
    result = decide_delivery(
        state=state,
        event=event,
        now=NOW,
        credential_expires_at=EXPIRY,
        invitation_eligible=False,
    )
    assert result.state is DeliveryState.CANCELLED
    assert result.delete_credential
    assert not result.increment_attempt


@pytest.mark.parametrize("event", list(DeliveryEvent))
@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (DeliveryState.QUEUED, DeliveryState.EXPIRED),
        (DeliveryState.SENDING, DeliveryState.UNCERTAIN),
    ],
)
def test_exact_expiry_prevents_send_but_preserves_possible_acceptance(
    state: DeliveryState, expected: DeliveryState, event: DeliveryEvent
) -> None:
    result = decide_delivery(
        state=state,
        event=event,
        now=EXPIRY,
        credential_expires_at=EXPIRY,
        invitation_eligible=True,
    )
    if event is DeliveryEvent.CANCEL:
        expected = DeliveryState.CANCELLED
    assert result.state is expected
    assert result.delete_credential
    assert not result.increment_attempt


@pytest.mark.parametrize("completion_committed", [False, True])
def test_acceptance_then_completion_commit_or_audit_failure_is_not_retryable(
    completion_committed: bool,
) -> None:
    claim = decide_delivery(
        state=DeliveryState.QUEUED,
        event=DeliveryEvent.CLAIM,
        now=NOW,
        credential_expires_at=EXPIRY,
        invitation_eligible=True,
    )
    assert claim.increment_attempt
    assert not claim.delete_credential
    persisted = claim.state  # Simulate successfully committed claim before SMTP.
    accepted = decide_delivery(
        state=persisted,
        event=DeliveryEvent.ACCEPTED,
        now=NOW,
        credential_expires_at=EXPIRY,
        invitation_eligible=True,
    )
    assert accepted.state is DeliveryState.SENT
    assert accepted.delete_credential
    if completion_committed:
        persisted = accepted.state
    recovered = decide_delivery(
        state=persisted,
        event=DeliveryEvent.RECOVER,
        now=GRACE,
        credential_expires_at=EXPIRY,
        invitation_eligible=True,
        recovery_after=GRACE,
    )
    assert recovered.state is (
        DeliveryState.SENT if completion_committed else DeliveryState.UNCERTAIN
    )
    assert recovered.delete_credential
    replay = decide_delivery(
        state=recovered.state,
        event=DeliveryEvent.CLAIM,
        now=GRACE,
        credential_expires_at=EXPIRY,
        invitation_eligible=True,
    )
    assert not replay.increment_attempt


def test_duplicate_claim_and_early_recovery_do_not_repeat_send() -> None:
    for event in (DeliveryEvent.CLAIM, DeliveryEvent.RECOVER):
        result = decide_delivery(
            state=DeliveryState.SENDING,
            event=event,
            now=GRACE - timedelta(microseconds=1),
            credential_expires_at=EXPIRY,
            invitation_eligible=True,
            recovery_after=GRACE,
        )
        assert result.state is DeliveryState.SENDING
        assert not result.increment_attempt
        assert not result.delete_credential


def test_timeout_after_possible_acceptance_requires_explicit_reissue() -> None:
    result = decide_delivery(
        state=DeliveryState.SENDING,
        event=DeliveryEvent.UNKNOWN,
        now=NOW,
        credential_expires_at=EXPIRY,
        invitation_eligible=True,
    )
    assert result.state is DeliveryState.UNCERTAIN
    assert result.delete_credential
    assert not result.increment_attempt


def test_cancel_queued_credential_before_send() -> None:
    result = decide_delivery(
        state=DeliveryState.QUEUED,
        event=DeliveryEvent.CANCEL,
        now=NOW,
        credential_expires_at=EXPIRY,
        invitation_eligible=True,
    )
    assert result.state is DeliveryState.CANCELLED
    assert result.delete_credential


def test_queued_recovery_leaves_job_available_for_a_future_claim() -> None:
    result = decide_delivery(
        state=DeliveryState.QUEUED,
        event=DeliveryEvent.RECOVER,
        now=NOW,
        credential_expires_at=EXPIRY,
        invitation_eligible=True,
    )
    assert result.state is DeliveryState.QUEUED
    assert not result.increment_attempt
    assert not result.delete_credential


@pytest.mark.parametrize("event", [DeliveryEvent.ACCEPTED, DeliveryEvent.UNKNOWN])
def test_no_provider_outcome_without_claim(event: DeliveryEvent) -> None:
    with pytest.raises(ValueError, match="committed claim"):
        decide_delivery(
            state=DeliveryState.QUEUED,
            event=event,
            now=NOW,
            credential_expires_at=EXPIRY,
            invitation_eligible=True,
        )


def test_recovery_requires_persisted_claim_deadline() -> None:
    with pytest.raises(ValueError, match="persisted deadline"):
        decide_delivery(
            state=DeliveryState.SENDING,
            event=DeliveryEvent.RECOVER,
            now=NOW,
            credential_expires_at=EXPIRY,
            invitation_eligible=True,
        )


@pytest.mark.parametrize("field", ["now", "credential_expires_at", "recovery_after"])
def test_reject_ambiguous_timestamps(field: str) -> None:
    values = {"now": NOW, "credential_expires_at": EXPIRY, "recovery_after": GRACE}
    values[field] = values[field].replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        decide_delivery(
            state=DeliveryState.SENDING,
            event=DeliveryEvent.RECOVER,
            invitation_eligible=True,
            **values,
        )


def test_invalid_state_event_and_eligibility_fail_closed() -> None:
    with pytest.raises(ValueError, match="invalid delivery transition"):
        decide_delivery(
            state="queued",  # type: ignore[arg-type]
            event=DeliveryEvent.CLAIM,
            now=NOW,
            credential_expires_at=EXPIRY,
            invitation_eligible=True,
        )
    with pytest.raises(ValueError, match="invalid delivery transition"):
        decide_delivery(
            state=DeliveryState.QUEUED,
            event="claim",  # type: ignore[arg-type]
            now=NOW,
            credential_expires_at=EXPIRY,
            invitation_eligible=True,
        )
    with pytest.raises(ValueError, match="eligibility must be explicit"):
        decide_delivery(
            state=DeliveryState.QUEUED,
            event=DeliveryEvent.CLAIM,
            now=NOW,
            credential_expires_at=EXPIRY,
            invitation_eligible=1,  # type: ignore[arg-type]
        )

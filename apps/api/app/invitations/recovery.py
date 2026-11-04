"""Token-free delivery recovery policy; not a queue or a runtime delivery path.

Callers must lock/re-read persisted state and atomically commit each decision with
its audit and credential deletion. Only a successfully committed CLAIM permits one
send. Never send on the strength of a returned decision before that commit.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DeliveryState(StrEnum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    UNCERTAIN = "uncertain"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class DeliveryEvent(StrEnum):
    CLAIM = "claim"
    ACCEPTED = "accepted"
    UNKNOWN = "unknown"
    RECOVER = "recover"
    CANCEL = "cancel"


@dataclass(frozen=True)
class DeliveryDecision:
    """Persistence instructions containing no credential or recipient data."""

    state: DeliveryState
    delete_credential: bool
    increment_attempt: bool = False


_TERMINAL = frozenset(
    {
        DeliveryState.SENT,
        DeliveryState.UNCERTAIN,
        DeliveryState.CANCELLED,
        DeliveryState.EXPIRED,
    }
)


def decide_delivery(
    *,
    state: DeliveryState,
    event: DeliveryEvent,
    now: datetime,
    credential_expires_at: datetime,
    invitation_eligible: bool,
    recovery_after: datetime | None = None,
) -> DeliveryDecision:
    """Plan a fail-closed transition using authoritative locked database values.

    ``recovery_after`` is the persisted claim start plus operational grace, not a
    fresh deadline on each poll. A crash or any unconfirmed acceptance is terminal:
    SMTP cannot prove that retrying will not duplicate a message. Explicit reissue
    must revoke the old invite and use a new delivery/idempotency key.
    """
    if not isinstance(state, DeliveryState) or not isinstance(event, DeliveryEvent):
        raise ValueError("invalid delivery transition")
    for instant in (now, credential_expires_at, recovery_after):
        if instant is not None and instant.utcoffset() is None:
            raise ValueError("delivery timestamps must be timezone-aware")
    if type(invitation_eligible) is not bool:
        raise ValueError("invitation eligibility must be explicit")
    if state in _TERMINAL:
        return DeliveryDecision(state, delete_credential=True)
    if event is DeliveryEvent.CANCEL or not invitation_eligible:
        return DeliveryDecision(DeliveryState.CANCELLED, delete_credential=True)
    if now >= credential_expires_at:
        # A previously claimed send may already have reached the SMTP sink.
        expired_state = (
            DeliveryState.UNCERTAIN if state is DeliveryState.SENDING else DeliveryState.EXPIRED
        )
        return DeliveryDecision(expired_state, delete_credential=True)
    if state is DeliveryState.QUEUED:
        if event is DeliveryEvent.CLAIM:
            return DeliveryDecision(
                DeliveryState.SENDING, delete_credential=False, increment_attempt=True
            )
        if event is DeliveryEvent.RECOVER:
            return DeliveryDecision(state, delete_credential=False)
        raise ValueError("delivery outcome requires a committed claim")
    if event is DeliveryEvent.ACCEPTED:
        return DeliveryDecision(DeliveryState.SENT, delete_credential=True)
    if event is DeliveryEvent.UNKNOWN:
        return DeliveryDecision(DeliveryState.UNCERTAIN, delete_credential=True)
    if event is DeliveryEvent.RECOVER:
        if recovery_after is None:
            raise ValueError("sending recovery requires a persisted deadline")
        if now >= recovery_after:
            return DeliveryDecision(DeliveryState.UNCERTAIN, delete_credential=True)
    # Duplicate claim/poll cannot authorize another send or increment attempts.
    return DeliveryDecision(state, delete_credential=False)

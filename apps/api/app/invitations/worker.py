"""Run one bounded encrypted invitation-delivery batch for an operator scheduler."""

from sqlalchemy.exc import SQLAlchemyError

from app.database.session import create_database_engine, create_session_factory
from app.invitations.config import InvitationSettings
from app.invitations.delivery import UnconfiguredInvitationDelivery
from app.invitations.logging import install_invite_token_log_filter
from app.invitations.outbox import process_delivery_batch
from app.invitations.provider import build_invitation_delivery


def main() -> None:
    """Keep operator output to counts and safe errors, never email bodies or credentials."""
    install_invite_token_log_filter()
    settings = InvitationSettings()
    adapter = build_invitation_delivery(settings)
    if isinstance(adapter, UnconfiguredInvitationDelivery):
        raise SystemExit("Invitation delivery is not configured; queued work was not changed.")
    engine = create_database_engine()
    try:
        count = process_delivery_batch(create_session_factory(engine), settings, adapter)
    except (SQLAlchemyError, ValueError):
        raise SystemExit(
            "Delivery batch failed. Check configuration/database and retry the same batch."
        ) from None
    finally:
        engine.dispose()
    print(f"Invitation delivery batch complete: {count} processed")


if __name__ == "__main__":  # pragma: no cover
    main()

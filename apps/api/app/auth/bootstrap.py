"""Controlled, one-time organization/administrator bootstrap for operators."""

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.users import UserInput
from app.database.models import AuditEvent, InternalUserRole, Organization, User
from app.database.session import create_database_engine, create_session_factory, session_scope


def bootstrap_administrator(
    session: Session, *, slug: str, organization_name: str, account: UserInput
) -> User:
    """Create the first administrator atomically; never overwrite an existing tenant."""

    if session.scalar(select(Organization.id).where(Organization.slug == slug)) is not None:
        raise ValueError("Organization already exists; use its administrator account management.")
    organization = Organization(slug=slug, name=organization_name)
    session.add(organization)
    session.flush()
    user = User(
        organization_id=organization.id,
        **account.model_copy(update={"role": InternalUserRole.ADMIN}).model_dump(),
    )
    session.add(user)
    session.flush()
    session.add(
        AuditEvent(
            organization_id=organization.id,
            actor_id=user.id,
            event_type="internal_user.bootstrap",
            entity_type="user",
            entity_id=user.id,
            metadata_json={"source": "operator_cli"},
        )
    )
    return user


def main() -> None:  # pragma: no cover - thin operator CLI around tested transaction.
    """Bootstrap with database operator credentials and a known Auth0 subject."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--organization-name", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    engine = create_database_engine()
    try:
        with session_scope(create_session_factory(engine)) as session:
            bootstrap_administrator(
                session,
                slug=args.slug,
                organization_name=args.organization_name,
                account=UserInput(
                    auth_subject=args.subject,
                    email=args.email,
                    name=args.name,
                    role=InternalUserRole.ADMIN,
                ),
            )
    finally:
        engine.dispose()
    print("Organization and administrator created. Sign in through the configured provider.")


if __name__ == "__main__":  # pragma: no cover
    main()

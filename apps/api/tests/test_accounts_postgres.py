"""Verify account locking and populated upgrades on a disposable PostgreSQL schema."""

import asyncio
from threading import Barrier
from uuid import UUID

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth import users as account_routes
from app.auth.config import AuthenticationSettings
from app.auth.context import AuthorizationContext
from app.database.models import InternalUserRole, User
from app.database.seed import ALPHA_ORGANIZATION_ID, ALPHA_USER_ID
from app.main import create_app
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET, make_token
from tests.test_database_migrations import alembic_config
from tests.test_reports_postgres import postgres_report_factory as postgres_report_factory


@pytest.fixture
def anyio_backend() -> str:
    """Run concurrent HTTP clients on asyncio."""
    return "asyncio"


@pytest.mark.anyio
async def test_concurrent_administrators_cannot_remove_all_access(
    postgres_report_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent demotions serialize and recheck the waiting actor's current role."""
    factory = postgres_report_factory
    both_authorized = Barrier(2)
    lock = account_routes._lock_administrator

    def synchronized_lock(session: Session, context: AuthorizationContext) -> None:
        """Force both requests past initial authorization before either mutates."""
        both_authorized.wait(timeout=5)
        lock(session, context)

    monkeypatch.setattr(account_routes, "_lock_administrator", synchronized_lock)
    second_id = UUID("10000000-0000-4000-8000-000000000099")
    with factory.begin() as session:
        first = session.get(User, ALPHA_USER_ID)
        assert first is not None
        first.role = InternalUserRole.ADMIN
        session.add(
            User(
                id=second_id,
                organization_id=ALPHA_ORGANIZATION_ID,
                auth_subject="second-admin",
                email="second@alpha.example.invalid",
                name="Second Admin",
                role=InternalUserRole.ADMIN,
            )
        )
    application = create_app(
        session_factory=factory,
        authentication_settings=AuthenticationSettings(
            jwt_secret=SECRET,
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:

        async def demote(subject: str, target: UUID) -> int:
            """Submit one independently authenticated permission change."""
            token = make_token(
                claims={"sub": subject, "organization_id": str(ALPHA_ORGANIZATION_ID)}
            )
            response = await client.patch(
                f"/v1/users/{target}",
                json={"role": "recruiter", "is_active": True},
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.status_code

        results = await asyncio.gather(
            demote("synthetic-alpha-recruiter", second_id), demote("second-admin", ALPHA_USER_ID)
        )
        assert sorted(results) == [200, 403]
    with factory() as session:
        administrators = list(
            session.scalars(
                select(User).where(
                    User.organization_id == ALPHA_ORGANIZATION_ID,
                    User.role == InternalUserRole.ADMIN,
                    User.is_active.is_(True),
                )
            )
        )
        assert len(administrators) == 1


def test_active_user_upgrade_preserves_populated_postgres(
    postgres_report_factory: sessionmaker[Session],
) -> None:
    """Upgrade the prior schema with existing identities and preserve their access."""
    factory = postgres_report_factory
    with factory() as session:
        engine = session.get_bind()
        assert isinstance(engine, Engine)
        database_url = engine.url.render_as_string(hide_password=False)
    config = alembic_config(database_url)
    command.downgrade(config, "20260929_0007")
    command.upgrade(config, "head")
    with factory() as session:
        user = session.get(User, ALPHA_USER_ID)
        assert user is not None
        assert user.is_active is True
        assert user.auth_subject == "synthetic-alpha-recruiter"
        assert user.role == InternalUserRole.RECRUITER

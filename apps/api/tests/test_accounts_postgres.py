"""Real PostgreSQL serialization checks on an explicitly supplied isolated database."""

import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.accounts.schemas import AccountUpdateRequest
from app.accounts.service import update_account
from app.auth.context import AuthorizationContext, OrganizationScope
from app.auth.errors import AccessProblemError
from app.database.base import Base
from app.database.models import AuditEvent, InternalUserRole, Organization, User
from app.database.session import REQUEST_TRANSACTION_INFO_KEY, create_session_factory

TENANT = UUID("20000000-0000-4000-8000-000000000001")
A = UUID("20000000-0000-4000-8000-000000000002")
B = UUID("20000000-0000-4000-8000-000000000003")
C = UUID("20000000-0000-4000-8000-000000000004")


@pytest.fixture
def account_pg() -> Generator[sessionmaker[Session]]:
    raw = os.environ.get("ACCOUNT_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("Requires explicit ACCOUNT_TEST_POSTGRES_URL; ambient databases are never used")
    url = make_url(raw)
    if url.host != "127.0.0.1" or url.port != 5594 or url.database != "iopsych_access":
        raise ValueError("Account tests require their own local database on port 5594")
    schema = f"accounts_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url.update_query_dict({"options": f"-csearch_path={schema}"}))
    try:
        Base.metadata.create_all(engine)
        factory = create_session_factory(engine)
        with factory() as session:
            session.add(Organization(id=TENANT, slug="accounts-test", name="Synthetic Accounts"))
            session.flush()
            for user_id in [A, B, C]:
                session.add(
                    User(
                        id=user_id,
                        organization_id=TENANT,
                        email=f"{user_id}@example.invalid",
                        name="Synthetic",
                        auth_subject=str(user_id),
                        role=InternalUserRole.RECRUITER if user_id == C else InternalUserRole.ADMIN,
                    )
                )
            session.commit()
        yield factory
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def context(user: User) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user.id,
        organization=OrganizationScope(user.organization_id),
        email=user.email,
        name=user.name,
        role=user.role,
    )


@pytest.mark.parametrize("change", [{"is_active": False}, {"role": "recruiter"}])
def test_parallel_admin_removal_retains_one_admin(
    account_pg: sessionmaker[Session], change: dict[str, object]
) -> None:
    barrier = Barrier(2)

    def remove(actor_id: UUID, target: UUID) -> int:
        with account_pg() as session:
            actor = session.get(User, actor_id)
            assert actor is not None
            auth = context(actor)
            barrier.wait(timeout=10)
            try:
                update_account(
                    session,
                    auth,
                    target,
                    AccountUpdateRequest.model_validate({"expected_version": 1, **change}),
                )
                return 200
            except AccessProblemError as exc:
                session.rollback()
                return exc.status

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(remove, A, B)
        second = executor.submit(remove, B, A)
        assert sorted([first.result(timeout=15), second.result(timeout=15)]) in [
            [200, 401],
            [200, 403],
        ]
    with account_pg() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == InternalUserRole.ADMIN, User.is_active.is_(True))
            )
            == 1
        )
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1


@pytest.mark.parametrize(
    "change,status", [({"is_active": False}, 401), ({"role": "recruiter"}, 403)]
)
def test_stale_admin_cannot_escalate_after_parallel_revocation(
    account_pg: sessionmaker[Session], change: dict[str, object], status: int
) -> None:
    loaded = Event()
    proceed = Event()

    def escalate() -> int:
        with account_pg() as session:
            actor = session.get(User, B)
            assert actor is not None
            stale_context = context(actor)
            loaded.set()
            assert proceed.wait(timeout=10)
            try:
                update_account(
                    session,
                    stale_context,
                    C,
                    AccountUpdateRequest(expected_version=1, role=InternalUserRole.ADMIN),
                )
                return 200
            except AccessProblemError as exc:
                session.rollback()
                return exc.status

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(escalate)
        assert loaded.wait(timeout=10)
        with account_pg() as session:
            session.info[REQUEST_TRANSACTION_INFO_KEY] = True
            actor = session.get(User, A)
            assert actor is not None
            update_account(
                session,
                context(actor),
                B,
                AccountUpdateRequest.model_validate({"expected_version": 1, **change}),
            )
            proceed.set()
            session.commit()
        assert future.result(timeout=15) == status
    with account_pg() as session:
        target = session.get(User, C)
        assert (
            target is not None and target.role == InternalUserRole.RECRUITER and target.version == 1
        )
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1


def test_access_audit_is_database_immutable(account_pg: sessionmaker[Session]) -> None:
    with account_pg() as session:
        actor = session.get(User, A)
        assert actor is not None
        update_account(
            session, context(actor), C, AccountUpdateRequest(expected_version=1, is_active=False)
        )
    for sql in ["UPDATE audit_events SET event_type='changed'", "DELETE FROM audit_events"]:
        with account_pg() as session, pytest.raises(DBAPIError, match="immutable"):
            session.execute(text(sql))
            session.commit()


def test_populated_access_migration_preserves_old_accounts(
    account_pg: sessionmaker[Session],
) -> None:
    """Exercise this revision independently while the predecessor is integrated."""

    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).parents[1] / "alembic/versions/20261104_0010_user_access.py"
    spec = importlib.util.spec_from_file_location("account_access_revision", path)
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    with account_pg() as session:
        connection = session.connection()
        original = list(
            connection.execute(
                text(
                    "SELECT id,organization_id,email,name,auth_subject,role,created_at "
                    "FROM users ORDER BY id"
                )
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            revision.downgrade()
            revision.upgrade()
        preserved = list(
            connection.execute(
                text(
                    "SELECT id,organization_id,email,name,auth_subject,role,created_at "
                    "FROM users ORDER BY id"
                )
            )
        )
        assert preserved == original
        assert list(connection.execute(text("SELECT is_active,version FROM users"))) == [
            (True, 1),
            (True, 1),
            (True, 1),
        ]
        session.commit()
    with account_pg() as session, pytest.raises(DBAPIError):
        session.execute(text("UPDATE users SET version=0"))
        session.commit()

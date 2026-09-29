"""SQLAlchemy engine and transaction helpers."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.config import DatabaseSettings

REQUEST_SESSION_STATE_ATTRIBUTE = "database_session"
REQUEST_TRANSACTION_INFO_KEY = "request_managed_transaction"


def create_database_engine(settings: DatabaseSettings | None = None) -> Engine:
    """Create an engine without opening a connection eagerly."""

    resolved = settings or DatabaseSettings()
    url = make_url(resolved.database_url)
    options: dict[str, object] = {
        "echo": resolved.database_echo,
        "pool_pre_ping": True,
    }
    if url.get_backend_name() == "sqlite" and url.database in (None, "", ":memory:"):
        # A single connection keeps in-memory SQLite visible to FastAPI's
        # worker threads during integration tests.
        options["connect_args"] = {"check_same_thread": False}
        options["poolclass"] = StaticPool
    elif url.get_backend_name() != "sqlite":
        options["pool_size"] = resolved.database_pool_size
    return create_engine(url, **options)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create sessions that retain loaded state after commits."""

    return sessionmaker(bind=engine, expire_on_commit=False)


def commit_or_flush(session: Session) -> None:
    """Finish a service write without breaking request-level atomicity.

    API requests are committed once by the audit middleware so the domain
    mutation and its required audit event succeed or roll back together.
    Direct service callers retain the historical commit-on-success behavior.
    """

    if session.info.get(REQUEST_TRANSACTION_INFO_KEY):
        session.flush()
    else:
        session.commit()


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Generator[Session]:
    """Commit successful work and roll back failures atomically."""

    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

"""SQLAlchemy engine and transaction helpers."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.database.config import DatabaseSettings


def create_database_engine(settings: DatabaseSettings | None = None) -> Engine:
    """Create an engine without opening a connection eagerly."""

    resolved = settings or DatabaseSettings()
    url = make_url(resolved.database_url)
    options: dict[str, object] = {
        "echo": resolved.database_echo,
        "pool_pre_ping": True,
    }
    if url.get_backend_name() != "sqlite":
        options["pool_size"] = resolved.database_pool_size
    return create_engine(url, **options)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create sessions that retain loaded state after commits."""

    return sessionmaker(bind=engine, expire_on_commit=False)


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

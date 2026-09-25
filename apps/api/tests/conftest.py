"""Database fixtures shared by API tests."""

from collections.abc import Generator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.config import DatabaseSettings
from app.database.models import Organization  # noqa: F401 - registers all model tables.
from app.database.seed import seed_database
from app.database.session import create_database_engine, create_session_factory


@pytest.fixture
def database_engine() -> Generator[Engine]:
    """Provide a foreign-key-enforcing in-memory SQLite database."""

    engine = create_database_engine(DatabaseSettings(database_url="sqlite+pysqlite:///:memory:"))
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def seeded_session(database_engine: Engine) -> Generator[Session]:
    """Provide the deterministic two-tenant dataset in one transaction."""

    factory = create_session_factory(database_engine)
    with factory() as session:
        seed_database(session)
        session.commit()
        yield session

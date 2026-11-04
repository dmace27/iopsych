"""Focused engine budgets and migration-aware readiness tests."""

import os
import socket
import threading
from collections.abc import Generator
from pathlib import Path
from time import monotonic
from unittest.mock import patch

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, TimeoutError

from alembic import command
from app.database.config import API_ROOT, DatabaseSettings
from app.database.session import create_database_engine, create_session_factory
from app.main import create_app
from app.runtime import health


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("database_connect_timeout_seconds", 1),
        ("database_connect_timeout_seconds", 61),
        ("database_pool_timeout_seconds", 0),
        ("database_pool_timeout_seconds", 61),
        ("database_pool_timeout_seconds", float("nan")),
        ("database_pool_timeout_seconds", float("inf")),
        ("database_max_overflow", -1),
        ("database_max_overflow", 51),
        ("database_statement_timeout_ms", 0),
        ("database_statement_timeout_ms", 300_001),
        ("database_lock_timeout_ms", 0),
        ("database_lock_timeout_ms", 60_001),
    ],
)
def test_budget_validation(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        DatabaseSettings.model_validate({field: value})


def test_budget_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "4")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "0.25")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "0")
    monkeypatch.setenv("DATABASE_STATEMENT_TIMEOUT_MS", "600")
    monkeypatch.setenv("DATABASE_LOCK_TIMEOUT_MS", "100")
    settings = DatabaseSettings()
    assert settings.database_connect_timeout_seconds == 4
    assert settings.database_pool_timeout_seconds == 0.25
    assert settings.database_max_overflow == 0
    assert settings.database_statement_timeout_ms == 600
    assert settings.database_lock_timeout_ms == 100


@pytest.mark.parametrize(
    "query",
    [
        "connect_timeout=5",
        "options=a&options=b",
        "options=-csearch_path%3Dsynthetic%5C",
    ],
)
def test_ambiguous_options_fail_without_configuration_details(query: str) -> None:
    with pytest.raises(ValueError) as error:
        create_database_engine(
            DatabaseSettings(
                database_url=f"postgresql+psycopg://hidden:secret@localhost/db?{query}"
            )
        )
    assert str(error.value) in {
        "Conflicting database connection options",
        "Invalid database connection options",
    }


def test_startup_options_preserve_search_path_and_bound_defaults() -> None:
    url = make_url("postgresql+psycopg://localhost/db").update_query_dict(
        {"options": "-csearch_path=synthetic -c statement_timeout=0", "application_name": "test"}
    )
    with patch("app.database.session.create_engine") as create:
        create_database_engine(DatabaseSettings(database_url=url.render_as_string()))
    args = create.call_args.kwargs
    assert args["pool_size"] == 5
    assert args["max_overflow"] == 10
    assert args["pool_timeout"] == 5
    assert args["connect_args"] == {
        "connect_timeout": 5,
        "options": (
            "-csearch_path=synthetic -c statement_timeout=0"
            " -c statement_timeout=15000 -c lock_timeout=3000"
        ),
    }
    assert create.call_args.args[0].query == {"application_name": "test"}


@pytest.mark.parametrize("state", ["missing", "empty", "stale", "extra", "current"])
def test_readiness_schema_states(database_engine: Engine, state: str) -> None:
    if state != "missing":
        with database_engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
            versions = health.expected_schema_heads() if state in {"current", "extra"} else set()
            if state in {"stale", "extra"}:
                versions.add("stale-synthetic")
            for version in versions:
                connection.execute(text("INSERT INTO alembic_version VALUES (:v)"), {"v": version})
    with TestClient(create_app(session_factory=create_session_factory(database_engine))) as client:
        response = client.get("/ready")
        assert response.status_code == (200 if state == "current" else 503)
        assert response.json() == {
            "status": "ready" if state == "current" else "unavailable",
            "service": "api",
        }
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("assets", ["missing", "empty", "broken"])
def test_readiness_requires_packaged_assets(
    database_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, assets: str
) -> None:
    monkeypatch.setattr(health, "API_ROOT", tmp_path)
    if assets != "missing":
        versions = tmp_path / "alembic" / "versions"
        versions.mkdir(parents=True)
        if assets == "broken":
            (versions / "broken.py").write_text("invalid python here", encoding="utf-8")
    with TestClient(create_app(session_factory=create_session_factory(database_engine))) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "service": "api"}


@pytest.fixture
def postgres_url() -> str:
    url = os.environ.get("READINESS_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("Set READINESS_TEST_DATABASE_URL to an isolated synthetic PostgreSQL database")
    parsed = make_url(url)
    if parsed.host != "127.0.0.1" or parsed.port != 5573 or parsed.database != "iopsych_readiness":
        pytest.fail("Readiness integration tests require the allocated isolated database")
    return url


@pytest.fixture
def postgres_engine(postgres_url: str) -> Generator[Engine]:
    url = make_url(postgres_url).update_query_dict(
        {"options": "-csearch_path=readiness_synthetic -c statement_timeout=0 -c lock_timeout=0"}
    )
    engine = create_database_engine(
        DatabaseSettings(
            database_url=url.render_as_string(hide_password=False),
            database_pool_size=1,
            database_max_overflow=0,
            database_pool_timeout_seconds=0.15,
            database_statement_timeout_ms=250,
            database_lock_timeout_ms=100,
        )
    )
    yield engine
    engine.dispose()


def test_postgres_statement_and_pool_deadlines(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        assert connection.scalar(text("SHOW search_path")) == "readiness_synthetic"
        assert connection.scalar(text("SHOW statement_timeout")) == "250ms"
        assert connection.scalar(text("SHOW lock_timeout")) == "100ms"
        started = monotonic()
        with pytest.raises(OperationalError) as error:
            connection.execute(text("SELECT pg_sleep(2)"))
        assert getattr(error.value.orig, "sqlstate", None) == "57014"
        assert 0.15 <= monotonic() - started < 1.5
        connection.rollback()
        started = monotonic()
        with pytest.raises(TimeoutError):
            postgres_engine.connect()
        assert 0.1 <= monotonic() - started < 1
        with TestClient(
            create_app(session_factory=create_session_factory(postgres_engine))
        ) as client:
            assert client.get("/ready").status_code == 503
            assert client.get("/health").status_code == 200


def test_postgres_lock_deadline(postgres_url: str, postgres_engine: Engine) -> None:
    blocker = create_database_engine(DatabaseSettings(database_url=postgres_url))
    try:
        with blocker.begin() as first, postgres_engine.connect() as second:
            first.execute(text("SELECT pg_advisory_xact_lock(5573, 8133)"))
            started = monotonic()
            with pytest.raises(OperationalError) as error:
                second.execute(text("SELECT pg_advisory_xact_lock(5573, 8133)"))
            assert getattr(error.value.orig, "sqlstate", None) == "55P03"
            assert 0.05 <= monotonic() - started < 1
    finally:
        blocker.dispose()


def test_postgres_actual_migrations_and_search_path(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_database_engine(DatabaseSettings(database_url=postgres_url))
    schema = "readiness_migrations"
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    url = make_url(postgres_url).update_query_dict({"options": f"-csearch_path={schema}"})
    url_string = url.render_as_string(hide_password=False)
    probe_engine = create_database_engine(DatabaseSettings(database_url=url_string))
    monkeypatch.setenv("DATABASE_URL", url_string)
    config = Config(API_ROOT / "alembic.ini")
    try:
        with TestClient(create_app(session_factory=create_session_factory(probe_engine))) as client:
            assert client.get("/ready").status_code == 503
            command.upgrade(config, "20260929_0007")
            assert client.get("/ready").status_code == 503
            command.upgrade(config, "head")
            assert client.get("/ready").status_code == 200
            with probe_engine.connect() as connection:
                assert (
                    set(connection.scalars(text("SELECT version_num FROM alembic_version")))
                    == health.expected_schema_heads()
                )
    finally:
        probe_engine.dispose()
        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()


def test_connect_deadline_on_stalled_local_handshake() -> None:
    release = threading.Event()
    accepted = threading.Event()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 8133))
        listener.listen(1)
        listener.settimeout(5)

        def stall() -> None:
            with listener.accept()[0]:
                accepted.set()
                release.wait(5)

        thread = threading.Thread(target=stall)
        thread.start()
        engine = create_database_engine(
            DatabaseSettings(
                database_url=f"postgresql+psycopg://synthetic@127.0.0.1:{listener.getsockname()[1]}/synthetic",
                database_connect_timeout_seconds=2,
            )
        )
        try:
            started = monotonic()
            with pytest.raises(OperationalError):
                engine.connect()
            assert accepted.is_set()
            assert 1.5 <= monotonic() - started < 4
        finally:
            release.set()
            thread.join(6)
            engine.dispose()

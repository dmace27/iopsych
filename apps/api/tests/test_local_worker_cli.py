"""CLI guards and delegation use only fake engines or isolated in-memory SQLite."""

import base64
import importlib
import json
import logging
import os
from unittest.mock import Mock

import pytest
import sqlalchemy
from sqlalchemy.orm import sessionmaker

from app.auth.errors import AccessProblemError
from app.invitations import local_worker_cli as cli
from app.invitations import worker

DATABASE = "synthetic_cli_test"
URL = f"postgresql+psycopg://synthetic:unused@127.0.0.1:5605/{DATABASE}"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in tuple(os.environ):
        if key.startswith(("PG", "INVITE_", "AUTH_", "DATABASE", "LOCAL_DELIVERY_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("AUTH_ENVIRONMENT", "development")
    monkeypatch.setenv("INVITE_ALLOW_SYNTHETIC_DEFINITIONS", "true")
    monkeypatch.setenv("INVITE_LOCAL_QUEUE_ENABLED", "true")
    monkeypatch.setenv("LOCAL_DELIVERY_DATABASE_URL", URL)
    monkeypatch.setenv("INVITE_CANDIDATE_BASE_URL", "http://127.0.0.1:3105/candidate/invites")
    monkeypatch.setenv("AUTH_JWT_SECRET", "a" * 32)
    monkeypatch.setenv("INVITE_TOKEN_SIGNING_SECRET", "b" * 32)
    monkeypatch.setenv("INVITE_LOCAL_QUEUE_KEY", base64.urlsafe_b64encode(b"c" * 32).decode())


def arguments(action: str = "cleanup", *extra: str) -> list[str]:
    return [action, "--once", "--ack-database", DATABASE, *extra]


def assert_counts(capsys: pytest.CaptureFixture[str], attempted: int = 0, cleaned: int = 0) -> None:
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {"attempted": attempted, "cleaned": cleaned}


@pytest.mark.parametrize(
    "url",
    [
        "sqlite+pysqlite:///:memory:",
        URL.replace("127.0.0.1", "localhost"),
        URL.replace("127.0.0.1", "192.0.2.1"),
        URL.replace("127.0.0.1", "remote.example.invalid"),
        URL.replace(":5605", ""),
        URL.replace(":5605", ":0"),
        URL.replace(":5605", ":65536"),
        *(URL.replace(":5605", f":{port}") for port in cli.PROTECTED_PORTS),
        URL + "?host=remote.example.invalid",
        URL + "?hostaddr=192.0.2.1",
        URL + "?service=remote",
        URL + "?options=-csearch_path=other",
        URL + "#fragment",
        URL.replace("postgresql+psycopg", "postgresql"),
        URL.replace(DATABASE, "postgres"),
        URL.replace(DATABASE, "bad/name"),
        "not-a-url-secret",
    ],
)
def test_invalid_targets_never_create_engine(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], url: str
) -> None:
    engine = Mock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr(sqlalchemy, "create_engine", engine)
    monkeypatch.setenv("LOCAL_DELIVERY_DATABASE_URL", url)
    assert cli.main(arguments()) == 2
    engine.assert_not_called()
    assert_counts(capsys)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("DATABASE_URL", URL),
        ("DATABASE_URL", ""),
        ("PGHOST", ""),
        ("PGHOST", "127.0.0.1"),
        ("PGHOSTADDR", "192.0.2.1"),
        ("PGSERVICE", "hidden"),
        ("PGOPTIONS", "-csearch_path=other"),
        ("AUTH_ENVIRONMENT", "production"),
        ("AUTH_ENVIRONMENT", "test"),
        ("INVITE_ALLOW_SYNTHETIC_DEFINITIONS", "false"),
        ("INVITE_LOCAL_QUEUE_ENABLED", "false"),
        ("LOCAL_DELIVERY_DATABASE_URL", None),
    ],
)
def test_environment_guards(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], key: str, value: str | None
) -> None:
    execute = Mock()
    monkeypatch.setattr(cli, "_execute", execute)
    if value is None:
        monkeypatch.delenv(key)
    else:
        monkeypatch.setenv(key, value)
    assert cli.main(arguments()) == 2
    execute.assert_not_called()
    assert_counts(capsys)


@pytest.mark.parametrize(
    "extra", [["--limit", "0"], ["--limit", "101"], ["--limit", "secret"], ["--unknown", "private"]]
)
def test_bad_arguments_are_private(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], extra: list[str]
) -> None:
    execute = Mock()
    monkeypatch.setattr(cli, "_execute", execute)
    assert cli.main(arguments("cleanup", *extra)) == 2
    execute.assert_not_called()
    assert_counts(capsys)


def test_once_and_acknowledgement_required(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["cleanup", "--ack-database", DATABASE]) == 2
    assert_counts(capsys)
    assert cli.main(["cleanup", "--once"]) == 2
    assert_counts(capsys)


@pytest.mark.parametrize("limit", [1, 25, 100])
@pytest.mark.parametrize("keys_present", [False, True])
def test_cleanup_delegates_without_any_keys(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    limit: int,
    keys_present: bool,
) -> None:
    for key in ("AUTH_JWT_SECRET", "INVITE_TOKEN_SIGNING_SECRET", "INVITE_LOCAL_QUEUE_KEY"):
        if keys_present:
            monkeypatch.setenv(key, "malformed-key-ignored")
        else:
            monkeypatch.delenv(key)
    monkeypatch.setenv("INVITE_CANDIDATE_BASE_URL", "invalid-and-ignored")
    engine = Mock()
    build = Mock(return_value=engine)
    cleanup = Mock(return_value=limit)
    monkeypatch.setattr(sqlalchemy, "create_engine", build)
    monkeypatch.setattr(worker, "cleanup_deliveries", cleanup)
    monkeypatch.setattr(worker, "LocalDeliveryWorker", Mock(side_effect=AssertionError))
    assert cli.main(arguments("cleanup", "--limit", str(limit))) == 0
    assert cleanup.call_args.kwargs == {"limit": limit}
    assert cleanup.call_args.args[0].kw["bind"] is engine
    assert build.call_args.args[0].database == DATABASE
    assert build.call_args.kwargs["echo"] is False
    engine.dispose.assert_called_once()
    assert_counts(capsys, cleaned=limit)


def test_drain_delegates_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engine = Mock()
    worker_class = Mock()
    worker_class.return_value.drain.return_value = 2
    monkeypatch.setattr(sqlalchemy, "create_engine", Mock(return_value=engine))
    monkeypatch.setattr(worker, "LocalDeliveryWorker", worker_class)
    assert cli.main(arguments("drain", "--smtp-port", "1145", "--limit", "3")) == 0
    worker_class.return_value.drain.assert_called_once_with(limit=3)
    factory, settings, authentication, adapter = worker_class.call_args.args
    assert factory.kw["bind"] is engine
    assert settings.local_queue_enabled and settings.allow_synthetic_definitions
    assert authentication.environment == "development"
    assert adapter.enabled and adapter.host == "127.0.0.1" and adapter.port == 1145
    engine.dispose.assert_called_once()
    assert_counts(capsys, attempted=2)


@pytest.mark.parametrize("port", ["3000", "8000", "8001", "5432", "25", "65536"])
def test_protected_smtp_never_connects(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], port: str
) -> None:
    build = Mock()
    monkeypatch.setattr(sqlalchemy, "create_engine", build)
    assert cli.main(arguments("drain", "--smtp-port", port)) == 1
    build.assert_not_called()
    assert_counts(capsys)


@pytest.mark.parametrize(
    "candidate",
    [
        "https://remote.example.invalid/invites",
        "http://localhost:3000/invites",
        "http://localhost/invites",
        "http://localhost:3105/invites",
        "http://user:private@127.0.0.1:3105/invites",
        "http://127.0.0.1:3105/invites#private",
    ],
)
def test_candidate_target_guard(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], candidate: str
) -> None:
    monkeypatch.setenv("INVITE_CANDIDATE_BASE_URL", candidate)
    build = Mock()
    monkeypatch.setattr(sqlalchemy, "create_engine", build)
    assert cli.main(arguments("drain", "--smtp-port", "1145")) == 1
    build.assert_not_called()
    assert_counts(capsys)


def test_errors_and_logs_are_suppressed_and_engine_disposed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engine = Mock()
    monkeypatch.setattr(sqlalchemy, "create_engine", Mock(return_value=engine))

    def fail(*args: object, **kwargs: object) -> None:
        logging.critical("private-token-and-email")
        raise RuntimeError("private-token-and-email")

    monkeypatch.setattr(worker, "cleanup_deliveries", fail)
    previous = logging.root.manager.disable
    assert cli.main(arguments()) == 1
    assert logging.root.manager.disable == previous
    engine.dispose.assert_called_once()
    assert_counts(capsys)


def test_existing_sqlite_worker_guard() -> None:
    engine = sqlalchemy.create_engine("sqlite+pysqlite:///:memory:")
    try:
        with pytest.raises(AccessProblemError) as caught:
            worker.cleanup_deliveries(sessionmaker(bind=engine), limit=1)
        assert caught.value.code == "local_queue_requires_postgresql"
    finally:
        engine.dispose()


def test_import_does_not_construct_engine_or_change_logging(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    build = Mock(side_effect=AssertionError)
    monkeypatch.setattr(sqlalchemy, "create_engine", build)
    previous = logging.root.manager.disable
    importlib.reload(cli)
    build.assert_not_called()
    assert logging.root.manager.disable == previous
    assert capsys.readouterr() == ("", "")


def test_connection_failure_is_redacted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sqlalchemy, "create_engine", Mock(side_effect=RuntimeError("private-database-url"))
    )
    assert cli.main(arguments()) == 1
    assert_counts(capsys)


@pytest.mark.parametrize("host", ["127.0.0.1", "[::1]"])
def test_numeric_loopback_database_targets(monkeypatch: pytest.MonkeyPatch, host: str) -> None:
    monkeypatch.setenv("LOCAL_DELIVERY_DATABASE_URL", URL.replace("127.0.0.1", host))
    assert cli._target(DATABASE).host == host.strip("[]")


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--smtp-port", "1145", "--smtp-host", "192.0.2.1"],
        ["--smtp-port", "1145", "--smtp-host", "localhost"],
    ],
)
def test_drain_requires_explicit_local_smtp(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], extra: list[str]
) -> None:
    build = Mock()
    monkeypatch.setattr(sqlalchemy, "create_engine", build)
    assert cli.main(arguments("drain", *extra)) == 1
    build.assert_not_called()
    assert_counts(capsys)


def test_drain_rejects_lost_key_before_engine(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("INVITE_LOCAL_QUEUE_KEY")
    build = Mock()
    monkeypatch.setattr(sqlalchemy, "create_engine", build)
    assert cli.main(arguments("drain", "--smtp-port", "1145")) == 1
    build.assert_not_called()
    assert_counts(capsys)

"""Connection-free safety checks for the populated-upgrade fixture."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from tests import test_assignment_upgrade as upgrade


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "[::1]"])
@pytest.mark.parametrize("port,database", sorted(upgrade.APPROVED_UPGRADE_DATABASES))
def test_approved_loopback_pairs(host: str, port: int, database: str) -> None:
    value = f"postgresql+psycopg://synthetic:synthetic@{host}:{port}/{database}"
    assert upgrade.validated_upgrade_url(value) == make_url(value)


@pytest.mark.parametrize(
    "value",
    [
        "not a URL",
        "sqlite+pysqlite:///:memory:",
        "postgresql://127.0.0.1:5550/iopsych_6c",
        "postgresql+psycopg2://127.0.0.1:5550/iopsych_6c",
        "mysql+psycopg://127.0.0.1:5550/iopsych_6c",
        "postgresql+psycopg://localhost:5550/iopsych_6c",
        "postgresql+psycopg://example.invalid:5550/iopsych_6c",
        "postgresql+psycopg://192.0.2.1:5550/iopsych_6c",
        "postgresql+psycopg://0.0.0.0:5550/iopsych_6c",
        "postgresql+psycopg://[::]:5550/iopsych_6c",
        "postgresql+psycopg://[::ffff:192.0.2.1]:5550/iopsych_6c",
        "postgresql+psycopg://[::1%lo0]:5550/iopsych_6c",
        "postgresql+psycopg://127.1:5550/iopsych_6c",
        "postgresql+psycopg://2130706433:5550/iopsych_6c",
        "postgresql+psycopg://user@/iopsych_6c",
        "postgresql+psycopg:///iopsych_6c?host=/tmp&port=5550",
        "postgresql+psycopg://127.0.0.1:5432/iopsych_6c",
        "postgresql+psycopg://127.0.0.1/iopsych_6c",
        "postgresql+psycopg://127.0.0.1:bad/iopsych_6c",
        "postgresql+psycopg://127.0.0.1:5550/iopsych_regression",
        "postgresql+psycopg://127.0.0.1:5571/iopsych_6c",
        "postgresql+psycopg://127.0.0.1:5571/existing",
        "postgresql+psycopg://127.0.0.1:5550/iopsych_6c?",
        "postgresql+psycopg://127.0.0.1:5550/iopsych_6c?host=remote.invalid",
        "postgresql+psycopg://127.0.0.1:5550/iopsych_6c?host=/tmp",
        "postgresql+psycopg://127.0.0.1:5550/iopsych_6c?hostaddr=192.0.2.1",
        "postgresql+psycopg://127.0.0.1:5550/iopsych_6c?port=5432",
        "postgresql+psycopg://127.0.0.1:5550/iopsych_6c?service=existing",
        "postgresql+psycopg://127.0.0.1:5550/iopsych_6c?options=-csearch_path=public",
        "postgresql+psycopg://127.0.0.1:5550/iopsych_6c?sslmode=disable",
    ],
)
def test_rejected_before_engine_creation(
    value: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    engine = MagicMock(side_effect=AssertionError("Must not create an engine"))
    monkeypatch.setattr(upgrade, "create_engine", engine)
    monkeypatch.setenv("TEST_POSTGRES_URL", value)
    fixture = upgrade.upgrade_url.__wrapped__(SimpleNamespace(param="postgresql"), tmp_path)
    with pytest.raises(ValueError, match="Upgrade tests require"):
        next(fixture)
    engine.assert_not_called()


def test_generated_schema_only_and_cleanup_without_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base = "postgresql+psycopg://synthetic:synthetic@127.0.0.1:5571/iopsych_regression"
    monkeypatch.setenv("TEST_POSTGRES_URL", base)
    admin = MagicMock()
    factory = MagicMock(return_value=admin)
    monkeypatch.setattr(upgrade, "create_engine", factory)
    fixture = upgrade.upgrade_url.__wrapped__(SimpleNamespace(param="postgresql"), tmp_path)
    scoped = make_url(next(fixture))
    factory.assert_called_once_with(make_url(base))
    connection = admin.begin.return_value.__enter__.return_value
    create = connection.execute.call_args.args[0]
    assert isinstance(create, CreateSchema)
    assert create.element.startswith("assignment_upgrade_")
    suffix = create.element.removeprefix("assignment_upgrade_")
    assert UUID(hex=suffix).version == 4
    assert len(suffix) == 32
    assert scoped.query == {"options": f"-csearch_path={create.element}"}
    fixture.close()
    drop = connection.execute.call_args.args[0]
    assert isinstance(drop, DropSchema)
    assert drop.element == create.element
    assert drop.cascade
    assert connection.execute.call_count == 2
    admin.dispose.assert_called_once_with()

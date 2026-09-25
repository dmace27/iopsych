"""Alembic migration and database command tests."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.database import seed, verify

API_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "alembic_version",
    "audit_events",
    "organizations",
    "role_construct_ratings",
    "role_profiles",
    "roles",
    "users",
}


def alembic_config(database_url: str) -> Config:
    """Build an Alembic config whose environment reads the requested URL."""

    config = Config(API_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migration_upgrades_and_downgrades_empty_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The initial revision creates all package 0C tables from nothing."""

    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = alembic_config(database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    engine.dispose()

    command.downgrade(config, "base")
    engine = create_engine(database_url)
    # Alembic retains its own empty version table after reaching base.
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()


def test_documented_seed_and_verify_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI entry points migrate, seed, and verify a fresh configured database."""

    database_url = f"sqlite+pysqlite:///{tmp_path / 'commands.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(database_url), "head")

    seed.main()
    verify.main()
    output = capsys.readouterr().out
    assert "Seed complete: 2 organizations" in output
    assert "Database verification passed" in output

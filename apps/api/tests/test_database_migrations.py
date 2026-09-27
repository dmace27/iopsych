"""Alembic migration and database command tests."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.database import seed, verify

API_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "alembic_version",
    "assessment_invites",
    "audit_events",
    "candidate_consents",
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
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    assert "auth_subject" in {column["name"] for column in inspector.get_columns("users")}
    with engine.connect() as connection:
        trigger_names = set(
            connection.scalars(text("SELECT name FROM sqlite_master WHERE type = 'trigger'"))
        )
    assert trigger_names == {
        "trg_audit_events_no_delete",
        "trg_audit_events_no_update",
    }
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


def test_auth_migration_backfills_existing_user_subject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Package 1A upgrades existing package-0C users without losing identity data."""

    database_url = f"sqlite+pysqlite:///{tmp_path / 'auth-upgrade.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = alembic_config(database_url)
    command.upgrade(config, "20260925_0001")
    engine = create_engine(database_url)
    existing_user_id = "10000000000040008000000000000001"
    existing_organization_id = "10000000000040008000000000000002"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organizations (id, slug, name) "
                "VALUES (:id, 'migration-test', 'Migration Test')"
            ),
            {"id": existing_organization_id},
        )
        connection.execute(
            text(
                "INSERT INTO users (id, organization_id, email, name, role) "
                "VALUES (:id, :organization_id, 'user@example.invalid', "
                "'Migration User', 'recruiter')"
            ),
            {"id": existing_user_id, "organization_id": existing_organization_id},
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        auth_subject = connection.scalar(
            text("SELECT auth_subject FROM users WHERE id = :id"),
            {"id": existing_user_id},
        )
    engine.dispose()
    assert auth_subject == existing_user_id

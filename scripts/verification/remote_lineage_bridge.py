"""Rollback-only remote lineage experiment. No operational bridge or stamp API."""

from __future__ import annotations

import hashlib
import json
import os
import runpy
import socket
import subprocess
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "apps/api/alembic/versions"
CANONICAL = "5cde2e7cc9b98fe8bd25bc7e38c91afa7b20090e"
REMOTE = "646201a58ceaeb679900344319ea95fdb888641e"
SOURCES = {
    "20261103_0008_active_internal_users.py": "8a82710dba4f675beeb5bcdddc56ae526e1d9d90166c0bf27de580b9a364893d",
    "20261103_0009_invitation_delivery.py": "0b88a6d743708065c1e92a6091b1f63b763c5691104c01c3d88ebc40c08d106e",
}
URL = "postgresql+psycopg://bridge:synthetic-only@127.0.0.1:5619/iopsych_bridge"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def command(*args):
    return subprocess.run(
        args, check=True, capture_output=True, timeout=60
    ).stdout.decode()


def source_bytes(name):
    data = subprocess.run(
        ["git", "show", f"{REMOTE}:apps/api/alembic/versions/{name}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=30,
    ).stdout
    if hashlib.sha256(data).hexdigest() != SOURCES[name]:
        raise RuntimeError("Remote migration provenance mismatch")
    return data


def guard():
    forbidden = {
        "DATABASE_URL",
        "TEST_POSTGRES_URL",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGPASSFILE",
    }
    if (
        forbidden.intersection(os.environ)
        or any(name.startswith("PG") for name in os.environ)
        or (ROOT / "apps/api/.env").exists()
    ):
        raise RuntimeError(
            "Unset ambient database/Docker configuration; isolated checkout required"
        )
    endpoint = command(
        "docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"
    ).strip()
    if not endpoint.startswith("unix://"):
        raise RuntimeError("Only a local Unix-socket Docker daemon is allowed")
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 5619))


def execute_revision(connection, path=None, source=None):
    with Operations.context(MigrationContext.configure(connection)):
        if path:
            relative = path.relative_to(ROOT).as_posix()
            committed = subprocess.run(
                ["git", "show", f"{CANONICAL}:{relative}"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                timeout=30,
            ).stdout
            if path.read_bytes() != committed:
                raise RuntimeError("Canonical migration differs from reviewed base")
            module = runpy.run_path(str(path))
        else:
            module = {}
            exec(compile(source, "<verified remote migration>", "exec"), module)  # noqa: S102 - exact hash-verified git migration
        module["upgrade"]()


def create_lineage(connection, head):
    for path in sorted(VERSIONS.glob("*.py")):
        if path.name.startswith("202609") or head == "canonical":
            execute_revision(connection, path=path)
    if head != "canonical":
        for name in SOURCES:
            execute_revision(connection, source=source_bytes(name))
            if head == "20261103_0008":
                break
    connection.execute(
        sa.text(
            "CREATE TABLE alembic_version (version_num varchar(32) NOT NULL PRIMARY KEY)"
        )
    )
    connection.execute(
        sa.text("INSERT INTO alembic_version VALUES (:head)"),
        {"head": "20261104_0012" if head == "canonical" else head},
    )


def signature(connection):
    """Observed structural signature; not yet approved as a complete schema verifier."""
    inspector = sa.inspect(connection)
    result = {}
    for table in inspector.get_table_names():
        result[table] = {
            "columns": sorted(
                (
                    column["name"],
                    str(column["type"]),
                    column["nullable"],
                    str(column["default"]),
                )
                for column in inspector.get_columns(table)
            ),
            "checks": sorted(
                constraint["sqltext"]
                for constraint in inspector.get_check_constraints(table)
            ),
            "unique": sorted(
                tuple(constraint["column_names"])
                for constraint in inspector.get_unique_constraints(table)
            ),
            "pk": inspector.get_pk_constraint(table)["constrained_columns"],
            "fk": sorted(
                (
                    tuple(constraint["constrained_columns"]),
                    constraint["referred_table"],
                    tuple(constraint["referred_columns"]),
                    str(constraint["options"]),
                )
                for constraint in inspector.get_foreign_keys(table)
            ),
            "indexes": sorted(
                (tuple(index["column_names"]), index["unique"])
                for index in inspector.get_indexes(table)
            ),
        }
    result["triggers"] = (
        connection.execute(
            sa.text(
                "SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=current_schema() AND NOT t.tgisinternal ORDER BY 1,2"
            )
        )
        .tuples()
        .all()
    )
    result["functions"] = (
        connection.execute(
            sa.text(
                "SELECT p.proname,p.prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=current_schema() ORDER BY 1"
            )
        )
        .tuples()
        .all()
    )
    return result


def rows(connection, columns=None, rename=False):
    inspector = sa.inspect(connection)
    columns = columns or {
        table_name: [column["name"] for column in inspector.get_columns(table_name)]
        for table_name in inspector.get_table_names()
        if table_name != "alembic_version"
    }
    result = {}
    for table, names in columns.items():
        actual = table
        if rename and table in ("invitation_deliveries", "invitation_delivery_events"):
            actual = "provider_" + table
        quoted = ",".join('"' + column_name + '"' for column_name in names)
        values = (
            connection.execute(sa.text(f'SELECT {quoted} FROM "{actual}"'))
            .tuples()
            .all()
        )
        result[table] = sorted(
            [list(row) for row in values],
            key=lambda row: json.dumps(row, default=str, sort_keys=True),
        )
    return columns, result


def _experiment(
    connection, expected_source, expected_target, *, inject=False, verify=None
):
    """Caller MUST roll back; version translation deliberately unavailable."""
    connection.execute(sa.text("SET LOCAL lock_timeout='3s'"))
    connection.execute(sa.text("SET LOCAL statement_timeout='30s'"))
    connection.execute(sa.text("SELECT pg_advisory_xact_lock(5619, 12)"))
    tables = sa.inspect(connection).get_table_names()
    connection.execute(
        sa.text(
            "LOCK TABLE "
            + ",".join('"' + table_name + '"' for table_name in tables)
            + " IN ACCESS EXCLUSIVE MODE"
        )
    )
    head = (
        connection.execute(sa.text("SELECT version_num FROM alembic_version"))
        .scalars()
        .all()
    )
    if head not in (["20261103_0008"], ["20261103_0009"]):
        raise RuntimeError("Unknown source revision; refused")
    if signature(connection) != expected_source:
        raise RuntimeError("Unknown source schema; refused")
    columns, before = rows(connection)
    remote9 = head == ["20261103_0009"]
    if remote9:
        for old, new in [
            ("invitation_deliveries", "provider_invitation_deliveries"),
            ("invitation_delivery_events", "provider_invitation_delivery_events"),
        ]:
            connection.execute(sa.text(f"ALTER TABLE {old} RENAME TO {new}"))
            connection.execute(
                sa.text(f"ALTER TABLE {new} RENAME CONSTRAINT {old}_pkey TO {new}_pkey")
            )
        connection.execute(
            sa.text(
                "ALTER INDEX ix_invitation_deliveries_due RENAME TO ix_provider_invitation_deliveries_due"
            )
        )
    if inject:
        raise RuntimeError("Injected failure after rename")
    for suffix in ("0008", "0009"):
        execute_revision(
            connection, path=next(VERSIONS.glob(f"20261104_{suffix}_*.py"))
        )
    connection.execute(
        sa.text("ALTER TABLE users ADD COLUMN version INTEGER DEFAULT 1 NOT NULL")
    )
    connection.execute(
        sa.text(
            "ALTER TABLE users ADD CONSTRAINT ck_users_version_positive CHECK (version >= 1)"
        )
    )
    execute_revision(connection, path=next(VERSIONS.glob("20261104_0011_*.py")))
    if not remote9:
        execute_revision(connection, path=next(VERSIONS.glob("20261104_0012_*.py")))
    if signature(connection) != expected_target:
        raise RuntimeError("Target structural equivalence not established")
    _, after = rows(connection, columns, rename=remote9)
    if before != after:
        raise RuntimeError("Existing row evidence changed")
    if verify is not None:
        verify(connection)
    return {
        "source": head[0],
        "row_sha256": digest(before),
        "rows": {
            table_name: len(table_rows) for table_name, table_rows in before.items()
        },
        "source_schema_sha256": digest(expected_source),
        "target_schema_sha256": digest(expected_target),
        "version_translated": False,
    }


def experiment(
    connection, expected_source, expected_target, *, inject=False, verify=None
):
    """Always roll back experimental DDL, including on successful equivalence."""
    if connection.engine.url.render_as_string(hide_password=False) != URL:
        raise RuntimeError(
            "Only the isolated synthetic PG5619/iopsych_bridge is allowed"
        )
    transaction = connection.begin_nested()
    try:
        return _experiment(
            connection, expected_source, expected_target, inject=inject, verify=verify
        )
    finally:
        transaction.rollback()


def main():
    raise SystemExit(
        "BLOCKED: operational bridge is not implemented; run focused synthetic tests only"
    )


if __name__ == "__main__":
    main()

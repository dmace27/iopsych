"""Enforce audit-event immutability inside the database.

Revision ID: 20260927_0003
Revises: 20260926_0002
Create Date: 2026-09-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260927_0003"
down_revision: str | None = "20260926_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reject direct updates and deletes for every supported database."""

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "CREATE OR REPLACE FUNCTION reject_audit_event_mutation() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'audit events are immutable'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_audit_events_immutable "
            "BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW "
            "EXECUTE FUNCTION reject_audit_event_mutation()"
        )
        op.execute(
            "CREATE TRIGGER trg_audit_events_no_truncate "
            "BEFORE TRUNCATE ON audit_events FOR EACH STATEMENT "
            "EXECUTE FUNCTION reject_audit_event_mutation()"
        )
    elif dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER trg_audit_events_no_update "
            "BEFORE UPDATE ON audit_events BEGIN "
            "SELECT RAISE(ABORT, 'audit events are immutable'); END"
        )
        op.execute(
            "CREATE TRIGGER trg_audit_events_no_delete "
            "BEFORE DELETE ON audit_events BEGIN "
            "SELECT RAISE(ABORT, 'audit events are immutable'); END"
        )
    else:
        raise RuntimeError(f"unsupported audit-trigger database: {dialect}")


def downgrade() -> None:
    """Remove the database-level mutation guards."""

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        # IF EXISTS also permits rollback from a partially applied revision.
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_truncate ON audit_events")
        op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS reject_audit_event_mutation()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER trg_audit_events_no_delete")
        op.execute("DROP TRIGGER trg_audit_events_no_update")
    else:
        raise RuntimeError(f"unsupported audit-trigger database: {dialect}")

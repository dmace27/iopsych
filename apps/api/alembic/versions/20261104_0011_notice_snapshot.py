"""Preserve notice evidence without fabricating historical snapshots.

Revision ID: 20261104_0011
Revises: 20261104_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20261104_0011"
down_revision: str | None = "20261104_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "notice_snapshot_json",
    "notice_sha256",
    "notice_snapshot_origin",
    "notice_snapshot_recorded_at",
)


def _restore_sqlite_assignment_trigger() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_assessment_invites_assignment_immutable "
            "BEFORE UPDATE OF assignment_json ON assessment_invites "
            "WHEN OLD.assignment_json IS NOT NEW.assignment_json BEGIN "
            "SELECT RAISE(ABORT, 'assignments are immutable'); END"
        )


def upgrade() -> None:
    """Add nullable evidence and prevent rewriting any frozen snapshot."""

    op.add_column(
        "assessment_invites",
        sa.Column(
            "notice_snapshot_json",
            sa.JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql"),
            nullable=True,
        ),
    )
    op.add_column("assessment_invites", sa.Column("notice_sha256", sa.String(64), nullable=True))
    op.add_column(
        "assessment_invites", sa.Column("notice_snapshot_origin", sa.String(24), nullable=True)
    )
    op.add_column(
        "assessment_invites",
        sa.Column("notice_snapshot_recorded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "candidate_consents", sa.Column("presented_notice_sha256", sa.String(64), nullable=True)
    )
    complete = (
        "("
        + " AND ".join(f"{name} IS NULL" for name in _COLUMNS)
        + ") OR ("
        + (" AND ".join(f"{name} IS NOT NULL" for name in _COLUMNS))
        + ")"
    )
    hex_check = "notice_sha256"
    for digit in "0123456789abcdef":
        hex_check = f"replace({hex_check}, '{digit}', '')"
    with op.batch_alter_table("assessment_invites") as batch:
        batch.create_check_constraint("ck_notice_snapshot_complete", complete)
        batch.create_check_constraint(
            "ck_notice_snapshot_origin",
            "notice_snapshot_origin IN ('issued', 'first_presented', 'legacy_decision')",
        )
        batch.create_check_constraint(
            "ck_notice_snapshot_digest", f"length(notice_sha256) = 64 AND {hex_check} = ''"
        )
    _restore_sqlite_assignment_trigger()
    decided = "EXISTS (SELECT 1 FROM candidate_consents WHERE invite_id = OLD.id)"
    if op.get_bind().dialect.name == "postgresql":
        changed = " OR ".join(
            f"OLD.{name}::text IS DISTINCT FROM NEW.{name}::text" for name in _COLUMNS
        )
        present = " OR ".join(f"OLD.{name} IS NOT NULL" for name in _COLUMNS)
        op.execute(
            "CREATE FUNCTION reject_notice_snapshot_mutation() RETURNS trigger LANGUAGE plpgsql "
            f"AS $$ BEGIN IF ({present} OR {decided}) AND ({changed}) THEN "
            "RAISE EXCEPTION 'notice snapshots are immutable'; END IF; RETURN NEW; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_assessment_invites_notice_immutable BEFORE UPDATE "
            "ON assessment_invites FOR EACH ROW EXECUTE FUNCTION reject_notice_snapshot_mutation()"
        )
    elif op.get_bind().dialect.name == "sqlite":
        changed = " OR ".join(f"OLD.{name} IS NOT NEW.{name}" for name in _COLUMNS)
        present = " OR ".join(f"OLD.{name} IS NOT NULL" for name in _COLUMNS)
        op.execute(
            "CREATE TRIGGER trg_assessment_invites_notice_immutable BEFORE UPDATE "
            f"ON assessment_invites WHEN ({present} OR {decided}) AND ({changed}) BEGIN "
            "SELECT RAISE(ABORT, 'notice snapshots are immutable'); END"
        )
    else:
        raise RuntimeError("Unsupported notice-trigger database")


def downgrade() -> None:
    """Refuse to erase any recorded snapshot or presented digest evidence."""

    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        connection.execute(
            sa.text("LOCK TABLE assessment_invites, candidate_consents IN ACCESS EXCLUSIVE MODE")
        )
    present = " OR ".join(f"{name} IS NOT NULL" for name in _COLUMNS)
    snapshots = connection.scalar(
        sa.text(f"SELECT count(*) FROM assessment_invites WHERE {present}")
    )
    digests = connection.scalar(
        sa.text("SELECT count(*) FROM candidate_consents WHERE presented_notice_sha256 IS NOT NULL")
    )
    if snapshots or digests:
        raise RuntimeError("Cannot downgrade while notice evidence exists")
    if connection.dialect.name == "postgresql":
        op.execute("DROP TRIGGER trg_assessment_invites_notice_immutable ON assessment_invites")
        op.execute("DROP FUNCTION reject_notice_snapshot_mutation()")
    else:
        op.execute("DROP TRIGGER trg_assessment_invites_notice_immutable")
    with op.batch_alter_table("assessment_invites") as batch:
        for name in ("complete", "origin", "digest"):
            batch.drop_constraint(f"ck_notice_snapshot_{name}", type_="check")
    _restore_sqlite_assignment_trigger()
    op.drop_column("candidate_consents", "presented_notice_sha256")
    for name in reversed(_COLUMNS):
        op.drop_column("assessment_invites", name)

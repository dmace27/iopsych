"""Pin legacy assignments without rewriting submissions or reports.

Revision ID: 20261104_0008
Revises: 20260929_0007
"""

import json
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "20261104_0008"
down_revision: str | None = "20260929_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _hash(payload: object) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()


def upgrade() -> None:
    """Freeze known v1 only; malformed, anonymized or unknown history stays NULL."""
    legacy = json.loads((Path(__file__).parents[1] / "definitions/legacy-v1.json").read_text())
    if _hash(legacy) != "021233ca4dab9c86b87aeabca88f503bf7c70fd0b0d324c64e788b620aeb6e3c":
        raise RuntimeError("Frozen migration definition checksum mismatch")
    op.add_column("assessment_invites", sa.Column("assignment_json", sa.JSON(), nullable=True))
    connection = op.get_bind()
    metadata = sa.MetaData()
    invites = sa.Table("assessment_invites", metadata, autoload_with=connection)
    assessments = sa.Table("assessments", metadata, autoload_with=connection)
    # No current model/registry imports: this revision's backfill is permanently v1.
    rows = (
        connection.execute(
            sa.select(
                invites.c.id,
                assessments.c.id.label("assessment_id"),
                assessments.c.definition_json,
                assessments.c.anonymized_at,
            ).outerjoin(assessments, assessments.c.invite_id == invites.c.id)
        )
        .mappings()
        .all()
    )
    for row in rows:
        definition = legacy if row["assessment_id"] is None else row["definition_json"]
        if row["anonymized_at"] is not None or definition != legacy:
            # Do not guess a snapshot for an unknown/malformed prior submission.
            continue
        assignment = {
            "contract_version": 1,
            "definition": definition,
            "definition_sha256": _hash(definition),
            "matching_algorithm_version": "1.0.0",
        }
        connection.execute(
            invites.update().where(invites.c.id == row["id"]).values(assignment_json=assignment)
        )
    if connection.dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION reject_assignment_mutation() RETURNS trigger LANGUAGE plpgsql "
            "AS $$ BEGIN IF OLD.assignment_json::text IS DISTINCT FROM "
            "NEW.assignment_json::text THEN RAISE EXCEPTION 'assignments are immutable'; "
            "END IF; RETURN NEW; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_assessment_invites_assignment_immutable BEFORE UPDATE "
            "ON assessment_invites FOR EACH ROW EXECUTE FUNCTION reject_assignment_mutation()"
        )
    elif connection.dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER trg_assessment_invites_assignment_immutable BEFORE UPDATE "
            "OF assignment_json ON assessment_invites "
            "WHEN OLD.assignment_json IS NOT NEW.assignment_json BEGIN "
            "SELECT RAISE(ABORT, 'assignments are immutable'); END"
        )
    else:
        raise RuntimeError("Unsupported assignment-trigger database")


def downgrade() -> None:
    """Remove only this additive assignment infrastructure."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER trg_assessment_invites_assignment_immutable ON assessment_invites")
        op.execute("DROP FUNCTION reject_assignment_mutation()")
    else:
        op.execute("DROP TRIGGER trg_assessment_invites_assignment_immutable")
    op.drop_column("assessment_invites", "assignment_json")

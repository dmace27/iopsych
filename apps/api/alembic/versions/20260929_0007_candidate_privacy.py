"""Track candidate retention deadlines and anonymization.

Revision ID: 20260929_0007
Revises: 20260928_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0007"
down_revision: str | None = "20260928_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable lifecycle timestamps without inventing legacy deadlines."""

    op.add_column(
        "assessments",
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_assessments_retention_expires_at",
        "assessments",
        ["retention_expires_at"],
    )
    op.create_index(
        "ix_assessments_anonymized_at",
        "assessments",
        ["anonymized_at"],
    )


def downgrade() -> None:
    """Remove lifecycle indexes before their timestamp columns."""

    op.drop_index("ix_assessments_anonymized_at", table_name="assessments")
    op.drop_index("ix_assessments_retention_expires_at", table_name="assessments")
    op.drop_column("assessments", "anonymized_at")
    op.drop_column("assessments", "retention_expires_at")

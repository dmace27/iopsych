"""Shared SQLAlchemy base classes and storage conventions."""

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """Persist timezone-aware timestamps and normalize values to UTC.

    PostgreSQL preserves the timezone information. SQLite does not, so the
    result hook also restores UTC awareness for portable unit tests.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            msg = "database timestamps must be timezone-aware"
            raise ValueError(msg)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    """Declarative base for all application-owned tables."""

    type_annotation_map: ClassVar[dict[type[Any], Any]] = {datetime: UtcDateTime()}


class UuidPrimaryKeyMixin:
    """Use application-generated UUIDs for portable, non-sequential IDs."""

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)


class CreatedAtMixin:
    """Add a database-generated, timezone-aware creation timestamp."""

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), nullable=False, server_default=func.now()
    )

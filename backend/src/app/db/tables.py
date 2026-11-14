"""Table definitions (the "Data model" section of _docs/specs.md).

Only portable column types and constraints are used, so the same schema works
on PostgreSQL and SQLite. Enums are VARCHAR columns with a CHECK constraint
rather than native PostgreSQL enums, so adding a value later is a plain
migration on both. Changing this file needs a new Alembic migration;
tests/api/test_db.py fails if the two drift apart.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Dialect,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
    TypeDecorator,
    Uuid,
)

from app.domain import Source, Status


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC datetimes on every backend.

    PostgreSQL stores timestamptz natively. SQLite has no timezone support, so
    values are stored as naive UTC and made aware again on the way out.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed; use timezone-aware UTC")
        value = value.astimezone(UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        assert isinstance(value, datetime)
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def enum_column_type(enum: type[StrEnum], name: str) -> Enum:
    """A VARCHAR limited to the enum's values by a CHECK constraint named `name`.

    Stores and returns the plain string values ("applied"), not the member names.
    """
    return Enum(
        *[member.value for member in enum],
        name=name,
        native_enum=False,
        create_constraint=True,
        length=max(len(member.value) for member in enum),
    )


metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

applications = Table(
    "applications",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("company", String(100), nullable=False),
    Column("role", String(100), nullable=False),
    Column("link", String(500), nullable=True),
    Column("source", enum_column_type(Source, "source"), nullable=False),
    Column("status", enum_column_type(Status, "status"), nullable=False),
    Column("applied_date", Date, nullable=True),
    Column("follow_up_date", Date, nullable=True),
    Column("notes", Text, nullable=True),
    Column("created_at", UTCDateTime, nullable=False),
    Column("updated_at", UTCDateTime, nullable=False),
    CheckConstraint("length(company) BETWEEN 1 AND 100", name="company_length"),
    CheckConstraint("length(role) BETWEEN 1 AND 100", name="role_length"),
    CheckConstraint("link IS NULL OR length(link) <= 500", name="link_length"),
    CheckConstraint("notes IS NULL OR length(notes) <= 5000", name="notes_length"),
)

status_events = Table(
    "status_events",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "application_id",
        Uuid,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("from_status", enum_column_type(Status, "from_status"), nullable=True),
    Column("to_status", enum_column_type(Status, "to_status"), nullable=False),
    Column("note", String(500), nullable=True),
    Column("created_at", UTCDateTime, nullable=False),
    CheckConstraint("note IS NULL OR length(note) <= 500", name="note_length"),
    Index(None, "application_id", "created_at"),
)

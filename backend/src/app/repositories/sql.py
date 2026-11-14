"""SQLAlchemy implementation of the Repository protocol.

Uses SQLAlchemy Core on one Connection per request, so it works with any
database SQLAlchemy supports. Rows come back as plain records (copies), and
writes happen only through the repository's own methods.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from uuid import UUID

from sqlalchemy import Engine, delete, insert, select, update
from sqlalchemy.engine import Connection, RowMapping

from app.db.tables import applications, status_events
from app.domain import Source, Status
from app.repositories.records import ApplicationRecord, StatusEventRecord


@contextmanager
def open_repository(engine: Engine) -> Iterator[SqlRepository]:
    """A repository on its own connection; anything not committed is rolled back on close."""
    with engine.connect() as connection:
        yield SqlRepository(connection)


def _application(row: RowMapping) -> ApplicationRecord:
    return ApplicationRecord(**{**row, "source": Source(row["source"]), "status": Status(row["status"])})


def _event(row: RowMapping) -> StatusEventRecord:
    from_status = row["from_status"]
    return StatusEventRecord(
        **{
            **row,
            "from_status": Status(from_status) if from_status is not None else None,
            "to_status": Status(row["to_status"]),
        }
    )


class SqlRepository:
    def __init__(self, connection: Connection) -> None:
        self._conn = connection
        self._depth = 0

    @contextmanager
    def transaction(self) -> Iterator[None]:
        outermost = self._depth == 0
        self._depth += 1
        try:
            yield
            if outermost:
                self._conn.commit()
        except BaseException:
            if outermost:
                self._conn.rollback()
            raise
        finally:
            self._depth -= 1

    # ---- applications --------------------------------------------------------

    def list_applications(self, status: Status | None = None) -> list[ApplicationRecord]:
        stmt = select(applications).order_by(applications.c.updated_at.desc(), applications.c.id)
        if status is not None:
            stmt = stmt.where(applications.c.status == status.value)
        return [_application(row) for row in self._conn.execute(stmt).mappings()]

    def get_application(self, application_id: UUID) -> ApplicationRecord | None:
        stmt = select(applications).where(applications.c.id == application_id)
        row = self._conn.execute(stmt).mappings().first()
        return _application(row) if row is not None else None

    def save_application(self, record: ApplicationRecord) -> None:
        values = asdict(record)
        values["source"] = record.source.value
        values["status"] = record.status.value
        result = self._conn.execute(
            update(applications).where(applications.c.id == record.id).values(**values)
        )
        if result.rowcount == 0:
            self._conn.execute(insert(applications).values(**values))

    def delete_application(self, application_id: UUID) -> None:
        # Explicit, child first, so it doesn't depend on ON DELETE CASCADE being enforced.
        self._conn.execute(delete(status_events).where(status_events.c.application_id == application_id))
        self._conn.execute(delete(applications).where(applications.c.id == application_id))

    # ---- status events -------------------------------------------------------

    def add_event(self, record: StatusEventRecord) -> None:
        values = asdict(record)
        values["from_status"] = record.from_status.value if record.from_status is not None else None
        values["to_status"] = record.to_status.value
        self._conn.execute(insert(status_events).values(**values))

    def list_events(self, application_id: UUID) -> list[StatusEventRecord]:
        stmt = (
            select(status_events)
            .where(status_events.c.application_id == application_id)
            .order_by(status_events.c.created_at, status_events.c.id)
        )
        return [_event(row) for row in self._conn.execute(stmt).mappings()]

    def list_all_events(self) -> list[StatusEventRecord]:
        stmt = select(status_events).order_by(status_events.c.created_at, status_events.c.id)
        return [_event(row) for row in self._conn.execute(stmt).mappings()]

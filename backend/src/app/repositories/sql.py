"""SQLAlchemy implementation of the Repository protocol.

Uses SQLAlchemy Core on one Connection per request, so it works with any
database SQLAlchemy supports. Rows come back as plain records (copies), and
writes happen only through the repository's own methods.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.engine import Connection


@contextmanager
def open_repository(engine: Engine) -> Iterator[SqlRepository]:
    """A repository on its own connection; anything not committed is rolled back on close."""
    with engine.connect() as connection:
        yield SqlRepository(connection)


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

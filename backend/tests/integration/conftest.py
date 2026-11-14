"""Integration tests: the API against PostgreSQL 16 (AC-9.1).

TEST_DATABASE_URL, when set, is used as is; the tests drop and recreate the schema in it, so
point it at a throwaway database (Compose creates `tracker_test` for this). Otherwise a
PostgreSQL 16 container is started with testcontainers. With neither, the run fails with a
message: it never skips, so `make test` can't be green without these tests running.

This folder has its own session-scoped `engine`. Pytest caches a session fixture once per
definition, so reusing the shared one from tests/conftest.py would hand these tests the SQLite
engine whenever tests/api ran first in the same session (#18).
"""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine

from app.db.engine import create_db_engine
from app.db.migrate import downgrade, upgrade
from app.db.tables import metadata

POSTGRES_IMAGE = "postgres:16"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        if not url.startswith("postgresql"):
            pytest.fail(f"Integration tests need PostgreSQL; TEST_DATABASE_URL is {url.split(':', 1)[0]}")
        yield url
        return
    try:
        from testcontainers.community.postgres import PostgresContainer

        container = PostgresContainer(POSTGRES_IMAGE, driver="psycopg")
        container.start()
    except Exception as exc:
        pytest.fail(
            "Integration tests need PostgreSQL: set TEST_DATABASE_URL, or start Docker so "
            f"testcontainers can run {POSTGRES_IMAGE}. Starting the container failed: {exc!r}",
            pytrace=False,
        )
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    """The PostgreSQL engine, kept apart from the API suite's SQLite one."""
    engine = create_db_engine(database_url)
    downgrade(engine)  # reset the schema: TEST_DATABASE_URL may point at a used database
    upgrade(engine)
    yield engine
    engine.dispose()


def _clear(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in reversed(metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture(autouse=True)
def _empty_tables(engine: Engine) -> Iterator[None]:
    """AC-9.5: every test starts and ends with empty tables."""
    _clear(engine)
    yield
    _clear(engine)

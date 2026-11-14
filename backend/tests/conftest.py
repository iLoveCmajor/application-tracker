"""Shared test setup for tests/api and tests/integration.

Tests run against a real database: a temporary SQLite file by default, or any
SQLAlchemy URL in TEST_DATABASE_URL (e.g. a throwaway PostgreSQL). The schema is
built once per run with the Alembic migrations. Test folders that use the
database opt in to `empty_tables` in their own conftest.py, so unit tests never
open one.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import RepoFactory
from sqlalchemy import Engine

from app.db.engine import create_db_engine
from app.db.migrate import downgrade, upgrade
from app.db.tables import metadata
from app.main import create_app
from app.repositories.sql import SqlRepository


@pytest.fixture(scope="session")
def database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    path: Path = tmp_path_factory.mktemp("db") / "test.db"
    return f"sqlite:///{path}"


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_db_engine(database_url)
    downgrade(engine)  # start clean if TEST_DATABASE_URL points at a used database
    upgrade(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def empty_tables(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as connection:
        for table in reversed(metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture
def repo_factory(engine: Engine) -> RepoFactory:
    """Opens a repository on its own connection, like one request does."""

    @contextmanager
    def open_repo() -> Iterator[SqlRepository]:
        with engine.connect() as connection:
            yield SqlRepository(connection)

    return open_repo


@pytest.fixture
def repo(repo_factory: RepoFactory) -> Iterator[SqlRepository]:
    with repo_factory() as repository:
        yield repository


@pytest.fixture
def client(engine: Engine) -> TestClient:
    return TestClient(create_app(engine, migrate=False))

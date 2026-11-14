"""AC-1.1, AC-1.2: the schema, its migration, and migrating on start."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import Date, DateTime, Engine, String, Text, insert, inspect, select
from sqlalchemy.exc import IntegrityError, StatementError

from app.db.engine import create_db_engine
from app.db.migrate import downgrade, upgrade
from app.db.tables import applications, metadata, status_events
from app.main import create_app

BACKEND = Path(__file__).resolve().parents[2]
APP_TABLES = {"applications", "status_events"}
STATUSES = ["saved", "applied", "screen", "interview", "offer", "rejected", "ghosted"]
SOURCES = ["cold", "inbound", "referral"]

# The spec's Data model: column -> (generic type, max length or None, nullable).
APPLICATIONS_COLUMNS: dict[str, tuple[type, int | None, bool]] = {
    "id": (String, None, False),  # UUID; CHAR(32) on SQLite
    "company": (String, 100, False),
    "role": (String, 100, False),
    "link": (String, 500, True),
    "source": (String, None, False),
    "status": (String, None, False),
    "applied_date": (Date, None, True),
    "follow_up_date": (Date, None, True),
    "notes": (Text, None, True),
    "created_at": (DateTime, None, False),
    "updated_at": (DateTime, None, False),
}
STATUS_EVENTS_COLUMNS: dict[str, tuple[type, int | None, bool]] = {
    "id": (String, None, False),
    "application_id": (String, None, False),
    "from_status": (String, None, True),
    "to_status": (String, None, False),
    "note": (String, 500, True),
    "created_at": (DateTime, None, False),
}


@pytest.fixture
def fresh_engine(tmp_path: Path) -> Iterator[Engine]:
    """An empty database, separate from the shared test database."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    yield engine
    engine.dispose()


def table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def now() -> datetime:
    return datetime.now(UTC)


def application_row(**overrides: Any) -> dict[str, Any]:
    ts = now()
    row: dict[str, Any] = {
        "id": uuid4(),
        "company": "Northwind Analytics",
        "role": "ML Engineer",
        "source": "cold",
        "status": "saved",
        "created_at": ts,
        "updated_at": ts,
    }
    return row | overrides


def event_row(application_id: UUID, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": uuid4(),
        "application_id": application_id,
        "from_status": None,
        "to_status": "saved",
        "created_at": now(),
    }
    return row | overrides


# ---- AC-1.1: the migration ------------------------------------------------------


def test_ac1_1_alembic_cli_upgrades_and_downgrades_an_empty_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same path as `cd backend && uv run alembic upgrade head` (alembic.ini + DATABASE_URL)."""
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(BACKEND / "alembic.ini"))
    engine = create_db_engine(url)
    try:
        command.upgrade(config, "head")
        assert table_names(engine) >= APP_TABLES
        command.downgrade(config, "base")
        assert table_names(engine) & APP_TABLES == set()
    finally:
        engine.dispose()


def test_ac1_1_upgrade_downgrade_upgrade(fresh_engine: Engine) -> None:
    upgrade(fresh_engine)
    assert table_names(fresh_engine) >= APP_TABLES
    downgrade(fresh_engine)
    assert table_names(fresh_engine) & APP_TABLES == set()
    upgrade(fresh_engine)
    assert table_names(fresh_engine) >= APP_TABLES


@pytest.mark.parametrize(
    ("table", "expected"),
    [("applications", APPLICATIONS_COLUMNS), ("status_events", STATUS_EVENTS_COLUMNS)],
)
def test_ac1_1_columns_types_and_nullability(
    engine: Engine, table: str, expected: dict[str, tuple[type, int | None, bool]]
) -> None:
    columns = {c["name"]: c for c in inspect(engine).get_columns(table)}
    assert list(columns) == list(expected)
    for name, (generic, length, nullable) in expected.items():
        column = columns[name]
        assert isinstance(column["type"], generic), (name, column["type"])
        if length is not None:
            assert column["type"].length == length, name
        assert column["nullable"] is nullable, name


def test_ac1_1_primary_keys_foreign_key_and_index(engine: Engine) -> None:
    db = inspect(engine)
    assert db.get_pk_constraint("applications")["constrained_columns"] == ["id"]
    assert db.get_pk_constraint("status_events")["constrained_columns"] == ["id"]

    [fk] = db.get_foreign_keys("status_events")
    assert fk["constrained_columns"] == ["application_id"]
    assert fk["referred_table"] == "applications"
    assert fk["referred_columns"] == ["id"]
    assert fk["options"].get("ondelete") == "CASCADE"

    indexes = {tuple(ix["column_names"]) for ix in db.get_indexes("status_events")}
    assert ("application_id", "created_at") in indexes


def test_ac1_1_migrations_match_the_table_definitions(engine: Engine) -> None:
    """Fails when tables.py changes without a matching Alembic migration."""
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), metadata)
    assert diff == []


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("source", SOURCES)
def test_ac1_1_every_enum_value_is_accepted(engine: Engine, status: str, source: str) -> None:
    app_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            insert(applications).values(application_row(id=app_id, status=status, source=source))
        )
        connection.execute(
            insert(status_events).values(event_row(app_id, from_status=status, to_status=status))
        )


@pytest.mark.parametrize(
    "bad",
    [
        {"status": "archived"},
        {"source": "agency"},
        {"company": ""},
        {"role": ""},
        {"company": "x" * 101},
        {"link": "x" * 501},
        {"notes": "x" * 5001},
        {"company": None},
        {"source": None},
        {"status": None},
    ],
)
def test_ac1_1_database_rejects_invalid_applications(engine: Engine, bad: dict[str, Any]) -> None:
    with pytest.raises((IntegrityError, StatementError)), engine.begin() as connection:
        connection.execute(insert(applications).values(application_row(**bad)))


@pytest.mark.parametrize(
    "bad",
    [{"to_status": "archived"}, {"from_status": "archived"}, {"to_status": None}, {"note": "x" * 501}],
)
def test_ac1_1_database_rejects_invalid_events(engine: Engine, bad: dict[str, Any]) -> None:
    app_id = uuid4()
    with engine.begin() as connection:
        connection.execute(insert(applications).values(application_row(id=app_id)))
    with pytest.raises((IntegrityError, StatementError)), engine.begin() as connection:
        connection.execute(insert(status_events).values(event_row(app_id, **bad)))


def test_ac1_1_event_needs_an_existing_application(engine: Engine) -> None:
    # Foreign keys are enforced (SQLite needs PRAGMA foreign_keys, set by create_db_engine).
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert(status_events).values(event_row(uuid4())))


def test_ac1_1_deleting_an_application_cascades_to_its_events(engine: Engine) -> None:
    app_id = uuid4()
    with engine.begin() as connection:
        connection.execute(insert(applications).values(application_row(id=app_id)))
        connection.execute(insert(status_events).values(event_row(app_id)))
        connection.execute(applications.delete().where(applications.c.id == app_id))
        assert connection.execute(select(status_events)).all() == []


def test_ac1_1_values_round_trip(engine: Engine) -> None:
    plus_two = timezone(timedelta(hours=2))
    created = datetime(2026, 10, 2, 12, 30, 15, 123456, tzinfo=plus_two)
    app_id = uuid4()
    row = application_row(
        id=app_id,
        link="https://jobs.example.com/1",
        applied_date=date(2026, 11, 1),
        follow_up_date=date(2026, 11, 8),
        notes="n" * 5000,
        created_at=created,
        updated_at=created,
    )
    with engine.begin() as connection:
        connection.execute(insert(applications).values(row))
        loaded = connection.execute(select(applications)).mappings().one()
    assert loaded["id"] == app_id
    assert loaded["applied_date"] == date(2026, 11, 1)
    assert loaded["created_at"] == created
    assert loaded["created_at"].tzinfo == UTC
    assert loaded["created_at"].microsecond == 123456


def test_ac1_1_naive_timestamps_are_rejected(engine: Engine) -> None:
    naive = datetime(2026, 10, 2, 12, 0)
    with pytest.raises(StatementError, match="Naive datetimes"), engine.begin() as connection:
        connection.execute(insert(applications).values(application_row(created_at=naive)))


# ---- AC-1.2: migrate on start ---------------------------------------------------


def test_ac1_2_app_migrates_an_empty_database_on_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'tracker.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_db_engine(url)
    try:
        assert table_names(engine) == set()
        with TestClient(create_app()) as client:  # `with` runs the startup hook
            assert table_names(engine) >= APP_TABLES
            assert client.get("/ready").status_code == 200
    finally:
        engine.dispose()

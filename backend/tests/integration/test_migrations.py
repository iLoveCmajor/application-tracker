"""AC-9.2: the Alembic migration on an empty PostgreSQL database, up and down."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.migrate import downgrade, upgrade

TABLES = {"applications", "status_events"}


@pytest.fixture
def fresh_schema(engine: Engine) -> Iterator[Engine]:
    """An empty database migrated to head; the session's schema is put back afterwards."""
    downgrade(engine)
    assert not TABLES & set(inspect(engine).get_table_names())
    try:
        upgrade(engine)
        yield engine
    finally:
        downgrade(engine)
        upgrade(engine)


def test_ac9_2_upgrade_creates_both_tables(fresh_schema: Engine) -> None:
    inspector = inspect(fresh_schema)
    assert set(inspector.get_table_names()) >= TABLES
    columns = {c["name"] for c in inspector.get_columns("applications")}
    assert {"id", "company", "role", "link", "source", "status", "applied_date", "follow_up_date"} <= columns
    assert {c["name"] for c in inspector.get_columns("status_events")} == {
        "id",
        "application_id",
        "from_status",
        "to_status",
        "note",
        "created_at",
    }
    assert fresh_schema.dialect.name == "postgresql"


def test_ac9_2_enums_are_enforced(fresh_schema: Engine) -> None:
    inspector = inspect(fresh_schema)
    app_checks = {c["name"]: c["sqltext"] for c in inspector.get_check_constraints("applications")}
    event_checks = {c["name"] for c in inspector.get_check_constraints("status_events")}
    assert {"ck_applications_status", "ck_applications_source"} <= set(app_checks)
    assert {"ck_status_events_from_status", "ck_status_events_to_status"} <= event_checks
    for value in ("saved", "applied", "screen", "interview", "offer", "rejected", "ghosted"):
        assert value in app_checks["ck_applications_status"]

    insert = text(
        "INSERT INTO applications (id, company, role, source, status, created_at, updated_at) "
        "VALUES (:id, 'Fernhill Data', 'ML Engineer', 'cold', :status, now(), now())"
    )
    with fresh_schema.begin() as connection:
        connection.execute(insert, {"id": uuid4(), "status": "applied"})
    with pytest.raises(IntegrityError), fresh_schema.begin() as connection:
        connection.execute(insert, {"id": uuid4(), "status": "hired"})


def test_ac9_2_events_foreign_key_cascades(fresh_schema: Engine) -> None:
    (fk,) = inspect(fresh_schema).get_foreign_keys("status_events")
    assert fk["referred_table"] == "applications"
    assert fk["constrained_columns"] == ["application_id"]
    assert fk["options"].get("ondelete") == "CASCADE"


def test_ac9_2_events_index_on_application_and_created_at(fresh_schema: Engine) -> None:
    indexes = inspect(fresh_schema).get_indexes("status_events")
    assert any(ix["column_names"] == ["application_id", "created_at"] for ix in indexes), indexes


def test_ac9_2_downgrade_base_leaves_no_tables(fresh_schema: Engine) -> None:
    downgrade(fresh_schema)
    assert set(inspect(fresh_schema).get_table_names()) <= {"alembic_version"}

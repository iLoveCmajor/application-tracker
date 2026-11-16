"""AC-33.1 and AC-33.2 on PostgreSQL: a database error's server text never reaches the ERROR log line."""

import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.logs import configure_logging
from app.main import create_app

CANARY = "db-detail-canary-33"
FAILING_INSERT = text(
    "INSERT INTO applications (id, company, role, source, status, created_at, updated_at) "
    "VALUES (gen_random_uuid(), :company, 'Engineer', 'cold', 'bogus', now(), now())"
)


@pytest.fixture
def logging_reset() -> Iterator[None]:
    root = logging.getLogger()
    level = root.level
    yield
    for handler in list(root.handlers):
        if getattr(handler, "_app_json", False):
            root.removeHandler(handler)
    root.setLevel(level)


def failing_client(engine: Engine) -> TestClient:
    app = create_app(engine, migrate=False)

    def fail() -> None:
        with engine.begin() as connection:
            connection.execute(FAILING_INSERT, {"company": CANARY})

    app.add_api_route("/test-only/constraint-failure", fail, methods=["POST"])
    return TestClient(app, raise_server_exceptions=False)


def error_lines(out: str) -> list[dict[str, Any]]:
    entries = [json.loads(line) for line in out.splitlines() if line.strip()]
    return [e for e in entries if e["level"] == "ERROR"]


def test_ac33_1_postgres_error_text_leaks_but_the_log_line_does_not(
    engine: Engine, capsys: pytest.CaptureFixture[str], logging_reset: None
) -> None:
    with pytest.raises(DBAPIError) as raised, engine.begin() as connection:
        connection.execute(FAILING_INSERT, {"company": CANARY})
    # Precondition: without the fix the raw error text carries the application value.
    assert CANARY in str(raised.value.orig)
    assert "DETAIL" in str(raised.value.orig)

    configure_logging()
    capsys.readouterr()
    res = failing_client(engine).post("/test-only/constraint-failure", headers={"X-Request-ID": "pg-33"})
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "internal_error"
    assert res.headers["X-Request-ID"] == "pg-33"
    out = capsys.readouterr().out
    (line,) = error_lines(out)
    assert (line["request_id"], line["status"], line["method"]) == ("pg-33", 500, "POST")
    assert CANARY not in out
    assert "DETAIL" not in out and "Failing row contains" not in out
    assert "violates check constraint" not in out


def test_ac33_2_postgres_error_line_names_class_and_sqlstate(
    engine: Engine, capsys: pytest.CaptureFixture[str], logging_reset: None
) -> None:
    configure_logging()
    capsys.readouterr()
    failing_client(engine).post("/test-only/constraint-failure")
    (line,) = error_lines(capsys.readouterr().out)
    assert "IntegrityError" in line["exc_info"]
    assert "CheckViolation" in line["exc_info"]
    assert "23514" in line["exc_info"]

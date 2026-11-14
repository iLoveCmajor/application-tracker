"""AC-12.1 to AC-12.5: JSON request logs with a request id, no private data, LOG_LEVEL, errors."""

import json
import logging
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from helpers import API, assert_error, change_status, create_application

from app.logs import configure_logging

REQUEST_FIELDS = {"timestamp", "level", "message", "request_id", "method", "path", "status", "duration_ms"}

CLIENT_LOGGERS = ("httpx", "httpcore")

ReadLogs = Callable[[], list[dict[str, Any]]]


@pytest.fixture
def logs(capsys: pytest.CaptureFixture[str]) -> Iterator[ReadLogs]:
    """Configures logging as the app does at start, and returns a reader for what reached stdout.

    The reader fails the test if any stdout line is not a JSON object (AC-12.1).
    """
    root = logging.getLogger()
    level = root.level
    capsys.readouterr()

    def read() -> list[dict[str, Any]]:
        lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
        entries = [json.loads(line) for line in lines]
        assert all(isinstance(entry, dict) for entry in entries), lines
        # The test client's own HTTP library logs too; those lines are the client's, not the app's.
        return [entry for entry in entries if not entry["logger"].startswith(CLIENT_LOGGERS)]

    yield read
    for handler in list(root.handlers):
        if getattr(handler, "_app_json", False):
            root.removeHandler(handler)
    root.setLevel(level)


@pytest.fixture
def info_logs(logs: ReadLogs, monkeypatch: pytest.MonkeyPatch) -> ReadLogs:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
    return logs


def request_lines(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in entries if "path" in entry]


def boom_client(client: TestClient) -> TestClient:
    app = client.app
    assert isinstance(app, FastAPI)

    def boom() -> None:
        raise RuntimeError("boom: secret detail")

    app.add_api_route("/test-only/boom", boom)
    return TestClient(app, raise_server_exceptions=False)


# ---- AC-12.1 --------------------------------------------------------------------


def test_ac12_1_each_request_logs_one_json_line_with_the_fields(
    client: TestClient, info_logs: ReadLogs
) -> None:
    client.get("/health")
    client.get(f"{API}/stats/funnel")
    lines = request_lines(info_logs())
    assert [(line["method"], line["path"], line["status"]) for line in lines] == [
        ("GET", "/health", 200),
        ("GET", f"{API}/stats/funnel", 200),
    ]
    for line in lines:
        assert set(line) >= REQUEST_FIELDS
        assert line["level"] == "INFO"
        assert isinstance(line["duration_ms"], int | float) and line["duration_ms"] >= 0
        assert line["timestamp"].endswith("+00:00")
        assert line["request_id"]


def test_ac12_1_other_log_lines_are_json_too(info_logs: ReadLogs) -> None:
    logging.getLogger("app.anything").warning("plain %s", "message")
    logging.getLogger("uvicorn.error").info("Started server process [1]")
    entries = info_logs()
    assert [(e["level"], e["message"]) for e in entries] == [
        ("WARNING", "plain message"),
        ("INFO", "Started server process [1]"),
    ]


def test_ac12_1_uvicorn_access_log_is_off_so_each_request_is_one_line(info_logs: ReadLogs) -> None:
    logging.getLogger("uvicorn.access").info('127.0.0.1 - "GET /health HTTP/1.1" 200')
    assert info_logs() == []


# ---- AC-12.2 --------------------------------------------------------------------


def test_ac12_2_incoming_request_id_is_echoed_and_logged(client: TestClient, info_logs: ReadLogs) -> None:
    res = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert res.headers["X-Request-ID"] == "abc-123"
    (line,) = request_lines(info_logs())
    assert line["request_id"] == "abc-123"


def test_ac12_2_missing_request_id_is_generated_and_matches_the_log(
    client: TestClient, info_logs: ReadLogs
) -> None:
    first = client.get("/health").headers["X-Request-ID"]
    second = client.get("/health").headers["X-Request-ID"]
    assert first and second and first != second
    assert [line["request_id"] for line in request_lines(info_logs())] == [first, second]


def test_ac12_2_error_responses_carry_the_request_id(client: TestClient, info_logs: ReadLogs) -> None:
    res = client.get(f"{API}/nope", headers={"X-Request-ID": "abc-404"})
    assert_error(res, 404, "not_found")
    assert res.headers["X-Request-ID"] == "abc-404"
    (line,) = request_lines(info_logs())
    assert (line["status"], line["request_id"]) == (404, "abc-404")


@pytest.mark.parametrize("bad", ["has space", "x" * 129, "semi;colon", ""])
def test_ac12_2_an_unusable_request_id_is_replaced(client: TestClient, info_logs: ReadLogs, bad: str) -> None:
    res = client.get("/health", headers={"X-Request-ID": bad})
    generated = res.headers["X-Request-ID"]
    assert generated != bad and generated
    (line,) = request_lines(info_logs())
    assert line["request_id"] == generated


# ---- AC-12.3 --------------------------------------------------------------------


def test_ac12_3_no_bodies_or_application_fields_in_logs(client: TestClient, info_logs: ReadLogs) -> None:
    marker = uuid.uuid4().hex
    company = f"Zylophant Labs {marker}"
    note = f"private note {marker}"
    created = create_application(client, company=company, notes=note)
    client.patch(f"{API}/applications/{created['id']}", json={"notes": f"{note} edited", "role": marker})
    change_status(client, created["id"], "applied", note=f"status note {marker}")
    client.post(f"{API}/applications", json={"company": f"{company} invalid", "role": "", "source": "x"})
    client.get(f"{API}/applications?q={marker}&status=applied")

    entries = info_logs()
    raw = json.dumps(entries)
    assert marker not in raw
    assert "Zylophant" not in raw
    assert "private note" not in raw
    lines = request_lines(entries)
    assert len(lines) == 5
    assert all("?" not in line["path"] for line in lines)
    assert lines[-1]["path"] == f"{API}/applications"


def test_ac12_3_debug_level_does_not_leak_sql_parameters(
    client: TestClient, logs: ReadLogs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    marker = uuid.uuid4().hex
    create_application(client, company=f"Quillmoor {marker}", notes=marker)
    assert marker not in json.dumps(logs())


# ---- AC-12.4 --------------------------------------------------------------------


def test_ac12_4_default_level_is_info(info_logs: ReadLogs) -> None:
    assert logging.getLogger().level == logging.INFO


def test_ac12_4_warning_level_drops_info_request_lines(
    client: TestClient, logs: ReadLogs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    configure_logging()
    client.get("/health")
    client.get(f"{API}/stats/funnel")
    logging.getLogger("app.anything").warning("still written")
    assert [e["message"] for e in logs()] == ["still written"]


def test_ac12_4_lowercase_level_works(
    client: TestClient, logs: ReadLogs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "warning")
    configure_logging()
    client.get("/health")
    assert logs() == []


# ---- AC-12.5 --------------------------------------------------------------------


def test_ac12_5_unhandled_exception_logs_one_error_line_with_the_request_id(
    client: TestClient, info_logs: ReadLogs
) -> None:
    failing = boom_client(client)
    res = failing.get("/test-only/boom", headers={"X-Request-ID": "abc-500"})
    error = assert_error(res, 500, "internal_error")
    assert error["details"] == {}
    assert res.headers["X-Request-ID"] == "abc-500"
    assert "Traceback" not in res.text and "boom" not in res.text and "RuntimeError" not in res.text

    entries = info_logs()
    errors = [e for e in entries if e["level"] == "ERROR"]
    assert len(errors) == 1
    (line,) = errors
    assert line["request_id"] == "abc-500"
    assert (line["method"], line["path"], line["status"]) == ("GET", "/test-only/boom", 500)
    assert "RuntimeError" in line["exc_info"]
    assert request_lines(entries) == [line]

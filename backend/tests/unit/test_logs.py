"""AC-12.4: LOG_LEVEL parsing, and the JSON line format (AC-12.1)."""

import json
import logging

import pytest

from app.logs import JsonFormatter, log_level, request_id_var


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "INFO"), ("", "INFO"), ("warning", "WARNING"), (" DEBUG ", "DEBUG"), ("loud", "INFO")],
)
def test_ac12_4_log_level_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: str
) -> None:
    if value is None:
        monkeypatch.delenv("LOG_LEVEL", raising=False)
    else:
        monkeypatch.setenv("LOG_LEVEL", value)
    assert log_level() == expected


def test_ac12_1_formatter_writes_one_json_object_with_the_request_id() -> None:
    record = logging.LogRecord("app.x", logging.INFO, __file__, 1, "line\nbreak %s", ("arg",), None)
    record.status = 201
    record.company = "never copied"
    token = request_id_var.set("rid-1")
    try:
        text = JsonFormatter().format(record)
    finally:
        request_id_var.reset(token)
    assert "\n" not in text
    entry = json.loads(text)
    assert entry["message"] == "line\nbreak arg"
    assert entry["request_id"] == "rid-1"
    assert entry["level"] == "INFO"
    assert entry["status"] == 201
    assert "company" not in entry

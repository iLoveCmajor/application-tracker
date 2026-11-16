"""AC-29.1 to AC-29.5: OpenTelemetry traces, metrics and logs, tested with in-memory exporters."""

import json
import logging
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from helpers import API, MISSING_ID, assert_error, change_status, create_application
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricExporter, MetricReader
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, format_span_id, format_trace_id
from sqlalchemy import Engine

from app import telemetry as telemetry_module
from app.logs import configure_logging
from app.main import create_app
from app.telemetry import (
    REQUEST_DURATION,
    STATUS_CHANGES,
    Telemetry,
    build_telemetry,
    telemetry_from_env,
    uninstrument,
)

STATUS_ROUTE = f"{API}/applications/{{id}}/status"
CLIENT_LOGGERS = ("httpx", "httpcore")
REQUEST_FIELDS = {"timestamp", "level", "message", "request_id", "method", "path", "status", "duration_ms"}


@dataclass
class Signals:
    """An app with telemetry on, exporting into memory."""

    client: TestClient
    telemetry: Telemetry
    spans_out: InMemorySpanExporter
    metrics_in: InMemoryMetricReader
    logs_out: InMemoryLogRecordExporter

    def spans(self) -> list[ReadableSpan]:
        self.telemetry.tracer_provider.force_flush()
        return list(self.spans_out.get_finished_spans())

    def metric_points(self, name: str) -> list[Any]:
        data = self.metrics_in.get_metrics_data()
        points: list[Any] = []
        for resource_metrics in data.resource_metrics if data else []:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    if metric.name == name:
                        points += list(metric.data.data_points)
        return points

    def status_change_counts(self) -> dict[tuple[str, str], int]:
        return {
            (p.attributes["from"], p.attributes["to"]): p.value for p in self.metric_points(STATUS_CHANGES)
        }

    def log_records(self) -> list[Any]:
        self.telemetry.logger_provider.force_flush()
        return [data.log_record for data in self.logs_out.get_finished_logs()]


ReadStdout = Callable[[], list[dict[str, Any]]]


@pytest.fixture
def stdout_logs(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> Iterator[ReadStdout]:
    """JSON logging as the app configures it; returns the app's lines that reached stdout."""
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    root = logging.getLogger()
    level = root.level
    configure_logging()
    capsys.readouterr()

    def read() -> list[dict[str, Any]]:
        entries = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
        assert all(isinstance(entry, dict) for entry in entries)
        return [entry for entry in entries if not entry["logger"].startswith(CLIENT_LOGGERS)]

    yield read
    for handler in list(root.handlers):
        if getattr(handler, "_app_json", False):
            root.removeHandler(handler)
    root.setLevel(level)


@pytest.fixture
def signals(engine: Engine, stdout_logs: ReadStdout) -> Iterator[Signals]:
    spans_out, metrics_in, logs_out = (
        InMemorySpanExporter(),
        InMemoryMetricReader(),
        InMemoryLogRecordExporter(),
    )
    telemetry = build_telemetry(spans_out, metrics_in, logs_out)
    app = create_app(engine, migrate=False, telemetry=telemetry)
    yield Signals(TestClient(app), telemetry, spans_out, metrics_in, logs_out)
    uninstrument(app)
    telemetry.shutdown()


def request_lines(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in entries if "path" in entry]


def status_trace(spans: list[ReadableSpan]) -> tuple[ReadableSpan, ReadableSpan]:
    """The one server span of a status-change request and its one `change_status` child."""
    (server,) = [s for s in spans if s.kind == SpanKind.SERVER and s.name == f"POST {STATUS_ROUTE}"]
    assert server.context is not None
    trace_id = server.context.trace_id
    in_trace = [s for s in spans if s.context is not None and s.context.trace_id == trace_id]
    (child,) = [s for s in in_trace if s is not server]
    return server, child


# ---- AC-29.1 --------------------------------------------------------------------


def test_ac29_1_without_the_endpoint_telemetry_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert telemetry_from_env() is None
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "  ")
    assert telemetry_from_env() is None


def test_ac29_1_with_telemetry_off_the_app_serves_and_exports_nothing(
    engine: Engine, stdout_logs: ReadStdout, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    def no_export(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("an exporter was created with telemetry off")

    for name in ("BatchSpanProcessor", "BatchLogRecordProcessor", "PeriodicExportingMetricReader"):
        monkeypatch.setattr(telemetry_module, name, no_export)

    app = create_app(engine, migrate=False, telemetry=telemetry_from_env())
    with TestClient(app) as client:
        created = create_application(client)
        change_status(client, created["id"], "applied")
        assert client.get("/health").status_code == 200

    root = logging.getLogger()
    assert not [h for h in root.handlers if getattr(h, "_app_otlp", False)]
    entries = stdout_logs()
    assert not [e for e in entries if e["logger"].startswith("opentelemetry")]
    assert not [e for e in entries if e["level"] in {"WARNING", "ERROR"}]


def test_ac29_1_with_the_endpoint_the_otlp_pipeline_is_built(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid:4318")
    readers: list[MetricExporter] = []

    def in_memory_reader(exporter: MetricExporter) -> MetricReader:
        readers.append(exporter)
        return InMemoryMetricReader()

    monkeypatch.setattr(telemetry_module, "PeriodicExportingMetricReader", in_memory_reader)
    telemetry = telemetry_from_env()
    assert telemetry is not None
    assert len(readers) == 1
    telemetry.shutdown()  # nothing was recorded, so nothing is sent


# ---- AC-29.2 --------------------------------------------------------------------


def test_ac29_2_status_change_is_one_trace_with_a_server_span_and_a_child(signals: Signals) -> None:
    created = create_application(signals.client)
    change_status(signals.client, created["id"], "applied")

    server, child = status_trace(signals.spans())
    assert server.parent is None
    assert server.attributes is not None and server.attributes["http.route"] == STATUS_ROUTE
    assert server.attributes["http.response.status_code"] == 200
    assert child.name == "change_status"
    assert child.parent is not None and server.context is not None
    assert child.parent.span_id == server.context.span_id
    assert dict(child.attributes or {}) == {
        "app.application.id": created["id"],
        "app.status.from": "saved",
        "app.status.to": "applied",
    }


def test_ac29_2_health_checks_are_not_traced(signals: Signals) -> None:
    signals.client.get("/health")
    signals.client.get("/ready")
    assert signals.spans() == []


# ---- AC-29.3 --------------------------------------------------------------------


def test_ac29_3_counter_adds_one_per_successful_change_with_from_and_to(signals: Signals) -> None:
    first = create_application(signals.client)
    second = create_application(signals.client)
    change_status(signals.client, first["id"], "applied")
    change_status(signals.client, second["id"], "applied")
    change_status(signals.client, first["id"], "screen")
    assert signals.status_change_counts() == {("saved", "applied"): 2, ("applied", "screen"): 1}


def test_ac29_3_a_409_or_404_adds_nothing(signals: Signals) -> None:
    created = create_application(signals.client)
    change_status(signals.client, created["id"], "applied")
    before = signals.status_change_counts()

    res = signals.client.post(f"{API}/applications/{created['id']}/status", json={"status": "applied"})
    assert_error(res, 409, "invalid_transition")
    res = signals.client.post(f"{API}/applications/{MISSING_ID}/status", json={"status": "applied"})
    assert_error(res, 404, "not_found")

    assert before == {("saved", "applied"): 1}
    assert signals.status_change_counts() == before


def test_ac29_3_request_duration_histogram_by_route(signals: Signals) -> None:
    created = create_application(signals.client)
    change_status(signals.client, created["id"], "applied")

    points = signals.metric_points(REQUEST_DURATION)
    by_route = {p.attributes["http.route"]: p for p in points}
    point = by_route[STATUS_ROUTE]
    assert point.count == 1 and point.sum > 0
    assert dict(point.attributes) == {
        "http.request.method": "POST",
        "http.route": STATUS_ROUTE,
        "http.response.status_code": 200,
    }


def test_ac29_3_counter_carries_the_trace_as_an_exemplar(signals: Signals) -> None:
    """So Grafana can jump from the metric to the trace."""
    created = create_application(signals.client)
    change_status(signals.client, created["id"], "applied")
    server, _ = status_trace(signals.spans())
    (point,) = signals.metric_points(STATUS_CHANGES)
    assert server.context is not None
    assert [e.trace_id for e in point.exemplars] == [server.context.trace_id]


# ---- AC-29.4 --------------------------------------------------------------------


def test_ac29_4_request_log_line_has_the_trace_and_span_of_its_request(
    signals: Signals, stdout_logs: ReadStdout
) -> None:
    created = create_application(signals.client)
    change_status(signals.client, created["id"], "applied")

    server, _ = status_trace(signals.spans())
    assert server.context is not None
    lines = request_lines(stdout_logs())
    assert len(lines) == 2
    for line in lines:
        assert set(line) >= REQUEST_FIELDS | {"trace_id", "span_id"}
    status_line = lines[-1]
    assert status_line["trace_id"] == format_trace_id(server.context.trace_id)
    assert status_line["span_id"] == format_span_id(server.context.span_id)


def test_ac29_4_exported_log_records_are_the_stdout_lines_with_the_trace(
    signals: Signals, stdout_logs: ReadStdout
) -> None:
    created = create_application(signals.client)
    change_status(signals.client, created["id"], "applied")

    server, _ = status_trace(signals.spans())
    assert server.context is not None
    status_line = request_lines(stdout_logs())[-1]
    records = [r for r in signals.log_records() if json.loads(str(r.body)).get("path") == status_line["path"]]
    (record,) = records
    assert json.loads(str(record.body)) == status_line
    assert record.trace_id == server.context.trace_id
    assert record.span_id == server.context.span_id
    assert not record.attributes


def test_ac29_4_with_telemetry_off_log_lines_are_the_12_fields(
    client: TestClient, stdout_logs: ReadStdout
) -> None:
    created = create_application(client)
    change_status(client, created["id"], "applied")
    lines = request_lines(stdout_logs())
    assert len(lines) == 2
    for line in lines:
        assert set(line) == REQUEST_FIELDS | {"logger"}
        assert "trace_id" not in line and "span_id" not in line


# ---- AC-29.5 --------------------------------------------------------------------


def test_ac29_5_no_application_fields_or_credentials_in_any_signal(
    signals: Signals, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = uuid.uuid4().hex
    password = f"pw-{marker}"
    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg://tracker:{password}@db:5432/tracker")
    secrets = {
        "company": f"Brindlewick {marker}",
        "role": f"Glassblower {marker}",
        "notes": f"private note {marker}",
        "link": f"https://jobs.example.com/{marker}?ref={marker}",
        "note": f"status note {marker}",
        "query": f"q{marker}",
        "password": password,
    }
    client = signals.client
    created = create_application(
        client,
        company=secrets["company"],
        role=secrets["role"],
        notes=secrets["notes"],
        link=secrets["link"],
    )
    change_status(client, created["id"], "applied", note=secrets["note"])
    # A rejected change and a query string must not leak either.
    res = client.post(
        f"{API}/applications/{created['id']}/status", json={"status": "applied", "note": secrets["note"]}
    )
    assert_error(res, 409, "invalid_transition")
    client.post(f"{API}/applications/{created['id']}/status?x={secrets['query']}", json={"status": "screen"})
    client.get(f"{API}/applications?q={secrets['query']}")

    spans = signals.spans()
    exported: list[Any] = []
    for span in spans:
        exported += [span.name, dict(span.attributes or {}), span.status.description]
        exported += [(e.name, dict(e.attributes or {})) for e in span.events]
        exported.append(dict(span.resource.attributes))
    for name in (STATUS_CHANGES, REQUEST_DURATION):
        exported += [dict(p.attributes) for p in signals.metric_points(name)]
    for record in signals.log_records():
        if json.loads(str(record.body))["logger"].startswith(CLIENT_LOGGERS):
            continue  # the test client's own lines (it logs the URLs it calls), not the app's
        exported += [record.body, dict(record.attributes or {})]
    dump = json.dumps(exported, default=str)

    assert spans and created["id"] in dump  # ids may appear
    for field, value in secrets.items():
        assert value not in dump, field
    assert marker not in dump
    # The rejected change is traced as an error, with no exception message attached.
    errors = [s for s in spans if s.name == "change_status" and s.events]
    assert errors
    for span in errors:
        assert all(set(e.attributes or {}) <= {"exception.type", "exception.escaped"} for e in span.events)

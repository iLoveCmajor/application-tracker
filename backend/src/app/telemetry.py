"""OpenTelemetry traces, metrics and logs (#29). Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set.

With the endpoint set, the app exports over OTLP/HTTP to that collector:

- traces: one server span per request (FastAPI instrumentation) and a child span for a status change;
- metrics: `app.status_changes` (counter, `from`/`to`) and `http.server.request.duration` (histogram);
- logs: the same JSON lines the app writes to stdout (app/logs.py), with the trace context attached.

No application fields or credentials reach any signal. Span attributes, span event attributes and
metric attributes pass through allowlists (below), so whatever an instrumentation library records
by default (query strings, client address, user agent, exception messages) is dropped before export.
Request bodies are never read. Log bodies are the JSON lines, which carry no application fields (#12).

Without the endpoint nothing is set up: no providers, no exporters, no background threads, so
nothing tries to connect anywhere. The status-change span and counter are then no-ops.
"""

import logging
import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from opentelemetry import context as otel_context
from opentelemetry import metrics, trace
from opentelemetry._logs import SeverityNumber
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogRecordExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import DropAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Span, Status

from app.config import app_version, otel_endpoint
from app.logs import JsonFormatter

SERVICE_NAME = "application-tracker"
SCOPE = "app"

STATUS_CHANGES = "app.status_changes"
REQUEST_DURATION = "http.server.request.duration"

# Health checks run every few seconds (Docker, Render): no traces for them.
EXCLUDED_URLS = "/health,/ready"

# Span attributes that may leave the process. Everything else is dropped on export.
SPAN_ATTRIBUTES = frozenset(
    {
        "http.request.method",
        "http.route",
        "http.response.status_code",
        "url.scheme",
        "network.protocol.version",
        "error.type",
        "app.application.id",
        "app.status.from",
        "app.status.to",
    }
)
# Span event attributes: an exception event keeps its type only, never its message or traceback.
EVENT_ATTRIBUTES = frozenset({"exception.type", "exception.escaped"})
# Metric attributes, per instrument. Instruments not listed here are not exported.
METRIC_ATTRIBUTES = {
    STATUS_CHANGES: frozenset({"from", "to"}),
    REQUEST_DURATION: frozenset({"http.request.method", "http.route", "http.response.status_code"}),
}
# What the HTTP instrumentation records besides the duration histogram; none of it is needed.
_UNUSED_HTTP_INSTRUMENTS = (
    "http.server.active_requests",
    "http.server.request.body.size",
    "http.server.response.body.size",
    "http.server.duration",
    "http.server.request.size",
    "http.server.response.size",
)

_SEVERITY = {
    logging.DEBUG: SeverityNumber.DEBUG,
    logging.INFO: SeverityNumber.INFO,
    logging.WARNING: SeverityNumber.WARN,
    logging.ERROR: SeverityNumber.ERROR,
    logging.CRITICAL: SeverityNumber.FATAL,
}

# The status-change span and counter. No-ops until `instrument` installs real ones.
_tracer: trace.Tracer = trace.NoOpTracer()
_status_changes: metrics.Counter = metrics.NoOpMeter(SCOPE).create_counter(STATUS_CHANGES)


@dataclass
class Telemetry:
    """The three SDK providers the app exports through. Kept local, never installed globally."""

    tracer_provider: TracerProvider
    meter_provider: MeterProvider
    logger_provider: LoggerProvider

    def shutdown(self) -> None:
        self.tracer_provider.shutdown()
        self.meter_provider.shutdown()
        self.logger_provider.shutdown()


class AllowlistSpanExporter(SpanExporter):
    """Passes spans on with only the allowlisted attributes, and no status description."""

    def __init__(self, exporter: SpanExporter) -> None:
        self._exporter = exporter

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self._exporter.export([_scrub(span) for span in spans])

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._exporter.force_flush(timeout_millis)


def _keep(attributes: Any, allowed: frozenset[str]) -> dict[str, Any]:
    return {key: value for key, value in dict(attributes or {}).items() if key in allowed}


def _scrub(span: ReadableSpan) -> ReadableSpan:
    return ReadableSpan(
        name=span.name,
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=_keep(span.attributes, SPAN_ATTRIBUTES),
        events=[
            Event(event.name, _keep(event.attributes, EVENT_ATTRIBUTES), event.timestamp)
            for event in span.events
        ],
        links=span.links,
        kind=span.kind,
        status=Status(span.status.status_code),
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


def metric_views() -> list[View]:
    views = [View(instrument_name=name, attribute_keys=set(keys)) for name, keys in METRIC_ATTRIBUTES.items()]
    views += [View(instrument_name=name, aggregation=DropAggregation()) for name in _UNUSED_HTTP_INSTRUMENTS]
    return views


def build_telemetry(
    span_exporter: SpanExporter, metric_reader: MetricReader, log_exporter: LogRecordExporter
) -> Telemetry:
    resource = Resource.create({"service.name": SERVICE_NAME, "service.version": app_version()})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(AllowlistSpanExporter(span_exporter)))
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader], views=metric_views())
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    return Telemetry(tracer_provider, meter_provider, logger_provider)


def telemetry_from_env() -> Telemetry | None:
    """OTLP/HTTP exporters to OTEL_EXPORTER_OTLP_ENDPOINT, or None (telemetry off) when it is unset.

    The exporters read the endpoint and the other standard OTEL_* variables themselves, e.g.
    OTEL_METRIC_EXPORT_INTERVAL. They are imported here so an app without the endpoint never loads them.
    """
    if otel_endpoint() is None:
        return None
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    return build_telemetry(
        OTLPSpanExporter(), PeriodicExportingMetricReader(OTLPMetricExporter()), OTLPLogExporter()
    )


class OtlpLogHandler(logging.Handler):
    """Sends each log line, formatted exactly as on stdout, to the OTLP logs pipeline.

    The record carries the current trace context, so the collector and Loki see trace_id and span_id
    as well. It adds no attributes of its own. The SDK's own log lines are skipped, so a failing export
    can't feed itself.
    """

    _app_otlp = True

    def __init__(self, logger_provider: LoggerProvider) -> None:
        super().__init__()
        self._logger = logger_provider.get_logger(SCOPE)
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("opentelemetry"):
            return
        try:
            self._logger.emit(
                timestamp=int(record.created * 1e9),
                context=otel_context.get_current(),
                severity_number=_SEVERITY.get(record.levelno, SeverityNumber.UNSPECIFIED),
                severity_text=record.levelname,
                body=self.format(record),
            )
        except Exception:
            self.handleError(record)


def instrument(app: FastAPI, telemetry: Telemetry) -> None:
    """Traces and metrics for every request, the status-change span and counter, and OTLP logs."""
    global _tracer, _status_changes
    # The stable HTTP conventions: http.route, http.response.status_code, seconds for durations.
    os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=telemetry.tracer_provider,
        meter_provider=telemetry.meter_provider,
        excluded_urls=EXCLUDED_URLS,
        exclude_spans=["receive", "send"],
    )
    _tracer = telemetry.tracer_provider.get_tracer(SCOPE)
    _status_changes = telemetry.meter_provider.get_meter(SCOPE).create_counter(
        STATUS_CHANGES, unit="{change}", description="Successful application status changes"
    )
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_app_otlp", False):
            root.removeHandler(handler)
    root.addHandler(OtlpLogHandler(telemetry.logger_provider))


def uninstrument(app: FastAPI) -> None:
    """Undoes `instrument` (tests)."""
    global _tracer, _status_changes
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.uninstrument_app(app)
    _tracer = trace.NoOpTracer()
    _status_changes = metrics.NoOpMeter(SCOPE).create_counter(STATUS_CHANGES)
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_app_otlp", False):
            root.removeHandler(handler)


@contextmanager
def status_change_span(application_id: object) -> Iterator[Span]:
    """The child span around one status change (a no-op span when telemetry is off)."""
    with _tracer.start_as_current_span(
        "change_status", attributes={"app.application.id": str(application_id)}
    ) as span:
        yield span


def count_status_change(from_status: str, to_status: str) -> None:
    """One increment per committed status change (a no-op when telemetry is off)."""
    _status_changes.add(1, {"from": from_status, "to": to_status})

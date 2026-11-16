"""AC-29.6 to AC-29.9: the Compose profile, the Grafana provisioning, Render and the docs (#29).

These read the repository's files. That the stack really runs and links the signals is checked by
hand against `docker compose --profile observability up` (README, "Observability and alerting").
"""

import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
OBSERVABILITY = ROOT / "docker" / "observability"
STACK = {"otel-collector", "prometheus", "tempo", "loki", "grafana"}


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def compose_services() -> dict[str, Any]:
    services: dict[str, Any] = load(ROOT / "compose.yaml")["services"]
    return services


def test_ac29_6_observability_services_are_behind_the_profile_with_pinned_images() -> None:
    services = compose_services()
    assert set(services) >= STACK
    for name in STACK:
        assert services[name]["profiles"] == ["observability"], name
        image = services[name]["image"]
        assert re.fullmatch(r"[\w./-]+:v?\d+\.\d+\.\d+", image), f"{name}: {image} is not an exact version"


def test_ac29_6_the_app_exports_to_the_collector_only_when_it_runs() -> None:
    app = compose_services()["app"]
    script = "\n".join(app["command"])
    assert "getent hosts otel-collector" in script
    assert "http://otel-collector:4318" in script
    assert app["depends_on"]["otel-collector"]["required"] is False
    # Unset by default; `${VAR:-}` keeps an endpoint the user sets.
    assert app["environment"]["OTEL_EXPORTER_OTLP_ENDPOINT"] == "${OTEL_EXPORTER_OTLP_ENDPOINT:-}"


def test_ac29_6_grafana_provisions_three_linked_data_sources_and_a_dashboard() -> None:
    sources = {
        s["uid"]: s
        for s in load(OBSERVABILITY / "grafana/provisioning/datasources/datasources.yaml")["datasources"]
    }
    assert {uid: s["type"] for uid, s in sources.items()} == {
        "prometheus": "prometheus",
        "tempo": "tempo",
        "loki": "loki",
    }
    # metric → trace, trace → logs, log → trace
    assert sources["prometheus"]["jsonData"]["exemplarTraceIdDestinations"][0]["datasourceUid"] == "tempo"
    assert sources["tempo"]["jsonData"]["tracesToLogsV2"]["datasourceUid"] == "loki"
    assert "trace_id" in sources["tempo"]["jsonData"]["tracesToLogsV2"]["query"]
    assert sources["loki"]["jsonData"]["derivedFields"][0]["datasourceUid"] == "tempo"

    dashboard = json.loads((OBSERVABILITY / "grafana/dashboards/application-tracker.json").read_text())
    used = {p["datasource"]["uid"] for p in dashboard["panels"]}
    assert used == {"prometheus", "tempo", "loki"}
    exprs = " ".join(t.get("expr", "") for p in dashboard["panels"] for t in p["targets"])
    assert "app_status_changes_total" in exprs and "http_server_request_duration_seconds" in exprs


def test_ac29_6_collector_sends_each_signal_to_its_store() -> None:
    pipelines = load(OBSERVABILITY / "otel-collector.yaml")["service"]["pipelines"]
    assert "otlp/tempo" in pipelines["traces"]["exporters"]
    assert "otlphttp/prometheus" in pipelines["metrics"]["exporters"]
    assert "otlphttp/loki" in pipelines["logs"]["exporters"]


def test_ac29_7_default_compose_up_starts_only_db_and_app() -> None:
    default = {name for name, s in compose_services().items() if not s.get("profiles")}
    assert default == {"db", "app"}


def test_ac29_8_render_does_not_set_the_endpoint() -> None:
    assert "OTEL_" not in (ROOT / "render.yaml").read_text()


def test_ac29_9_readme_and_env_example_document_telemetry() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "Metrics, traces and an on-call agent are out of scope for this project." not in readme
    section = readme.split("## Observability and alerting", 1)[1].split("\n## ", 1)[0]
    assert "--profile observability" in section
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in section
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", section)
    assert images and all((ROOT / image).is_file() for image in images)
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in (ROOT / ".env.example").read_text()

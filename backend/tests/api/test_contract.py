"""AC-1.7, AC-1.8: openapi.yaml is valid, and the app exposes exactly its operations.

Operations in openapi.yaml that are not built yet are listed in PENDING. Each
issue that builds one removes it from the set; from #5 on PENDING is empty and
the app's operations must equal the file's.
"""

from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient
from openapi_spec_validator import validate

SPEC_PATH = Path(__file__).resolve().parents[3] / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}

Operation = tuple[str, str]  # (METHOD, path)

# The nine /api/v1 operations of the spec's API table.
SPEC_API_OPERATIONS: set[Operation] = {
    ("GET", "/api/v1/applications"),
    ("POST", "/api/v1/applications"),
    ("GET", "/api/v1/applications/{id}"),
    ("PATCH", "/api/v1/applications/{id}"),
    ("DELETE", "/api/v1/applications/{id}"),
    ("POST", "/api/v1/applications/{id}/status"),
    ("GET", "/api/v1/applications/{id}/events"),
    ("GET", "/api/v1/followups"),
    ("GET", "/api/v1/stats/funnel"),
}
OUTSIDE_PREFIX: set[Operation] = {("GET", "/health"), ("GET", "/ready")}

# In openapi.yaml but not built yet.
PENDING: set[Operation] = {
    ("GET", "/api/v1/stats/funnel"),
}


def load_spec() -> dict[str, Any]:
    spec: dict[str, Any] = yaml.safe_load(SPEC_PATH.read_text())
    return spec


def operations(spec: dict[str, Any]) -> dict[Operation, tuple[str, str]]:
    """(METHOD, path) -> (operationId, success status)."""
    result = {}
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method not in METHODS:
                continue
            success = next(code for code in op["responses"] if str(code).startswith("2"))
            result[(method.upper(), path)] = (op["operationId"], str(success))
    return result


def test_ac1_7_openapi_yaml_is_valid() -> None:
    validate(load_spec())


def test_ac1_7_openapi_yaml_has_every_operation_of_the_spec() -> None:
    spec = load_spec()
    assert set(operations(spec)) == SPEC_API_OPERATIONS | OUTSIDE_PREFIX
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method not in METHODS:
                continue
            assert "500" in op["responses"], (method, path)
            body = op.get("requestBody")
            if body is not None:
                ref = body["content"]["application/json"]["schema"]["$ref"]
                schema = spec["components"]["schemas"][ref.rsplit("/", 1)[-1]]
                assert schema["additionalProperties"] is False, (method, path)


def test_ac1_8_app_matches_openapi_yaml(client: TestClient) -> None:
    expected = operations(load_spec())
    actual = operations(client.app.openapi())  # type: ignore[attr-defined]

    still_pending = PENDING & set(actual)
    assert not still_pending, f"Implemented, so remove from PENDING: {sorted(still_pending)}"
    assert set(expected) >= PENDING, f"Not in openapi.yaml: {sorted(PENDING - set(expected))}"
    assert actual == {op: value for op, value in expected.items() if op not in PENDING}

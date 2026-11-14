"""AC-8.6: the built frontend is served at /, while the API keeps its JSON behaviour."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import API, assert_error
from sqlalchemy import Engine

from app.main import create_app

INDEX = '<!doctype html><html><body><div id="root"></div></body></html>'


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(INDEX)
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log('app')")
    (tmp_path.parent / "secret.txt").write_text("outside")
    return tmp_path


@pytest.fixture
def web(engine: Engine, dist: Path) -> TestClient:
    return TestClient(create_app(engine, migrate=False, frontend_dir=dist))


def test_ac8_6_index_at_root(web: TestClient) -> None:
    res = web.get("/")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert res.text == INDEX


def test_ac8_6_assets_are_served(web: TestClient) -> None:
    res = web.get("/assets/index-abc123.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"]


def test_ac8_6_other_pages_fall_back_to_index(web: TestClient) -> None:
    res = web.get("/applications/new")
    assert res.status_code == 200
    assert res.text == INDEX


def test_ac8_6_missing_asset_is_a_json_404(web: TestClient) -> None:
    assert_error(web.get("/assets/missing.js"), 404, "not_found")


@pytest.mark.parametrize("path", [f"{API}/unknown", f"{API}/applications/x/y/z", "/api", "/api/v2/x"])
def test_ac8_6_unknown_api_paths_stay_json_404(web: TestClient, path: str) -> None:
    assert_error(web.get(path), 404, "not_found")


def test_ac8_6_api_health_and_ready_still_answer_json(web: TestClient) -> None:
    assert web.get(f"{API}/applications").json() == []
    assert web.get("/health").json()["status"] == "ok"
    assert web.get("/ready").json() == {"status": "ok"}


def test_ac8_6_no_path_traversal(web: TestClient) -> None:
    res = web.get("/..%2Fsecret.txt")
    assert "outside" not in res.text


def test_ac8_6_catch_all_is_not_in_the_api_schema(web: TestClient) -> None:
    paths = web.get("/openapi.json").json()["paths"]
    assert "/{path}" not in paths


def test_ac8_6_static_dir_without_index_is_refused(engine: Engine, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="index.html"):
        create_app(engine, migrate=False, frontend_dir=tmp_path)

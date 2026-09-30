"""One server for the built UI and the API (`app.serve`)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.serve import create_site


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    """A stand-in for frontend/dist."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Goal Simulator</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log('app')")
    return tmp_path


@pytest.fixture
def site(dist: Path, empty_db_url: str):
    api = create_app(Settings(database_url=empty_db_url))
    with TestClient(create_site(api, dist)) as client:
        yield client


def test_the_ui_is_served_at_the_root(site: TestClient):
    assert "Goal Simulator" in site.get("/").text
    assert site.get("/assets/app.js").text == "console.log('app')"


@pytest.mark.parametrize("route", ["/compare", "/ask", "/plan"])
def test_ui_routes_get_the_app(site: TestClient, route: str):
    response = site.get(route)
    assert response.status_code == 200
    assert "Goal Simulator" in response.text


def test_the_api_is_under_api_and_its_startup_ran(site: TestClient):
    assert site.get("/api/health").json()["database"] == "ok"
    # The database didn't exist: the presets prove the API's startup (migrations) ran.
    assert len(site.get("/api/assumptions").json()) == 3
    assert "/simulate" in site.get("/api/openapi.json").json()["paths"]


def test_a_missing_build_is_explained(tmp_path: Path):
    with pytest.raises(RuntimeError, match="npm run build"):
        create_site(dist=tmp_path)

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_dashboard_page_and_assets_are_available(client: TestClient) -> None:
    page = client.get("/")
    styles = client.get("/static/styles.css")
    script = client.get("/static/app.js")

    assert page.status_code == 200
    assert "任务调度看板" in page.text
    assert "并发完成 x5" in page.text
    assert styles.status_code == 200
    assert script.status_code == 200


def test_seed_endpoint_returns_same_demo_task(client: TestClient) -> None:
    first = client.post("/api/demo/seed")
    second = client.post("/api/demo/seed")

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

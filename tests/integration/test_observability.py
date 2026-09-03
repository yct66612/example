import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_health_endpoint_exposes_instance_and_request_id(client: TestClient) -> None:
    response = client.get("/healthz", headers={"X-Request-ID": "defense-request-1"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "instance": "local"}
    assert response.headers["X-App-Instance"] == "local"
    assert response.headers["X-Request-ID"] == "defense-request-1"


def test_application_generates_request_id_when_header_is_missing(client: TestClient) -> None:
    response = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.headers["X-App-Instance"] == "local"
    assert response.headers["X-Request-ID"]

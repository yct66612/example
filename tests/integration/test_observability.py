import logging

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


def test_request_is_logged_with_instance_and_request_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    logger = logging.getLogger("uvicorn.error")
    previous_level = logger.level
    previous_disabled = logger.disabled
    logger.disabled = False
    logger.setLevel(logging.INFO)
    logger.addHandler(caplog.handler)
    try:
        response = client.get("/healthz", headers={"X-Request-ID": "logged-request"})
    finally:
        logger.removeHandler(caplog.handler)
        logger.setLevel(previous_level)
        logger.disabled = previous_disabled

    assert response.status_code == 200
    assert "instance=local request_id=logged-request" in caplog.text

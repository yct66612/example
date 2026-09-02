import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _task_payload(group_name: str = "sales") -> dict:
    return {
        "group_name": group_name,
        "group_overrides": {"channel": "email", "tone": ""},
        "name": "welcome-sequence",
        "base_parameters": {"tone": "formal", "retry": 1},
        "steps": [
            {"name": "prepare", "overrides": {"tone": "friendly"}},
            {"name": "send", "overrides": {"tone": "", "retry": 3}},
            {"name": "follow-up", "overrides": {"channel": "sms"}},
        ],
    }


def test_create_list_and_resolve_task(client: TestClient) -> None:
    response = client.post("/api/tasks", json=_task_payload())

    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "pending"
    assert [step["step_index"] for step in created["steps"]] == [0, 1, 2]

    listed = client.get("/api/tasks")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == created["id"]

    parameters = client.get(f"/api/tasks/{created['id']}/parameters")
    assert parameters.status_code == 200
    assert parameters.json()["snapshots"] == [
        {"tone": "friendly", "retry": 1, "channel": "email"},
        {"tone": "friendly", "retry": 3, "channel": "email"},
        {"tone": "friendly", "retry": 3, "channel": "sms"},
    ]


def test_empty_steps_are_rejected(client: TestClient) -> None:
    payload = _task_payload()
    payload["steps"] = []

    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 422


def test_duplicate_group_name_returns_conflict(client: TestClient) -> None:
    assert client.post("/api/tasks", json=_task_payload()).status_code == 201

    response = client.post("/api/tasks", json=_task_payload())

    assert response.status_code == 409

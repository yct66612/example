import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_dashboard_page_and_assets_are_available(client: TestClient) -> None:
    page = client.get("/")
    styles = client.get("/static/styles.css")
    script = client.get("/static/app.js")

    assert page.status_code == 200
    assert "任务调度看板" in page.text
    assert "并发完成 x5" in page.text
    assert styles.status_code == 200
    assert script.status_code == 200


def test_seed_endpoint_resets_completed_demo_task(client: TestClient) -> None:
    first = client.post("/api/demo/seed")
    assert first.status_code == 201
    first_task = first.json()

    claimed = client.post("/api/tasks/claim", json={"worker_id": "demo-worker"})
    assert claimed.status_code == 200
    assert claimed.json()["id"] == first_task["id"]

    started = client.post(
        f"/api/tasks/{first_task['id']}/start?worker_id=demo-worker"
    )
    assert started.status_code == 200

    for step_index in range(3):
        completed = client.post(
            f"/api/tasks/{first_task['id']}/steps/{step_index}/complete",
            json={"worker_id": "demo-worker", "success": True},
        )
        assert completed.status_code == 200

    second = client.post("/api/demo/seed")

    assert second.status_code == 201
    assert second.json()["id"] != first_task["id"]
    assert second.json()["status"] == "pending"
    assert second.json()["current_step_index"] == 0
    assert second.json()["log_count"] == 0

    demo_tasks = [
        task for task in client.get("/api/tasks").json() if task["name"] == "看板演示任务"
    ]
    assert len(demo_tasks) == 1


def test_seed_reset_does_not_delete_same_named_custom_task(client: TestClient) -> None:
    custom = client.post(
        "/api/tasks",
        json={
            "group_name": "用户自定义组",
            "group_overrides": {},
            "name": "看板演示任务",
            "base_parameters": {},
            "steps": [{"name": "自定义步骤", "overrides": {}}],
        },
    )
    assert custom.status_code == 201

    demo = client.post("/api/demo/seed")

    assert demo.status_code == 201
    tasks = client.get("/api/tasks").json()
    assert {(task["group_name"], task["name"]) for task in tasks} == {
        ("用户自定义组", "看板演示任务"),
        ("演示客户组", "看板演示任务"),
    }

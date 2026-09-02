import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_task_creation_dialog_markup_is_available(client: TestClient) -> None:
    page = client.get("/")

    assert page.status_code == 200
    assert "新建任务" in page.text
    assert "重置演示任务" in page.text
    assert 'id="task-dialog"' in page.text
    assert 'id="task-form"' in page.text
    assert 'id="open-task-dialog"' in page.text
    assert 'id="reset-demo-button"' in page.text
    assert 'id="base-parameters"' in page.text
    assert 'id="group-overrides"' in page.text
    assert 'id="steps-container"' in page.text
    assert 'id="add-step-button"' in page.text
    assert 'id="create-task-button"' in page.text


def test_task_creation_script_contains_validation_and_create_flow(client: TestClient) -> None:
    script = client.get("/static/app.js")

    assert script.status_code == 200
    assert "JSON.parse" in script.text
    assert "/api/tasks" in script.text
    assert "add-step-button" in script.text
    assert "task-dialog" in script.text
    assert "reset-demo-button" in script.text
    assert "请新建任务或重置演示任务" in script.text

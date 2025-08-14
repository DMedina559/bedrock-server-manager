from unittest.mock import patch
import pytest


@patch("bedrock_server_manager.web.routers.tasks.tasks.get_task", return_value=None)
def test_get_task_status_not_found(mock_get_task, authenticated_client):
    """Test getting the status of a task that does not exist."""
    response = authenticated_client.get("/api/tasks/status/invalid_task_id")
    assert response.status_code == 404
    assert "Task not found" in response.json()["detail"]


from bedrock_server_manager.web import tasks


def test_get_task_status_success(authenticated_client):
    """Test getting the status of a task successfully."""
    task_id = tasks.create_task()
    tasks.tasks[task_id] = {
        "status": "completed",
        "result": {"status": "success"},
    }
    response = authenticated_client.get(f"/api/tasks/status/{task_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["status"] == "success"

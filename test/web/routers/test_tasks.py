from unittest.mock import patch
import pytest


@patch("bedrock_server_manager.web.routers.tasks.tasks.get_task", return_value=None)
def test_get_task_status_not_found(mock_get_task, authenticated_client):
    """Test getting the status of a task that does not exist."""
    response = authenticated_client.get("/api/tasks/status/invalid_task_id")
    assert response.status_code == 404
    assert "Task not found" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.tasks.tasks.get_task")
def test_get_task_status_success(mock_get_task, authenticated_client):
    """Test getting the status of a task successfully."""
    mock_get_task.return_value = {
        "status": "completed",
        "result": {"status": "success"},
    }
    response = authenticated_client.get("/api/tasks/status/test_task_id")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["status"] == "success"

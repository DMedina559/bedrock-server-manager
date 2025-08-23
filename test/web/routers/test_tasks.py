from unittest.mock import MagicMock
import pytest


def test_get_task_status_not_found(authenticated_client):
    """Test getting the status of a task that does not exist."""
    # The app_context fixture provides a real context. We can access the
    # lazy-loaded task_manager and mock its methods for this test.
    authenticated_client.app.state.app_context.task_manager.get_task = MagicMock(
        return_value=None
    )

    response = authenticated_client.get("/api/tasks/status/invalid_task_id")

    assert response.status_code == 404
    assert "Task not found" in response.json()["detail"]
    authenticated_client.app.state.app_context.task_manager.get_task.assert_called_once_with(
        "invalid_task_id"
    )


def test_get_task_status_success(authenticated_client):
    """Test getting the status of a task successfully."""
    task_id = "some-real-task-id"
    task_data = {
        "status": "completed",
        "message": "Task is done",
        "result": {"status": "success"},
    }

    # Mock the get_task method on the task_manager instance within the app context
    authenticated_client.app.state.app_context.task_manager.get_task = MagicMock(
        return_value=task_data
    )

    response = authenticated_client.get(f"/api/tasks/status/{task_id}")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "completed"
    assert response_data["result"]["status"] == "success"
    authenticated_client.app.state.app_context.task_manager.get_task.assert_called_once_with(
        task_id
    )

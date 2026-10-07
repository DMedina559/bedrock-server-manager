"""
Integration tests for the tasks router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.api.models.tasks import TaskSnapshot


def test_get_task_status_unauthorized(unauth_client: TestClient):
    response = unauth_client.get("/api/tasks/status/123")
    assert response.status_code == 401


def test_get_task_status_success(auth_client: TestClient):
    with patch("bedrock_server_manager.web.tasks.TaskManager.get_task") as mock_get:
        mock_get.return_value = TaskSnapshot(
            id="123", status="running", message="Running"
        )

        response = auth_client.get("/api/tasks/status/123")
        assert response.status_code == 200
        assert response.json()["status"] == "running"
        assert response.json()["id"] == "123"


def test_get_task_status_not_found(auth_client: TestClient):
    with patch("bedrock_server_manager.web.tasks.TaskManager.get_task") as mock_get:
        mock_get.return_value = None

        response = auth_client.get("/api/tasks/status/123")
        assert response.status_code == 404
        assert "not found" in response.json()["error"]["message"].lower()


def test_list_tasks_unauthorized(unauth_client: TestClient):
    response = unauth_client.get("/api/tasks/list")
    assert response.status_code == 401


def test_list_tasks_success(auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.get_all_tasks"
    ) as mock_get:
        mock_get.return_value = {
            "task-1": TaskSnapshot(id="task-1", status="completed", message="Done"),
            "task-2": TaskSnapshot(id="task-2", status="queued", message="Queued"),
        }

        response = auth_client.get("/api/tasks/list")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "task-1"
        assert data[1]["id"] == "task-2"


def test_list_tasks_empty(auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.get_all_tasks"
    ) as mock_get:
        mock_get.return_value = {}

        response = auth_client.get("/api/tasks/list")
        assert response.status_code == 200
        assert response.json() == []

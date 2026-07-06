"""
Integration tests for the tasks router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_get_task_status_unauthorized(unauth_client: TestClient):
    response = unauth_client.get("/api/tasks/status/123")
    assert response.status_code == 401


def test_get_task_status_success(auth_client: TestClient):
    with patch("bedrock_server_manager.web.tasks.TaskManager.get_task") as mock_get:
        mock_get.return_value = {"status": "running", "progress": 50}

        response = auth_client.get("/api/tasks/status/123")
        assert response.status_code == 200
        assert response.json()["status"] == "running"
        assert response.json()["progress"] == 50


def test_get_task_status_not_found(auth_client: TestClient):
    with patch("bedrock_server_manager.web.tasks.TaskManager.get_task") as mock_get:
        mock_get.return_value = None

        response = auth_client.get("/api/tasks/status/123")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_list_tasks_unauthorized(unauth_client: TestClient):
    response = unauth_client.get("/api/tasks/list")
    assert response.status_code == 401


def test_list_tasks_success(auth_client: TestClient):
    with patch(
        "bedrock_server_manager.web.tasks.TaskManager.get_all_tasks"
    ) as mock_get:
        mock_get.return_value = {
            "task-1": {"status": "completed"},
            "task-2": {"status": "pending"},
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

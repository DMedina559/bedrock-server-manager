import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from bedrock_server_manager.web.main import app
from bedrock_server_manager.web.auth_utils import create_access_token
from datetime import timedelta
import os

# Test data
TEST_USER = "testuser"


@pytest.fixture
def client():
    """Create a test client for the app, with authentication and mocked dependencies."""
    os.environ["BEDROCK_SERVER_MANAGER_USERNAME"] = TEST_USER
    os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"] = "testpassword"
    os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"] = "test-secret-key"

    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {access_token}"

    yield client

    del os.environ["BEDROCK_SERVER_MANAGER_USERNAME"]
    del os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"]
    del os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"]
    app.dependency_overrides = {}


@patch("bedrock_server_manager.web.routers.tasks.tasks.get_task", return_value=None)
def test_get_task_status_not_found(mock_get_task, client):
    """Test getting the status of a task that does not exist."""
    response = client.get("/api/tasks/status/invalid_task_id")
    assert response.status_code == 404
    assert "Task not found" in response.json()["detail"]


@patch("bedrock_server_manager.web.routers.tasks.tasks.get_task")
def test_get_task_status_success(mock_get_task, client):
    """Test getting the status of a task successfully."""
    mock_get_task.return_value = {
        "status": "completed",
        "result": {"status": "success"},
    }
    response = client.get("/api/tasks/status/test_task_id")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["status"] == "success"

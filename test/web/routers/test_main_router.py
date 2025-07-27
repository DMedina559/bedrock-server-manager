from unittest.mock import patch
from fastapi.testclient import TestClient
from bedrock_server_manager.web.main import app
from bedrock_server_manager.web.dependencies import validate_server_exists
from bedrock_server_manager.web.auth_utils import get_current_user_optional


def test_index_authenticated(client):
    """Test the index route with an authenticated user."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Bedrock Server Manager" in response.text


def test_index_unauthenticated(client):
    """Test the index route with an unauthenticated user."""
    app.dependency_overrides[get_current_user_optional] = lambda: None
    client.headers.pop("Authorization")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"
    app.dependency_overrides = {}


def test_monitor_server_route(client):
    """Test the monitor_server_route with an authenticated user."""
    response = client.get("/server/test-server/monitor")
    assert response.status_code == 200
    assert "Server Monitor" in response.text


async def test_monitor_server_route_user_input_error(client):
    """Test the monitor_server_route with a UserInputError."""
    from fastapi import HTTPException

    async def mock_validation():
        raise HTTPException(status_code=404, detail="Server not found")

    app.dependency_overrides[validate_server_exists] = mock_validation
    response = client.get("/server/test-server/monitor")
    assert response.status_code == 404
    assert "Server not found" in response.json()["detail"]

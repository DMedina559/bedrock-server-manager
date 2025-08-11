from unittest.mock import patch
from fastapi.testclient import TestClient
from bedrock_server_manager.web.dependencies import validate_server_exists, needs_setup

import pytest


def test_index_authenticated(authenticated_client: TestClient):
    """Test the index route with an authenticated user."""
    response = authenticated_client.get("/")
    assert response.status_code == 200
    assert "Bedrock Server Manager" in response.text


@patch("bedrock_server_manager.app_context.needs_setup", return_value=False)
def test_index_unauthenticated(mock_needs_setup, client: TestClient):
    """Test the index route with an unauthenticated user."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"


def test_monitor_server_route(authenticated_client: TestClient):
    """Test the monitor_server_route with an authenticated user."""
    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        lambda: "test-server"
    )
    response = authenticated_client.get("/server/test-server/monitor")
    assert response.status_code == 200
    assert "Server Monitor" in response.text
    authenticated_client.app.dependency_overrides.clear()


def test_monitor_server_route_user_input_error(authenticated_client: TestClient):
    """Test the monitor_server_route with a UserInputError."""
    from fastapi import HTTPException

    async def mock_validation():
        raise HTTPException(status_code=404, detail="Server not found")

    # This override is specific to this test case
    original_override = authenticated_client.app.dependency_overrides.get(
        validate_server_exists
    )
    authenticated_client.app.dependency_overrides[validate_server_exists] = (
        mock_validation
    )

    response = authenticated_client.get("/server/test-server/monitor")

    # Restore original dependencies
    if original_override:
        authenticated_client.app.dependency_overrides[validate_server_exists] = (
            original_override
        )
    else:
        del authenticated_client.app.dependency_overrides[validate_server_exists]

    assert response.status_code == 404
    assert "Server not found" in response.json()["detail"]

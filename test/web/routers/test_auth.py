from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import pytest

# Test data
TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"

pytestmark = pytest.mark.skip(reason="WEB Test need refactoring")


@patch("bedrock_server_manager.web.routers.auth.authenticate_user")
def test_login_for_access_token_success(mock_authenticate_user, client: TestClient):
    """Test the login for access token route with valid credentials."""
    app_context = MagicMock()

    def settings_get_side_effect(key, default=None):
        if key == "web.jwt_cookie_samesite":
            return "lax"
        if key == "web.jwt_cookie_secure":
            return False
        return 4.0

    app_context.settings.get.side_effect = settings_get_side_effect
    client.app.state.app_context = app_context
    mock_authenticate_user.return_value = TEST_USER
    response = client.post(
        "/auth/token", data={"username": TEST_USER, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


@patch("bedrock_server_manager.web.routers.auth.authenticate_user")
def test_login_for_access_token_invalid_credentials(
    mock_authenticate_user, client: TestClient
):
    """Test the login for access token route with invalid credentials."""
    app_context = MagicMock()
    app_context.settings.get.return_value = 4.0
    client.app.state.app_context = app_context
    mock_authenticate_user.return_value = None
    response = client.post(
        "/auth/token", data={"username": TEST_USER, "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_for_access_token_empty_username(client: TestClient):
    """Test the login for access token route with an empty username."""
    app_context = MagicMock()
    app_context.settings.get.return_value = 4.0
    client.app.state.app_context = app_context
    response = client.post(
        "/auth/token", data={"username": "", "password": TEST_PASSWORD}
    )
    assert response.status_code == 401


def test_login_for_access_token_empty_password(client: TestClient):
    """Test the login for access token route with an empty password."""
    app_context = MagicMock()
    app_context.settings.get.return_value = 4.0
    client.app.state.app_context = app_context
    response = client.post("/auth/token", data={"username": TEST_USER, "password": ""})
    assert response.status_code == 401


def test_logout_success(authenticated_client: TestClient):
    """Test the logout route with a valid token."""
    response = authenticated_client.get("/auth/logout")
    assert response.status_code == 200
    assert len(response.history) > 0
    assert response.history[0].status_code == 302


def test_logout_no_token(client: TestClient):
    """Test the logout route without a token."""
    response = client.get("/auth/logout")
    assert response.status_code == 401

from unittest.mock import patch
from fastapi.testclient import TestClient
from bedrock_server_manager.web.main import app
from bedrock_server_manager.web.auth_utils import create_access_token
from datetime import timedelta

# Test data
TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"

client = TestClient(app)


@patch("bedrock_server_manager.web.routers.auth.authenticate_user")
def test_login_for_access_token_success(mock_authenticate_user):
    """Test the login for access token route with valid credentials."""
    mock_authenticate_user.return_value = TEST_USER
    response = client.post(
        "/auth/token", data={"username": TEST_USER, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


@patch("bedrock_server_manager.web.routers.auth.authenticate_user")
def test_login_for_access_token_invalid_credentials(mock_authenticate_user):
    """Test the login for access token route with invalid credentials."""
    mock_authenticate_user.return_value = None
    response = client.post(
        "/auth/token", data={"username": TEST_USER, "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_for_access_token_empty_username():
    """Test the login for access token route with an empty username."""
    response = client.post(
        "/auth/token", data={"username": "", "password": TEST_PASSWORD}
    )
    assert response.status_code == 401


def test_login_for_access_token_empty_password():
    """Test the login for access token route with an empty password."""
    response = client.post("/auth/token", data={"username": TEST_USER, "password": ""})
    assert response.status_code == 401


def test_logout_success():
    """Test the logout route with a valid token."""
    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    response = client.get(
        "/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert len(response.history) > 0
    assert response.history[0].status_code == 302


def test_logout_no_token():
    """Test the logout route without a token."""
    response = client.get("/auth/logout")
    assert response.status_code == 401

"""
Integration tests for the auth router endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.db.models import User as UserModel


def test_api_login_success(
    unauth_client: TestClient, test_user: UserModel, app_context: AppContext
):
    """Test successful login and token generation."""
    response = unauth_client.post(
        "/auth/token", data={"username": "testuser", "password": "testpassword"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "access_token_cookie" in response.cookies


def test_api_login_remember_me(
    unauth_client: TestClient, test_user: UserModel, app_context: AppContext
):
    """Test successful login with remember_me."""
    response = unauth_client.post(
        "/auth/token",
        data={
            "username": "testuser",
            "password": "testpassword",
            "remember_me": "true",
        },
    )

    assert response.status_code == 200
    assert "access_token_cookie" in response.cookies


def test_api_login_failure_wrong_password(
    unauth_client: TestClient, test_user: UserModel, app_context: AppContext
):
    """Test login with wrong password."""
    response = unauth_client.post(
        "/auth/token", data={"username": "testuser", "password": "wrongpassword"}
    )

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_api_login_failure_no_username(
    unauth_client: TestClient, test_user: UserModel, app_context: AppContext
):
    """Test login missing username."""
    # Since OAuth2PasswordRequestForm expects form data, skipping username might be caught by validation
    response = unauth_client.post("/auth/token", data={"password": "testpassword"})

    assert (
        response.status_code == 422
    )  # Unprocessable entity from Pydantic form validation


def test_logout_success(auth_client: TestClient):
    """Test logout successfully clears the cookie."""
    # The fixture sets a cookie initially
    assert "access_token_cookie" in auth_client.cookies

    # Allow redirects just in case, though the endpoint returns JSON
    response = auth_client.get("/auth/logout")

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Check that Set-Cookie header exists and tells the browser to expire the cookie
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "access_token_cookie=" in set_cookie_header
    assert "Max-Age=0" in set_cookie_header or "expires=" in set_cookie_header.lower()


def test_logout_unauthorized(unauth_client: TestClient):
    """Test logout without being logged in."""
    with patch(
        "bedrock_server_manager.config.bcm_config.needs_setup", return_value=False
    ):
        response = unauth_client.get("/auth/logout")
        assert response.status_code == 401


def test_reauth_success(auth_client: TestClient):
    """Test successful reauth for an existing authenticated user."""
    old_cookie = auth_client.cookies.get("access_token_cookie")

    response = auth_client.post("/auth/reauth")

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["message"] == "Successfully refreshed token."

    # We should have a new cookie
    new_cookie = response.cookies.get("access_token_cookie")
    assert new_cookie is not None
    assert old_cookie != new_cookie


def test_reauth_remember_me(auth_client: TestClient):
    """Test reauth properly accepts the remember_me flag."""
    # By sending remember_me as True, the cookie's expiration should be longer.
    # While we cannot easily assert the exact datetime delta on the client side,
    # we can ensure the endpoint successfully processes the flag without failing.
    response = auth_client.post("/auth/reauth", data={"remember_me": "true"})

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "access_token_cookie" in response.cookies


def test_reauth_unauthorized(unauth_client: TestClient):
    """Test reauth fails properly when a user is unauthenticated."""
    with patch(
        "bedrock_server_manager.config.bcm_config.needs_setup", return_value=False
    ):
        response = unauth_client.post("/auth/reauth")
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

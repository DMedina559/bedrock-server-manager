"""
Integration tests for the account router endpoints.
"""

from fastapi.testclient import TestClient

from bedrock_server_manager.db.models import User as UserModel


def test_get_account_api_unauthorized(unauth_client: TestClient):
    """Test getting account details without authentication."""
    response = unauth_client.get("/api/account")
    assert response.status_code == 401


def test_get_account_api_success(auth_client: TestClient, test_user: UserModel):
    """Test getting account details with valid authentication."""
    response = auth_client.get("/api/account")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user.username
    assert data["role"] == test_user.role


def test_post_update_theme_success(
    auth_client: TestClient, test_user: UserModel, db_session
):
    """Test updating user theme successfully."""
    response = auth_client.post(
        "/api/account/theme",
        json={"theme": "dark"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify DB update
    db_session.refresh(test_user)
    assert test_user.theme == "dark"


def test_post_update_profile_success(
    auth_client: TestClient, test_user: UserModel, db_session
):
    """Test updating user profile successfully."""
    response = auth_client.post(
        "/api/account/profile",
        json={"full_name": "Test User Full", "email": "test@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify DB update
    db_session.refresh(test_user)
    assert test_user.full_name == "Test User Full"
    assert test_user.email == "test@example.com"


def test_post_change_password_success(
    auth_client: TestClient, test_user: UserModel, db_session
):
    """Test changing user password successfully."""
    response = auth_client.post(
        "/api/account/change-password",
        json={"current_password": "testpassword", "new_password": "newpassword123"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify DB update (password should change, current verification logic requires re-hashing or testing endpoint again)
    from bedrock_server_manager.utils.auth import verify_password

    db_session.refresh(test_user)
    assert verify_password("newpassword123", test_user.hashed_password)


def test_post_change_password_incorrect_current(
    auth_client: TestClient, test_user: UserModel
):
    """Test changing password with incorrect current password."""
    response = auth_client.post(
        "/api/account/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpassword123"},
    )
    assert response.status_code == 400
    assert "Incorrect current password" in response.json()["detail"]


def test_post_change_password_validation_error(auth_client: TestClient):
    """Test changing password with missing fields."""
    response = auth_client.post(
        "/api/account/change-password",
        json={"current_password": "testpassword"},  # missing new_password
    )
    assert response.status_code == 422

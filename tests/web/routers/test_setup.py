"""
Integration tests for the setup router endpoints.
"""

from fastapi.testclient import TestClient


def test_get_setup_status_needs_setup(unauth_client: TestClient, app_context):
    """Test setup status when DB is empty."""
    # Ensure DB is empty
    with app_context.db.session_manager() as db:
        from bedrock_server_manager.db.models import User

        db.query(User).delete()
        db.commit()

    response = unauth_client.get("/api/setup/status")
    assert response.status_code == 200
    assert response.json()["needs_setup"] is True


def test_get_setup_status_no_setup_needed(unauth_client: TestClient, test_user):
    """Test setup status when DB has users."""
    response = unauth_client.get("/api/setup/status")
    assert response.status_code == 200
    assert response.json()["needs_setup"] is False


def test_create_first_user_success(unauth_client: TestClient, app_context):
    """Test creating the first user successfully."""
    # Ensure DB is empty
    with app_context.db.session_manager() as db:
        from bedrock_server_manager.db.models import User

        db.query(User).delete()
        db.commit()

    response = unauth_client.post(
        "/api/setup/create-first-user",
        json={"username": "admin", "password": "securepassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "access_token" in data
    assert "access_token_cookie" in response.cookies


def test_create_first_user_already_exists(unauth_client: TestClient, test_user):
    """Test creating a user when one already exists."""
    response = unauth_client.post(
        "/api/setup/create-first-user",
        json={"username": "admin2", "password": "securepassword"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["status"] == "error"
    assert "Setup already completed" in response.json()["detail"]["message"]

from fastapi.testclient import TestClient

# Test data
TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"


def test_login_for_access_token_success(client: TestClient, authenticated_user):
    """Test the login for access token route with valid credentials."""
    response = client.post(
        "/auth/token",
        json={"username": TEST_USER, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_for_access_token_invalid_credentials(
    client: TestClient, authenticated_user
):
    """Test the login for access token route with invalid credentials."""
    response = client.post(
        "/auth/token",
        json={"username": TEST_USER, "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_for_access_token_empty_username(client: TestClient):
    """Test the login for access token route with an empty username."""
    response = client.post(
        "/auth/token",
        json={"username": "", "password": TEST_PASSWORD},
    )
    assert response.status_code == 422


def test_login_for_access_token_empty_password(client: TestClient):
    """Test the login for access token route with an empty password."""
    response = client.post(
        "/auth/token",
        json={"username": TEST_USER, "password": ""},
    )
    assert response.status_code == 422


def test_logout_success(authenticated_client: TestClient):
    """Test the logout route with a valid token."""
    response = authenticated_client.get("/auth/logout")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

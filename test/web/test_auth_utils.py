import pytest
from unittest.mock import patch
from jose import jwt
from datetime import timedelta
import os
from bedrock_server_manager.web.auth_utils import (
    verify_password,
    pwd_context,
    create_access_token,
    get_current_user,
    get_current_user_optional,
    JWT_SECRET_KEY,
    ALGORITHM,
)
from fastapi import HTTPException, Request

# Test data
TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"


@pytest.fixture(autouse=True)
def setup_env_vars():
    """Set up environment variables for testing."""
    os.environ["BEDROCK_SERVER_MANAGER_USERNAME"] = TEST_USER
    os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"] = pwd_context.hash(TEST_PASSWORD)
    os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"] = "test-secret-key"
    yield
    del os.environ["BEDROCK_SERVER_MANAGER_USERNAME"]
    del os.environ["BEDROCK_SERVER_MANAGER_PASSWORD"]
    del os.environ["BEDROCK_SERVER_MANAGER_SECRET_KEY"]


def test_verify_password():
    """Test password verification."""
    hashed_password = pwd_context.hash(TEST_PASSWORD)
    assert verify_password(TEST_PASSWORD, hashed_password)
    assert not verify_password("wrongpassword", hashed_password)


def test_get_password_hash():
    """Test password hashing."""
    hashed_password = pwd_context.hash(TEST_PASSWORD)
    assert isinstance(hashed_password, str)
    assert hashed_password != TEST_PASSWORD


def test_create_access_token():
    """Test access token creation."""
    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    decoded_token = jwt.decode(access_token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded_token["sub"] == TEST_USER


from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

app = FastAPI()


@app.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/users/me/optional")
async def read_users_me_optional(
    current_user: dict = Depends(get_current_user_optional),
):
    return current_user


client = TestClient(app)


def test_get_current_user():
    """Test getting the current user from a valid token."""
    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    response = client.get(
        "/users/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == TEST_USER


def test_get_current_user_invalid_token():
    """Test getting the current user from an invalid token."""
    response = client.get(
        "/users/me", headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


def test_get_current_user_expired_token():
    """Test getting the current user from an expired token."""
    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=-15)
    )
    response = client.get(
        "/users/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


def test_get_current_user_no_username():
    """Test getting the current user from a token with no username."""
    access_token = create_access_token(
        data={"sub": None}, expires_delta=timedelta(minutes=15)
    )
    response = client.get(
        "/users/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


def test_get_current_user_optional():
    """Test getting an optional user from a valid token."""
    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    response = client.get(
        "/users/me/optional", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == TEST_USER


def test_get_current_user_optional_no_token():
    """Test getting an optional user with no token."""
    response = client.get("/users/me/optional")
    assert response.status_code == 200
    assert response.json() is None

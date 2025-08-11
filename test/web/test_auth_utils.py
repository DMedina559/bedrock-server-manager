import pytest
from jose import jwt
from datetime import timedelta
from bedrock_server_manager.web.auth_utils import (
    verify_password,
    pwd_context,
    create_access_token,
    get_current_user_optional,
    ALGORITHM,
)
from fastapi import Request
from bedrock_server_manager.db.models import User as UserModel

# Test data
TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"


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


def test_create_access_token(app_context):
    """Test access token creation."""
    from bedrock_server_manager.web.auth_utils import get_jwt_secret_key

    access_token = create_access_token(
        data={"sub": TEST_USER},
        expires_delta=timedelta(minutes=15),
        app_context=app_context,
    )
    decoded_token = jwt.decode(
        access_token, get_jwt_secret_key(), algorithms=[ALGORITHM]
    )
    assert decoded_token["sub"] == TEST_USER


from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_get_current_user(db_session):
    """Test getting the current user from a valid token."""
    user = UserModel(
        username=TEST_USER,
        hashed_password=pwd_context.hash(TEST_PASSWORD),
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    request = Request(
        {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {access_token}".encode())],
        }
    )
    request.state.db = db_session
    user = await get_current_user_optional(request)
    assert user.username == TEST_USER


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(client: TestClient):
    """Test getting the current user from an invalid token."""
    request = Request(
        {"type": "http", "headers": [(b"authorization", b"Bearer invalid_token")]}
    )
    user = await get_current_user_optional(request)
    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_expired_token(client: TestClient):
    """Test getting the current user from an expired token."""
    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=-15)
    )
    request = Request(
        {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {access_token}".encode())],
        }
    )
    user = await get_current_user_optional(request)
    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_no_username(client: TestClient):
    """Test getting the current user from a token with no username."""
    access_token = create_access_token(
        data={"sub": None}, expires_delta=timedelta(minutes=15)
    )
    request = Request(
        {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {access_token}".encode())],
        }
    )
    user = await get_current_user_optional(request)
    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_optional(db_session):
    """Test getting an optional user from a valid token."""
    user = UserModel(
        username=TEST_USER,
        hashed_password=pwd_context.hash(TEST_PASSWORD),
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    access_token = create_access_token(
        data={"sub": TEST_USER}, expires_delta=timedelta(minutes=15)
    )
    request = Request(
        {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {access_token}".encode())],
        }
    )
    request.state.db = db_session
    user = await get_current_user_optional(request)
    assert user.username == TEST_USER


@pytest.mark.asyncio
async def test_get_current_user_optional_no_token(client: TestClient):
    """Test getting an optional user with no token."""
    request = Request({"type": "http", "headers": []})
    user = await get_current_user_optional(request)
    assert user is None

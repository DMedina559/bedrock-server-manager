import pytest
from jose import jwt
from datetime import timedelta
from bedrock_server_manager.web.auth_utils import (
    verify_password,
    create_access_token,
    get_current_user_optional,
    get_current_user,
    get_password_hash,
    ALGORITHM,
)
from fastapi import Request, FastAPI, Depends
from fastapi.testclient import TestClient
from bedrock_server_manager.db.models import User as UserModel
from bedrock_server_manager.web.schemas import User
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.web.routers import auth_router, users_router

# Test data
TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"


@pytest.fixture
def unauthenticated_app(app_context):
    app = FastAPI()
    app.state.app_context = app_context
    app.include_router(auth_router, prefix="/auth")
    app.include_router(users_router, prefix="/users")

    @app.get("/users/me-optional")
    async def read_users_me_optional(
        current_user: User = Depends(get_current_user_optional),
    ):
        return current_user

    @app.get("/users/me", response_model=User)
    async def read_users_me(current_user: User = Depends(get_current_user)):
        return current_user

    return app


def test_verify_password():
    """Test password verification."""
    hashed_password = get_password_hash(TEST_PASSWORD)
    assert verify_password(TEST_PASSWORD, hashed_password)
    assert not verify_password("wrongpassword", hashed_password)


def test_create_access_token(app_context):
    """Test access token creation."""
    from bedrock_server_manager.web.auth_utils import get_jwt_secret_key

    access_token = create_access_token(
        app_context,
        data={"sub": TEST_USER},
        expires_delta=timedelta(minutes=15),
    )
    decoded_token = jwt.decode(
        access_token, get_jwt_secret_key(app_context.settings), algorithms=[ALGORITHM]
    )
    assert decoded_token["sub"] == TEST_USER


@pytest.mark.asyncio
async def test_get_current_user(db_session, app_context):
    """Test getting the current user from a valid token."""
    user = UserModel(
        username=TEST_USER,
        hashed_password=get_password_hash(TEST_PASSWORD),
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    access_token = create_access_token(
        app_context,
        data={"sub": TEST_USER},
        expires_delta=timedelta(minutes=15),
    )
    app = FastAPI()
    app.state.app_context = app_context
    request = Request(
        {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {access_token}".encode())],
            "app": app,
        }
    )
    request.state.db = db_session
    user = await get_current_user_optional(request)
    assert user.username == TEST_USER


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(unauthenticated_app):
    """Test getting the current user from an invalid token."""
    with TestClient(unauthenticated_app) as client:
        response = client.get(
            "/users/me", headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_expired_token(unauthenticated_app, app_context):
    """Test getting the current user from an expired token."""
    with TestClient(unauthenticated_app) as client:
        access_token = create_access_token(
            app_context,
            data={"sub": TEST_USER},
            expires_delta=timedelta(minutes=-15),
        )
        response = client.get(
            "/users/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_no_username(unauthenticated_app, app_context):
    """Test getting the current user from a token with no username."""
    with TestClient(unauthenticated_app) as client:
        access_token = create_access_token(
            app_context,
            data={"sub": None},
            expires_delta=timedelta(minutes=15),
        )
        response = client.get(
            "/users/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_optional_no_token(unauthenticated_app):
    """Test getting an optional user with no token."""
    with TestClient(unauthenticated_app) as client:
        response = client.get("/users/me-optional")
        assert response.status_code == 200
        assert response.json() is None

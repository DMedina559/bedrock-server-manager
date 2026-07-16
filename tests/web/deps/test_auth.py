import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from bedrock_server_manager.web.deps.auth import (
    get_admin_user,
    get_current_user,
    get_current_user_optional,
    get_moderator_user,
)
from bedrock_server_manager.web.schemas import UserResponse


@pytest.fixture
def auth_test_app(app_context):
    """Create a minimal FastAPI app to test auth dependencies directly."""
    app = FastAPI()
    app.state.app_context = app_context

    @app.get("/optional")
    async def optional_route(user: UserResponse = Depends(get_current_user_optional)):
        return {"user": user.model_dump() if user else None}

    @app.get("/required")
    async def required_route(user: UserResponse = Depends(get_current_user)):
        return {"user": user.model_dump()}

    @app.get("/admin")
    async def admin_route(user: UserResponse = Depends(get_admin_user)):
        return {"user": user.model_dump()}

    @app.get("/moderator")
    async def moderator_route(user: UserResponse = Depends(get_moderator_user)):
        return {"user": user.model_dump()}

    return app


@pytest.fixture
def unauth_client_test(auth_test_app):
    return TestClient(auth_test_app)


@pytest.fixture
def auth_client_test(auth_test_app, app_context, test_user):
    from bedrock_server_manager.utils.auth import create_access_token

    token = create_access_token(app_context, {"sub": test_user.username})
    client = TestClient(auth_test_app)
    client.cookies.set("access_token_cookie", token)
    return client


@pytest.fixture
def admin_client_test(auth_test_app, app_context, test_admin_user):
    from bedrock_server_manager.utils.auth import create_access_token

    token = create_access_token(app_context, {"sub": test_admin_user.username})
    client = TestClient(auth_test_app)
    client.cookies.set("access_token_cookie", token)
    return client


@pytest.fixture
def moderator_client_test(auth_test_app, app_context, db_session):
    from bedrock_server_manager.db.models import User as UserModel
    from bedrock_server_manager.utils.auth import create_access_token, get_password_hash

    user = UserModel(
        username="moduser",
        hashed_password=get_password_hash("modpassword"),
        role="moderator",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(app_context, {"sub": user.username})
    client = TestClient(auth_test_app)
    client.cookies.set("access_token_cookie", token)
    return client


def test_get_current_user_optional_no_token(unauth_client_test):
    """Test get_current_user_optional without any token returns None."""
    response = unauth_client_test.get("/optional")
    assert response.status_code == 200
    assert response.json() == {"user": None}


def test_get_current_user_optional_with_token(auth_client_test, test_user):
    """Test get_current_user_optional with a valid token returns the user."""
    response = auth_client_test.get("/optional")
    assert response.status_code == 200
    data = response.json()
    assert data["user"] is not None
    assert data["user"]["username"] == test_user.username


def test_get_current_user_no_token(unauth_client_test):
    """Test get_current_user without token raises 401."""
    response = unauth_client_test.get("/required")
    assert response.status_code == 401


def test_get_current_user_with_token(auth_client_test, test_user):
    """Test get_current_user with token returns user."""
    response = auth_client_test.get("/required")
    assert response.status_code == 200
    assert response.json()["user"]["username"] == test_user.username


def test_get_admin_user_as_admin(admin_client_test, test_admin_user):
    """Test get_admin_user with an admin user succeeds."""
    response = admin_client_test.get("/admin")
    assert response.status_code == 200
    assert response.json()["user"]["username"] == test_admin_user.username


def test_get_admin_user_as_normal_user(auth_client_test):
    """Test get_admin_user with a normal user raises 403."""
    response = auth_client_test.get("/admin")
    assert response.status_code == 403


def test_get_admin_user_as_moderator(moderator_client_test):
    """Test get_admin_user with a moderator user raises 403."""
    response = moderator_client_test.get("/admin")
    assert response.status_code == 403


def test_get_moderator_user_as_moderator(moderator_client_test):
    """Test get_moderator_user with a moderator user succeeds."""
    response = moderator_client_test.get("/moderator")
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "moduser"


def test_get_moderator_user_as_admin(admin_client_test, test_admin_user):
    """Test get_moderator_user with an admin user succeeds."""
    response = admin_client_test.get("/moderator")
    assert response.status_code == 200
    assert response.json()["user"]["username"] == test_admin_user.username


def test_get_moderator_user_as_normal_user(auth_client_test):
    """Test get_moderator_user with a normal user raises 403."""
    response = auth_client_test.get("/moderator")
    assert response.status_code == 403


def test_get_current_user_optional_bearer_token(auth_test_app, app_context, test_user):
    """Test get_current_user_optional with a bearer token."""
    from bedrock_server_manager.utils.auth import create_access_token

    token = create_access_token(app_context, {"sub": test_user.username})

    client = TestClient(auth_test_app)
    response = client.get("/optional", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["user"] is not None
    assert data["user"]["username"] == test_user.username

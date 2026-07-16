import datetime

import pytest
from fastapi import WebSocketException

from bedrock_server_manager.db.models import User
from bedrock_server_manager.utils.auth import (
    _get_user_from_token,
    authenticate_user,
    authenticate_websocket_token,
    create_access_token,
    get_jwt_secret_key,
    get_password_hash,
    verify_password,
)


def test_get_jwt_secret_key_creates_if_missing(app_context):
    """Test get_jwt_secret_key creates and sets a new key if one is missing in settings."""
    app_context.settings.set("web.jwt_secret_key", None)
    key = get_jwt_secret_key(app_context.settings)
    assert key is not None
    assert len(key) > 0
    assert app_context.settings.get("web.jwt_secret_key") == key


def test_get_jwt_secret_key_returns_existing(app_context):
    """Test get_jwt_secret_key returns the existing key from settings."""
    app_context.settings.set("web.jwt_secret_key", "my_secret_key")
    key = get_jwt_secret_key(app_context.settings)
    assert key == "my_secret_key"


def test_create_access_token(app_context):
    """Test create_access_token successfully generates a valid JWT string."""
    token = create_access_token(app_context, {"sub": "test_user"})
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_with_custom_expiry(app_context):
    """Test create_access_token handles custom expiration deltas correctly."""
    expires = datetime.timedelta(minutes=15)
    token = create_access_token(
        app_context, {"sub": "test_user"}, expires_delta=expires
    )
    assert isinstance(token, str)
    assert len(token) > 0


def test_get_user_from_token_success(app_context, db_session):
    """Test _get_user_from_token successfully retrieves an active user from the database."""
    user = User(
        username="test_token_user", hashed_password="pw", role="admin", is_active=True
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(app_context, {"sub": "test_token_user"})
    user_response = _get_user_from_token(app_context, token)

    assert user_response is not None
    assert user_response.username == "test_token_user"


def test_get_user_from_token_invalid_token(app_context):
    """Test _get_user_from_token gracefully handles and returns None for invalid token strings."""
    user_response = _get_user_from_token(app_context, "invalid_token_string")
    assert user_response is None


def test_get_user_from_token_user_not_found(app_context):
    """Test _get_user_from_token returns None when the token payload references a missing user."""
    token = create_access_token(app_context, {"sub": "non_existent_user"})
    user_response = _get_user_from_token(app_context, token)
    assert user_response is None


def test_authenticate_websocket_token_success(app_context, db_session):
    """Test authenticate_websocket_token correctly resolves a valid user object."""
    user = User(username="ws_user", hashed_password="pw", role="admin", is_active=True)
    db_session.add(user)
    db_session.commit()

    token = create_access_token(app_context, {"sub": "ws_user"})
    user_response = authenticate_websocket_token(app_context, token)

    assert user_response.username == "ws_user"


def test_authenticate_websocket_token_missing_token(app_context):
    """Test authenticate_websocket_token raises a WebSocketException on empty tokens."""
    with pytest.raises(WebSocketException) as exc_info:
        authenticate_websocket_token(app_context, "")
    assert exc_info.value.reason == "Missing token"


def test_authenticate_websocket_token_invalid_user(app_context):
    """Test authenticate_websocket_token raises a WebSocketException when a token user is missing."""
    token = create_access_token(app_context, {"sub": "missing_ws_user"})
    with pytest.raises(WebSocketException) as exc_info:
        authenticate_websocket_token(app_context, token)
    assert "Invalid token, user not found, or inactive" in exc_info.value.reason


def test_password_hashing():
    """Test password hashing encrypts effectively and verification checks appropriately."""
    password = "supersecretpassword"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_authenticate_user_success(app_context, db_session):
    """Test authenticate_user successfully logs in an active user."""
    password = "mypassword"
    hashed = get_password_hash(password)
    user = User(
        username="auth_user", hashed_password=hashed, role="admin", is_active=True
    )
    db_session.add(user)
    db_session.commit()

    result = authenticate_user(app_context, "auth_user", password)
    assert result == "auth_user"


def test_authenticate_user_wrong_password(app_context, db_session):
    """Test authenticate_user returns None upon incorrect password submission."""
    password = "mypassword"
    hashed = get_password_hash(password)
    user = User(
        username="auth_user_2", hashed_password=hashed, role="admin", is_active=True
    )
    db_session.add(user)
    db_session.commit()

    result = authenticate_user(app_context, "auth_user_2", "wrong_password")
    assert result is None


def test_authenticate_user_not_found(app_context):
    """Test authenticate_user returns None if the user does not exist in the database."""
    result = authenticate_user(app_context, "ghost_user", "password")
    assert result is None

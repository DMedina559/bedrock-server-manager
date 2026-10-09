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


async def test_get_jwt_secret_key_creates_if_missing(app_context):
    """Test get_jwt_secret_key creates and sets a new key if one is missing in settings."""
    await app_context.settings.set("web.jwt_secret_key", None)
    key = await get_jwt_secret_key(app_context.settings)
    assert key is not None
    assert len(key) > 0
    assert app_context.settings.get("web.jwt_secret_key") == key


async def test_get_jwt_secret_key_returns_existing(app_context):
    """Test get_jwt_secret_key returns the existing key from settings."""
    await app_context.settings.set("web.jwt_secret_key", "my_secret_key")
    key = await get_jwt_secret_key(app_context.settings)
    assert key == "my_secret_key"


async def test_get_jwt_secret_key_persists_across_reloads(app_context):
    """Test get_jwt_secret_key persists its generated key and retrieves it after reload."""
    await app_context.settings.set("web.jwt_secret_key", None)
    initial_key = await get_jwt_secret_key(app_context.settings)
    assert initial_key is not None

    # Reload storage state into AppState
    await app_context.storage.load_state(app_context.state)
    reloaded_key = await get_jwt_secret_key(app_context.settings)

    assert reloaded_key == initial_key


async def test_create_access_token(app_context):
    """Test create_access_token successfully generates a valid JWT string."""
    token = await create_access_token(app_context, {"sub": "test_user"})
    assert isinstance(token, str)
    assert len(token) > 0


async def test_create_access_token_with_custom_expiry(app_context):
    """Test create_access_token handles custom expiration deltas correctly."""
    expires = datetime.timedelta(minutes=15)
    token = await create_access_token(
        app_context, {"sub": "test_user"}, expires_delta=expires
    )
    assert isinstance(token, str)
    assert len(token) > 0


async def test_get_user_from_token_success(app_context, db):
    """Test _get_user_from_token successfully retrieves an active user from the database."""
    user = User(
        username="test_token_user", hashed_password="pw", role="admin", is_active=True
    )
    async with db.session_manager() as session:
        session.add(user)
        await session.commit()

    app_context._db = db

    token = await create_access_token(app_context, {"sub": "test_token_user"})
    user_response = await _get_user_from_token(app_context, token)

    assert user_response is not None
    assert user_response.username == "test_token_user"


async def test_get_user_from_token_invalid_token(app_context, db):
    """Test _get_user_from_token gracefully handles and returns None for invalid token strings."""
    app_context._db = db
    user_response = await _get_user_from_token(app_context, "invalid_token_string")
    assert user_response is None


async def test_get_user_from_token_user_not_found(app_context, db):
    """Test _get_user_from_token returns None when the token payload references a missing user."""
    app_context._db = db
    token = await create_access_token(app_context, {"sub": "non_existent_user"})
    user_response = await _get_user_from_token(app_context, token)
    assert user_response is None


async def test_authenticate_websocket_token_success(app_context, db):
    """Test authenticate_websocket_token correctly resolves a valid user object."""
    user = User(username="ws_user", hashed_password="pw", role="admin", is_active=True)
    async with db.session_manager() as session:
        session.add(user)
        await session.commit()

    app_context._db = db

    token = await create_access_token(app_context, {"sub": "ws_user"})
    user_response = await authenticate_websocket_token(app_context, token)

    assert user_response.username == "ws_user"


async def test_authenticate_websocket_token_missing_token(app_context):
    """Test authenticate_websocket_token raises a WebSocketException on empty tokens."""
    with pytest.raises(WebSocketException) as exc_info:
        await authenticate_websocket_token(app_context, "")
    assert exc_info.value.reason == "Missing token"


async def test_authenticate_websocket_token_invalid_user(app_context, db):
    """Test authenticate_websocket_token raises a WebSocketException when a token user is missing."""
    app_context._db = db
    token = await create_access_token(app_context, {"sub": "missing_ws_user"})
    with pytest.raises(WebSocketException) as exc_info:
        await authenticate_websocket_token(app_context, token)
    assert "Invalid token, user not found, or inactive" in exc_info.value.reason


async def test_password_hashing():
    """Test password hashing encrypts effectively and verification checks appropriately."""
    password = "supersecretpassword"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


async def test_authenticate_user_success(app_context, db):
    """Test authenticate_user successfully logs in an active user."""
    password = "mypassword"
    hashed = get_password_hash(password)
    user = User(
        username="auth_user", hashed_password=hashed, role="admin", is_active=True
    )
    async with db.session_manager() as session:
        session.add(user)
        await session.commit()

    app_context._db = db

    result = await authenticate_user(app_context, "auth_user", password)
    assert result == "auth_user"


async def test_authenticate_user_wrong_password(app_context, db):
    """Test authenticate_user returns None upon incorrect password submission."""
    password = "mypassword"
    hashed = get_password_hash(password)
    user = User(
        username="auth_user_2", hashed_password=hashed, role="admin", is_active=True
    )
    async with db.session_manager() as session:
        session.add(user)
        await session.commit()

    app_context._db = db

    result = await authenticate_user(app_context, "auth_user_2", "wrong_password")
    assert result is None


async def test_authenticate_user_not_found(app_context, db):
    """Test authenticate_user returns None if the user does not exist in the database."""
    app_context._db = db
    result = await authenticate_user(app_context, "ghost_user", "password")
    assert result is None


async def test_token_cache_fill_preserves_full_profile(app_context):
    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.create_user(
            session, "profile", "hash", "user"
        )
        user.full_name = "Full Name"
        user.email = "user@example.com"
    token = await create_access_token(data={"sub": "profile"}, app_context=app_context)
    assert await _get_user_from_token(app_context, token) is not None
    cached = app_context.state.users.get("profile")
    assert cached.full_name == "Full Name" and cached.email == "user@example.com"


async def test_token_cache_fill_cannot_overwrite_concurrent_disable(
    app_context, monkeypatch
):
    import asyncio

    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.create_user(
            session, "racing", "hash", "user"
        )
        await session.flush()
        user_id = user.id
    token = await create_access_token(data={"sub": "racing"}, app_context=app_context)
    entered = asyncio.Event()
    release = asyncio.Event()
    original = app_context.storage.user_repo.get_user_by_username
    first = True

    async def delayed(session, username):
        nonlocal first
        record = await original(session, username)
        if first and username == "racing":
            first = False
            entered.set()
            await release.wait()
        return record

    monkeypatch.setattr(app_context.storage.user_repo, "get_user_by_username", delayed)
    lookup = asyncio.create_task(_get_user_from_token(app_context, token))
    await entered.wait()
    disable = asyncio.create_task(
        app_context.user_service.update_account(action="disable", user_id=user_id)
    )
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(lookup, disable)
    assert not app_context.state.users.get("racing").is_active
    assert await _get_user_from_token(app_context, token) is None

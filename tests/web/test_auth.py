import asyncio
import datetime
from pathlib import Path

from bedrock_server_manager.db.models import User
from bedrock_server_manager.web.auth import (
    authenticate_user,
    create_access_token,
    get_jwt_secret_key,
    get_password_hash,
    resolve_session_token,
    verify_password,
)


async def test_jwt_secret_key_and_access_token_lifecycle(app_context):
    """Test JWT secret key creation, persistence across reloads, and token generation."""
    key = await get_jwt_secret_key(app_context.settings)
    assert key
    assert (Path(app_context.config_dir) / "credentials" / "jwt.key").is_file()
    assert app_context.settings.get("web.jwt_secret_key") is None
    assert await get_jwt_secret_key(app_context.settings) == key

    await app_context.storage.load_state(app_context.state)
    app_context.settings._jwt_signing_credential = None
    assert await get_jwt_secret_key(app_context.settings) == key

    token = await create_access_token(app_context, {"sub": "test_user"})
    assert isinstance(token, str) and len(token) > 0

    custom_token = await create_access_token(
        app_context,
        {"sub": "test_user"},
        expires_delta=datetime.timedelta(minutes=15),
    )
    assert isinstance(custom_token, str) and len(custom_token) > 0


async def test_password_hashing_authentication_and_session_resolution(
    app_context, db, password_hashes
):
    """Test password hashing, authenticate_user, and resolve_session_token scenarios."""
    password = "supersecretpassword"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

    app_context._db = db
    async with db.session_manager() as session:
        session.add(
            User(
                username="auth_user",
                hashed_password=password_hashes["user"],
                role="admin",
                is_active=True,
            )
        )
        await session.commit()

    # authenticate_user success, wrong password, missing user
    assert (
        await authenticate_user(app_context, "auth_user", "testpassword") == "auth_user"
    )
    assert await authenticate_user(app_context, "auth_user", "wrong_password") is None
    assert await authenticate_user(app_context, "ghost_user", "password") is None

    # resolve_session_token success, invalid token, missing user
    token = await create_access_token(app_context, {"sub": "auth_user"})
    session_info = await resolve_session_token(app_context, token)
    assert session_info is not None
    assert session_info.user.username == "auth_user"
    assert session_info.authorization.username == "auth_user"

    assert await resolve_session_token(app_context, "invalid_token_string") is None
    missing_token = await create_access_token(app_context, {"sub": "non_existent_user"})
    assert await resolve_session_token(app_context, missing_token) is None

    # Token resolution does not publish a partial cached profile
    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.create_user(
            session, "profile", "hash", "user"
        )
        user.full_name = "Full Name"
        user.email = "user@example.com"
    profile_token = await create_access_token(
        data={"sub": "profile"}, app_context=app_context
    )
    assert await resolve_session_token(app_context, profile_token) is not None
    assert app_context.state.users.get("profile") is None
    async with app_context.storage.transaction() as session:
        profile = await app_context.storage.user_repo.get_user_by_username(
            session, "profile"
        )
        assert profile.full_name == "Full Name" and profile.email == "user@example.com"


async def test_token_cache_fill_cannot_overwrite_concurrent_disable(
    app_context, monkeypatch
):
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
    lookup = asyncio.create_task(resolve_session_token(app_context, token))
    await entered.wait()
    disable = asyncio.create_task(
        app_context.user_service.update_account(action="disable", user_id=user_id)
    )
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(lookup, disable)
    assert not app_context.state.users.get("racing").is_active
    assert await resolve_session_token(app_context, token) is None

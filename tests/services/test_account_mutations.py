"""Account writes stay coherent with cached state and audit transactions."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from bedrock_server_manager.error import StorageError, UserInputError
from bedrock_server_manager.state.updates import AccountPatch


async def create_user(app_context, name="alice", role="user"):
    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.create_user(
            session, name, "hash", role
        )
        await session.flush()
        user_id = user.id
    await app_context.storage.load_state(app_context.state)
    return user_id


async def test_disable_survives_flush_of_pending_theme(app_context):
    user_id = await create_user(app_context)
    cached = app_context.state.users.get("alice")
    cached.theme = "dark"
    app_context.state.users.set(cached)
    await app_context.user_service.update_account(action="disable", user_id=user_id)
    assert not app_context.state.users.get("alice").is_active
    await app_context.storage.flush(app_context.state)
    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.get_user_by_id(session, user_id)
        assert not user.is_active
        assert user.theme == "dark"


async def test_deleted_dirty_user_is_not_resurrected(app_context):
    user_id = await create_user(app_context)
    app_context.state.users.set(app_context.state.users.get("alice"))
    await app_context.user_service.update_account(action="delete", user_id=user_id)
    await app_context.storage.flush(app_context.state)
    assert app_context.state.users.get("alice") is None
    async with app_context.storage.transaction() as session:
        assert (
            await app_context.storage.user_repo.get_user_by_id(session, user_id) is None
        )


async def test_failed_audit_rolls_back_account_and_keeps_cache(
    app_context, monkeypatch
):
    user_id = await create_user(app_context)
    monkeypatch.setattr(
        app_context.storage.audit_log_repo,
        "create_audit_log",
        AsyncMock(side_effect=RuntimeError("failed")),
    )
    with pytest.raises(StorageError):
        await app_context.user_service.update_account(
            action="disable", user_id=user_id, actor_id=user_id
        )
    assert app_context.state.users.get("alice").is_active
    async with app_context.storage.transaction() as session:
        assert (
            await app_context.storage.user_repo.get_user_by_id(session, user_id)
        ).is_active


async def test_concurrent_admin_demotion_preserves_one_admin(app_context):
    first = await create_user(app_context, "first", "admin")
    second = await create_user(app_context, "second", "admin")
    results = await asyncio.gather(
        *[
            app_context.user_service.update_account(
                action="role", user_id=user_id, values=AccountPatch(role="user")
            )
            for user_id in (first, second)
        ],
        return_exceptions=True,
    )
    assert sum(isinstance(result, UserInputError) for result in results) == 1
    async with app_context.storage.transaction() as session:
        assert await app_context.storage.user_repo.count_active_admins(session) == 1


@pytest.mark.parametrize(
    "details", [{1: "bad"}, {"value": float("nan")}, {"value": object()}]
)
async def test_audit_details_validate_before_session_mutation(app_context, details):
    from pydantic import ValidationError

    async with app_context.db.session_manager() as session:
        with pytest.raises(ValidationError):
            await app_context.storage.audit_log_repo.create_audit_log(
                session, 1, "update", details
            )
        assert not session.new


async def test_registration_consumes_token_and_publishes_clean_account(app_context):
    import time

    async with app_context.storage.transaction() as session:
        await app_context.storage.user_repo.create_registration_token(
            session, "token", "user", int(time.time()) + 3600
        )
    record = await app_context.user_service.create_account(
        "registered", "hash", token="token"
    )
    assert record.id is not None
    assert app_context.state.users.get("registered") == record
    assert "registered" not in app_context.state.users.dirty_users
    async with app_context.storage.transaction() as session:
        assert (
            await app_context.storage.user_repo.get_registration_token(session, "token")
            is None
        )


async def test_failed_creation_does_not_publish_state_or_consume_token(
    app_context, monkeypatch
):
    import time

    async with app_context.storage.transaction() as session:
        await app_context.storage.user_repo.create_registration_token(
            session, "token", "user", int(time.time()) + 3600
        )
    monkeypatch.setattr(
        app_context.storage.user_repo,
        "create_user",
        AsyncMock(side_effect=RuntimeError("failed")),
    )
    with pytest.raises(StorageError):
        await app_context.user_service.create_account(
            "registered", "hash", token="token"
        )
    assert app_context.state.users.get("registered") is None
    async with app_context.storage.transaction() as session:
        assert (
            await app_context.storage.user_repo.get_registration_token(session, "token")
            is not None
        )


async def test_revocation_failure_preserves_committed_account_result(
    app_context, monkeypatch
):
    from bedrock_server_manager.error import IncompleteOperationError

    user_id = await create_user(app_context)

    async def fail_revoke(name):
        assert not app_context.storage.write_lock.locked()
        raise RuntimeError("revocation failed")

    monkeypatch.setattr(app_context.user_service, "revoke_connections", fail_revoke)
    with pytest.raises(IncompleteOperationError) as failure:
        await app_context.user_service.update_account(action="disable", user_id=user_id)
    assert failure.value.result.committed
    assert failure.value.result.resource == "alice"
    assert not app_context.state.users.get("alice").is_active
    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.get_user_by_id(session, user_id)
        assert not user.is_active


async def test_change_password_off_transaction_and_concurrency(
    app_context, monkeypatch
):
    from sqlalchemy import update

    import bedrock_server_manager.web.auth as web_auth
    from bedrock_server_manager.db.models import User
    from bedrock_server_manager.web.auth import get_password_hash

    plain_old = "correct horse battery staple 1"
    plain_new = "correct horse battery staple 2"
    initial_hash = get_password_hash(plain_old)

    async with app_context.storage.transaction() as session:
        user = await app_context.storage.user_repo.create_user(
            session, "concurrency_user", initial_hash, "user"
        )
        await session.flush()
        user_id = user.id

    original_hash_async = web_auth.get_password_hash_async
    hashing_called_outside_tx = False

    async def monitored_hash(pwd):
        nonlocal hashing_called_outside_tx
        assert not app_context.storage.write_lock.locked()
        hashing_called_outside_tx = True
        return await original_hash_async(pwd)

    monkeypatch.setattr(web_auth, "get_password_hash_async", monitored_hash)

    success = await app_context.user_service.change_password(
        "concurrency_user", plain_old, plain_new
    )
    assert success is True
    assert hashing_called_outside_tx is True

    # Concurrent collision test: if auth_revision changed during hashing, update fails safely
    async def conflicting_hash(pwd):
        async with app_context.storage.transaction() as session:
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(auth_revision=User.auth_revision + 1)
            )
        return await original_hash_async(pwd)

    monkeypatch.setattr(web_auth, "get_password_hash_async", conflicting_hash)

    with pytest.raises(UserInputError, match="Account credentials changed; try again"):
        await app_context.user_service.change_password(
            "concurrency_user", plain_new, "correct horse battery staple 3"
        )

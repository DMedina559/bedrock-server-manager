"""Account writes stay coherent with cached state and audit transactions."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from bedrock_server_manager.error import StorageError, UserInputError


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
                action="role", user_id=user_id, values={"role": "user"}
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

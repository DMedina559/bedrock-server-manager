"""Password work is outside transactions; competing commits cannot overwrite proofs."""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar

import pytest
from sqlalchemy import select

from bedrock_server_manager.db.models import AuthSecurityEvent, User
from bedrock_server_manager.error import UserInputError


@pytest.mark.parametrize(
    "modes", [("change", "change"), ("reset", "reset"), ("change", "reset")]
)
async def test_competing_password_updates_have_one_atomic_winner(
    auth_client, app_context, monkeypatch, modes
):
    import bedrock_server_manager.web.auth as auth

    active = ContextVar("password_test_transaction", default=0)
    original_transaction = app_context.storage.transaction
    original_hash = auth.get_password_hash_async
    original_verify = auth.verify_password_async
    barrier = asyncio.Barrier(2)
    async with original_transaction() as session:
        owner = await session.scalar(select(User).where(User.username == "testuser"))
        revision, owner_id = owner.auth_revision, owner.access_id

    @asynccontextmanager
    async def transaction():
        async with original_transaction() as session:
            token = active.set(active.get() + 1)
            try:
                yield session
            finally:
                active.reset(token)

    async def hash_password(password):
        assert active.get() == 0
        result = await original_hash(password)
        await barrier.wait()
        return result

    async def verify_password(*args):
        assert active.get() == 0
        return await original_verify(*args)

    monkeypatch.setattr(app_context.storage, "transaction", transaction)
    monkeypatch.setattr(auth, "get_password_hash_async", hash_password)
    monkeypatch.setattr(auth, "verify_password_async", verify_password)
    passwords = ["first replacement passphrase", "second replacement passphrase"]

    async def change(mode, password):
        if mode == "change":
            return await app_context.user_service.change_password(
                "testuser", "testpassword", password
            )
        return await app_context.user_service.reset_password("testuser", password)

    async with asyncio.timeout(10):
        results = await asyncio.gather(
            *(change(mode, password) for mode, password in zip(modes, passwords)),
            return_exceptions=True,
        )
    assert sum(result is True for result in results) == 1, results
    assert sum(isinstance(result, UserInputError) for result in results) == 1, results
    async with original_transaction() as session:
        owner = await session.scalar(select(User).where(User.username == "testuser"))
        assert owner.auth_revision == revision + 1
        stored_hash = owner.hashed_password
        events = list(
            await session.scalars(
                select(AuthSecurityEvent).where(
                    AuthSecurityEvent.owner_id == owner_id,
                    AuthSecurityEvent.action.in_(
                        ["password_changed", "password_reset"]
                    ),
                )
            )
        )
        assert len(events) == 1
    winner = results.index(True)
    assert await original_verify(passwords[winner], stored_hash)
    assert not await original_verify(passwords[1 - winner], stored_hash)
    assert (await auth_client.get("/api/account")).status_code == 401


@pytest.mark.parametrize("mode", ["change", "reset"])
@pytest.mark.parametrize("mutation", ["disable", "delete"])
async def test_account_mutations_during_hashing_invalidate_password_commit(
    auth_client, app_context, monkeypatch, mode, mutation
):
    import bedrock_server_manager.web.auth as auth

    entered, release = asyncio.Event(), asyncio.Event()
    original = auth.get_password_hash_async

    async def hash_password(password):
        value = await original(password)
        entered.set()
        await release.wait()
        return value

    monkeypatch.setattr(auth, "get_password_hash_async", hash_password)
    service = app_context.user_service
    pending = asyncio.create_task(
        service.change_password(
            "testuser", "testpassword", "new replacement passphrase"
        )
        if mode == "change"
        else service.reset_password("testuser", "new replacement passphrase")
    )
    try:
        async with asyncio.timeout(10):
            await entered.wait()
            await service.update_account(action=mutation, username="testuser")
            release.set()
            with pytest.raises(UserInputError, match="credentials changed"):
                await pending
    finally:
        release.set()
        if not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)

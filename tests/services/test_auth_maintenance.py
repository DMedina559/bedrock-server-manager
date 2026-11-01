"""Retention scheduling, canonical peer budgets and pure lifetime policy."""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from bedrock_server_manager.db.models import (
    AuthSecurityEvent,
    AuthThrottle,
    LoginSession,
)
from bedrock_server_manager.web.auth import token_lifetime


@pytest.mark.parametrize(
    "configured", [None, "invalid", float("nan"), float("inf"), -1, 0]
)
def test_invalid_lifetime_falls_back(configured):
    settings = {"web.token_expires_weeks": configured}
    assert token_lifetime(settings).total_seconds() == 28 * 86400
    assert token_lifetime(settings, remember_me=False).total_seconds() == 86400


def test_remembered_lifetime_uses_configuration():
    assert token_lifetime({"web.token_expires_weeks": 2}).total_seconds() == 14 * 86400


async def test_retention_batches_without_authentication(app_context, monkeypatch):
    now = int(time.time())
    service = app_context.session_service
    async with app_context.storage.transaction() as session:
        session.add_all(
            [
                AuthSecurityEvent(
                    id=f"{i:032x}",
                    owner_id="owner",
                    action="login",
                    timestamp=now - 91 * 86400,
                    details={},
                )
                for i in range(501)
            ]
        )
        session.add(
            AuthSecurityEvent(
                id="recent", owner_id="owner", action="login", timestamp=now, details={}
            )
        )
        session.add(AuthThrottle(key="old", window=now - 90000, attempts=1))
        session.add(AuthThrottle(key="active", window=now, attempts=1))
        for identifier, expiry in (
            ("old", now - 91 * 86400),
            ("recent", now - 86400),
            ("active", now + 86400),
        ):
            session.add(
                LoginSession(
                    id=identifier,
                    owner_id="owner",
                    name="test",
                    user_agent="",
                    ip_address="",
                    created_at=now - 100 * 86400,
                    last_seen_at=now,
                    expires_at=expiry,
                    verified_at=now,
                )
            )
    completed = asyncio.Event()
    original = service.cleanup

    async def cleanup():
        await original()
        completed.set()

    monkeypatch.setattr(service, "cleanup", cleanup)
    await service.start()
    await service.start()  # Idempotent ownership.
    task = service._maintenance_task
    async with asyncio.timeout(5):
        await completed.wait()
    await service.shutdown()
    assert task.done() and service._maintenance_task is None
    async with app_context.storage.transaction() as session:
        assert list(await session.scalars(select(AuthSecurityEvent.id))) == ["recent"]
        assert list(await session.scalars(select(AuthThrottle.key))) == ["active"]
        assert set(await session.scalars(select(LoginSession.id))) == {
            "recent",
            "active",
        }


async def test_retention_retries_and_cancellation_drains(
    app_context, monkeypatch, caplog
):
    service = app_context.session_service
    attempted = asyncio.Event()
    retry_wait = asyncio.Event()
    drained = asyncio.Event()
    calls = 0

    async def cleanup():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("storage temporarily unavailable")
        attempted.set()
        try:
            await asyncio.Event().wait()
        finally:
            drained.set()

    async def sleep(delay):
        assert delay == 300
        retry_wait.set()

    # Replace the module's asyncio reference, not the process-wide sleep function.
    from types import SimpleNamespace

    import bedrock_server_manager.services.session_service as module

    monkeypatch.setattr(
        module,
        "asyncio",
        SimpleNamespace(
            create_task=asyncio.create_task,
            CancelledError=asyncio.CancelledError,
            sleep=sleep,
        ),
    )
    monkeypatch.setattr(service, "cleanup", cleanup)
    await service.start()
    async with asyncio.timeout(5):
        await attempted.wait()
    await service.shutdown()
    assert retry_wait.is_set() and drained.is_set()
    assert "retrying in five minutes" in caplog.text


async def test_retention_stops_before_database_close(app_context, monkeypatch):
    service = app_context.session_service
    entered = asyncio.Event()
    drained = asyncio.Event()

    async def cleanup():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            drained.set()

    close = app_context._db.shutdown

    async def close_database():
        assert drained.is_set()
        await close()

    monkeypatch.setattr(service, "cleanup", cleanup)
    monkeypatch.setattr(app_context._db, "shutdown", close_database)
    await service.start()
    await entered.wait()
    await app_context.shutdown()


async def test_login_does_not_run_retention(app_context, monkeypatch):
    cleanup = AsyncMock(side_effect=AssertionError("retention on login path"))
    monkeypatch.setattr(app_context.session_service, "cleanup", cleanup)
    await app_context.session_service.throttle("account", "192.0.2.1")
    cleanup.assert_not_awaited()


async def test_peer_normalization_and_optional_prefix(app_context):
    service = app_context.session_service
    assert service.peer_key("::ffff:192.0.2.1") == service.peer_key("192.0.2.1")
    assert service.peer_key("2001:0db8:0:0::1") == service.peer_key("2001:db8::1")
    assert service.peer_key("2001:db8::1") != service.peer_key("2001:db8::2")
    await app_context.settings.set("security.auth_ipv6_prefix", 64)
    assert service.peer_key("2001:db8::1") == service.peer_key("2001:db8::2")
    assert service.peer_key("2001:db8:0:1::1") != service.peer_key("2001:db8::1")
    assert service.peer_key("testclient") == "testclient"


async def test_equivalent_peer_forms_share_one_budget(app_context, monkeypatch):
    from fastapi import HTTPException

    import bedrock_server_manager.services.session_service as module

    monkeypatch.setattr(module.time, "time", lambda: 2000000000)
    await app_context.settings.set("security.auth_peer_attempts", 10)
    for attempt in range(10):
        await app_context.session_service.throttle(
            peer="::ffff:192.0.2.1" if attempt % 2 else "192.0.2.1"
        )
    with pytest.raises(HTTPException) as denied:
        await app_context.session_service.throttle(peer="192.0.2.1")
    assert denied.value.status_code == 429
    await app_context.session_service.throttle(peer="192.0.2.2")

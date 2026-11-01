"""Regression coverage for the remaining auth audit boundaries."""

import asyncio
import hashlib
import json
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from importlib.resources import files
from uuid import uuid4

import pyotp
import pytest
from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select, update

from bedrock_server_manager.contracts import NewPassword
from bedrock_server_manager.db.models import (
    AccountSecurity,
    AuthSecurityEvent,
    IntegrationToken,
    LoginSession,
    TrustedDevice,
    User,
)


async def owner_id(context):
    async with context.storage.transaction() as session:
        return await session.scalar(
            select(User.access_id).where(User.username == "testuser")
        )


async def enroll(context, *, confirm=True):
    owner = await owner_id(context)
    enrollment = await context.session_service.enrollment(owner, "testuser")
    otp = pyotp.TOTP(enrollment["secret"])
    result = (
        await context.session_service.confirm_enrollment(owner, otp.now())
        if confirm
        else None
    )
    return owner, otp, result


def test_packaged_password_list_has_provenance_and_preserves_eight_character_policy():
    directory = files("bedrock_server_manager").joinpath("data")
    data = directory.joinpath("common-passwords.txt").read_bytes()
    metadata = json.loads(
        directory.joinpath("common-passwords-source.json").read_text()
    )
    assert hashlib.sha256(data).hexdigest() == metadata["sha256"]
    assert len(data.splitlines()) == metadata["entries"] >= 1000
    assert "MIT License" in directory.joinpath("common-passwords.LICENSE").read_text()
    assert (
        TypeAdapter(NewPassword).validate_python("Otter42!").get_secret_value()
        == "Otter42!"
    )
    for password in ["short42", "PaSsWoRd", "12345678", "iloveyou"]:
        with pytest.raises(ValidationError):
            TypeAdapter(NewPassword).validate_python(password)


async def test_active_credential_filter_keeps_old_active_token_visible(
    auth_client, app_context
):
    response = await auth_client.post(
        "/api/account/tokens",
        json={
            "name": "Old active",
            "permissions": ["account:read"],
            "expires_in_days": None,
        },
    )
    assert response.status_code == 201
    active = response.json()["credential"]["id"]
    now = int(time.time())
    async with app_context.storage.transaction() as session:
        owner = await owner_id(app_context)
        await session.execute(
            update(IntegrationToken)
            .where(IntegrationToken.id == active)
            .values(created_at=1)
        )
        for i in range(100):
            session.add(
                IntegrationToken(
                    id=uuid4().hex,
                    owner_id=owner,
                    name=f"Revoked {i}",
                    digest=uuid4().hex * 2,
                    permissions=["account:read"],
                    server_ids=None,
                    created_at=now + i,
                    expires_at=None,
                    revoked_at=now,
                )
            )
    current = await auth_client.get("/api/account/tokens?status=active&limit=51")
    assert [row["id"] for row in current.json()] == [active]
    history = await auth_client.get("/api/account/tokens?status=inactive&limit=51")
    assert len(history.json()) == 51 and all(
        row["revoked_at"] for row in history.json()
    )
    assert (
        await auth_client.get("/api/account/tokens?status=invalid")
    ).status_code == 422


@pytest.mark.parametrize("factor", ["totp", "recovery"])
async def test_concurrent_factor_consumption_has_one_winner(
    app_context, auth_client, factor
):
    owner, otp, confirmation = await enroll(app_context)
    code = (
        confirmation["recovery_codes"][0]
        if factor == "recovery"
        else otp.at((int(time.time()) // 30 + 1) * 30)
    )
    result = await asyncio.gather(
        *(app_context.session_service.verify_factor(owner, code) for _ in range(2))
    )
    assert sorted(result) == [False, True]
    if factor == "recovery":
        async with app_context.storage.transaction() as session:
            events = list(
                await session.scalars(
                    select(AuthSecurityEvent).where(
                        AuthSecurityEvent.owner_id == owner,
                        AuthSecurityEvent.action == "recovery_code_used",
                    )
                )
            )
            assert len(events) == 1


@pytest.mark.parametrize("change", ["revision", "disable", "factor"])
async def test_mfa_worker_runs_outside_transaction_and_rejects_changed_snapshot(
    app_context, auth_client, monkeypatch, change
):
    owner, otp, _ = await enroll(app_context)
    service = app_context.session_service
    opened = ContextVar("mfa_transaction", default=False)
    transaction = app_context.storage.transaction

    @asynccontextmanager
    async def tracked():
        async with transaction() as session:
            ticket = opened.set(True)
            try:
                yield session
            finally:
                opened.reset(ticket)

    entered, release = asyncio.Event(), asyncio.Event()
    counter = service._counter

    async def delayed(*args):
        assert not opened.get()
        entered.set()
        await release.wait()
        return await counter(*args)

    monkeypatch.setattr(app_context.storage, "transaction", tracked)
    monkeypatch.setattr(service, "_counter", delayed)
    task = asyncio.create_task(
        service.verify_factor(owner, otp.at((int(time.time()) // 30 + 1) * 30))
    )
    await asyncio.wait_for(entered.wait(), 5)
    async with app_context.storage.transaction() as session:
        if change == "factor":
            await session.execute(
                update(AccountSecurity)
                .where(AccountSecurity.owner_id == owner)
                .values(version=AccountSecurity.version + 1)
            )
        else:
            values = (
                {"auth_revision": User.auth_revision + 1}
                if change == "revision"
                else {"is_active": False}
            )
            await session.execute(
                update(User).where(User.access_id == owner).values(**values)
            )
    release.set()
    assert await task is False


async def test_enrollment_rechecks_deadline_after_worker_wait(
    app_context, auth_client, monkeypatch
):
    owner, otp, _ = await enroll(app_context, confirm=False)
    service = app_context.session_service
    counter = service._counter

    async def expire(*args):
        async with app_context.storage.transaction() as session:
            await session.execute(
                update(AccountSecurity)
                .where(AccountSecurity.owner_id == owner)
                .values(pending_until=int(time.time()) - 1)
            )
        return await counter(*args)

    monkeypatch.setattr(service, "_counter", expire)
    with pytest.raises(HTTPException) as failure:
        await service.confirm_enrollment(owner, otp.now())
    assert failure.value.status_code == 409
    async with app_context.storage.transaction() as session:
        assert (await session.get(AccountSecurity, owner)).totp_secret is None


async def test_active_devices_and_sessions_are_not_hidden_by_newer_history(
    app_context, auth_client
):
    owner, _, _ = await enroll(app_context)
    now = int(time.time())
    async with app_context.storage.transaction() as session:
        revision = await session.scalar(
            select(User.auth_revision).where(User.access_id == owner)
        )
        for i in range(201):
            session.add(
                LoginSession(
                    id=uuid4().hex,
                    owner_id=owner,
                    name="old active" if i == 0 else "revoked",
                    user_agent="",
                    ip_address="",
                    created_at=1 if i == 0 else now,
                    last_seen_at=now,
                    expires_at=now + 3600,
                    verified_at=0,
                    revoked_at=None if i == 0 else now,
                )
            )
        for i in range(101):
            session.add(
                TrustedDevice(
                    id=uuid4().hex,
                    owner_id=owner,
                    auth_revision=revision,
                    token_digest=uuid4().hex * 2,
                    name="old active" if i == 0 else "revoked",
                    user_agent="",
                    ip_address="",
                    created_at=1 if i == 0 else now,
                    last_used_at=now,
                    expires_at=now + 3600,
                    revoked_at=None if i == 0 else now,
                )
            )
    sessions = await app_context.session_service.list_sessions(owner)
    devices = await app_context.trusted_device_service.list(owner)
    assert len(sessions) == 200 and sessions[0]["name"] == "old active"
    assert len(devices) == 100 and devices[0]["name"] == "old active"


async def test_concurrent_enrollment_confirmation_has_one_winner(
    app_context, auth_client, monkeypatch
):
    owner, otp, _ = await enroll(app_context, confirm=False)
    counter = app_context.session_service._counter
    barrier = asyncio.Barrier(2)

    async def coordinated(*args):
        await barrier.wait()
        return await counter(*args)

    monkeypatch.setattr(app_context.session_service, "_counter", coordinated)
    outcomes = await asyncio.gather(
        *(
            app_context.session_service.confirm_enrollment(owner, otp.now())
            for _ in range(2)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(outcome, dict) for outcome in outcomes) == 1
    assert (
        sum(
            isinstance(outcome, HTTPException) and outcome.status_code == 409
            for outcome in outcomes
        )
        == 1
    )

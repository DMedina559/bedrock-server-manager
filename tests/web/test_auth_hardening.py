"""Security-state races, legacy credentials, policy enrollment, and owned notices."""

import asyncio
import time
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import bcrypt
import pyotp
import pytest
from sqlalchemy import select

from bedrock_server_manager.db.models import AuthThrottle, LoginSession, User
from bedrock_server_manager.web.auth import authenticate_user
from bedrock_server_manager.web.schemas import UserResponse


async def test_legacy_bcrypt_login_upgrades_hash_without_revoking_existing_sessions(
    auth_client, app_context
):
    async with app_context.storage.transaction() as session:
        user = await session.scalar(select(User).where(User.username == "testuser"))
        user.hashed_password = bcrypt.hashpw(
            b"testpassword", bcrypt.gensalt(rounds=4)
        ).decode()
        revision = user.auth_revision
    login = await auth_client.post(
        "/auth/token", data={"username": "testuser", "password": "testpassword"}
    )
    assert login.status_code == 200, login.text
    async with app_context.storage.transaction() as session:
        user = await session.scalar(select(User).where(User.username == "testuser"))
        assert user.hashed_password.startswith("$argon2id$")
        assert user.auth_revision == revision
    assert (await auth_client.get("/api/account")).status_code == 200


async def test_unknown_accounts_do_not_skip_password_verification(
    app_context, test_user, monkeypatch
):
    verify = AsyncMock(return_value=False)
    monkeypatch.setattr("bedrock_server_manager.web.auth.verify_password_async", verify)
    assert (
        await authenticate_user(app_context, "unknown-account", "any password") is None
    )
    verify.assert_awaited_once()
    assert verify.call_args.args[1].startswith("$argon2id$")


async def test_new_password_policy_keeps_legacy_login_and_accepts_long_passphrases(
    auth_client,
):
    assert (
        await auth_client.post(
            "/auth/token", data={"username": "testuser", "password": "testpassword"}
        )
    ).status_code == 200
    for weak in ["tiny-pw", "passwordpassword", "aaaaaaaaaaaaaaaa"]:
        rejected = await auth_client.post(
            "/api/account/change-password",
            json={"current_password": "testpassword", "new_password": weak},
        )
        assert rejected.status_code == 422
        assert weak not in rejected.text
    long_password = "a long memorable Unicode passphrase 🦊 " * 4
    changed = await auth_client.post(
        "/api/account/change-password",
        json={"current_password": "testpassword", "new_password": long_password},
    )
    assert changed.status_code == 200, changed.text
    assert (
        await auth_client.post(
            "/auth/token", data={"username": "testuser", "password": long_password}
        )
    ).status_code == 200


async def test_required_admin_mfa_allows_only_enrollment_until_completed(
    admin_auth_client, app_context, test_app
):
    token_response = await admin_auth_client.post(
        "/api/account/tokens",
        json={"name": "existing integration", "permissions": ["settings:read"]},
    )
    assert token_response.status_code == 201, token_response.text
    integration = token_response.json()["token"]

    @test_app.get("/_enrollment_escape")
    async def escape():
        return {"escaped": True}

    await app_context.settings.set("security.require_admin_mfa", True)
    assert app_context.settings.get("security.require_admin_mfa") is True
    account = (await admin_auth_client.get("/api/account")).json()
    assert account["mfa_enrollment_required"] is True
    assert (await admin_auth_client.get("/_enrollment_escape")).status_code == 403
    assert set(account["permissions"]) == {"account:read", "sessions:manage"}
    assert (await admin_auth_client.get("/api/settings/get")).status_code == 403
    assert (
        await admin_auth_client.get(
            "/api/settings/get", headers={"Authorization": f"Bearer {integration}"}
        )
    ).status_code == 200
    enrollment = await admin_auth_client.post("/api/account/security/mfa/enroll")
    assert enrollment.status_code == 200, enrollment.text
    confirmed = await admin_auth_client.post(
        "/api/account/security/mfa/confirm",
        json={"code": pyotp.TOTP(enrollment.json()["secret"]).now()},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert (await admin_auth_client.get("/api/account")).json()[
        "mfa_enrollment_required"
    ] is False
    assert (await admin_auth_client.get("/api/settings/get")).status_code == 200
    assert (
        await admin_auth_client.delete("/api/account/security/mfa")
    ).status_code == 403


@pytest.mark.parametrize("operation", ["login", "verify"])
async def test_mfa_enrollment_invalidates_inflight_password_only_proof(
    auth_client, app_context, monkeypatch, operation
):
    verified, release = asyncio.Event(), asyncio.Event()
    original = app_context.session_service.verify_factor

    async def pause(owner_id, code):
        result = await original(owner_id, code)
        verified.set()
        await release.wait()
        return result

    monkeypatch.setattr(app_context.session_service, "verify_factor", pause)
    if operation == "login":
        pending = asyncio.create_task(
            auth_client.post(
                "/auth/token", data={"username": "testuser", "password": "testpassword"}
            )
        )
    else:
        pending = asyncio.create_task(
            auth_client.post(
                "/api/account/security/verify", json={"password": "testpassword"}
            )
        )
    try:
        await asyncio.wait_for(verified.wait(), 5)
        enrollment = await auth_client.post("/api/account/security/mfa/enroll")
        confirmed = await auth_client.post(
            "/api/account/security/mfa/confirm",
            json={"code": pyotp.TOTP(enrollment.json()["secret"]).now()},
        )
        assert confirmed.status_code == 200, confirmed.text
    finally:
        release.set()
    result = await pending
    assert result.status_code == 401, result.text


async def test_successful_recent_verification_resets_its_attempt_budget(
    auth_client, app_context
):
    await app_context.settings.set("security.auth_account_attempts", 3)
    for _ in range(4):
        assert (
            await auth_client.post(
                "/api/account/security/verify", json={"password": "testpassword"}
            )
        ).status_code == 200


async def test_idle_expired_sessions_do_not_exhaust_active_login_limit(
    auth_client, app_context
):
    now = int(time.time())
    async with app_context.storage.transaction() as session:
        owner = await session.scalar(
            select(User.access_id).where(User.username == "testuser")
        )
        for index in range(100):
            session.add(
                LoginSession(
                    id=f"{index:032x}",
                    owner_id=owner,
                    name="idle",
                    user_agent="",
                    ip_address="",
                    created_at=now - 90000,
                    last_seen_at=now - 90000,
                    expires_at=now + 86400,
                    verified_at=1,
                )
            )
    login = await auth_client.post(
        "/auth/token", data={"username": "testuser", "password": "testpassword"}
    )
    assert login.status_code == 200, login.text


async def test_security_notices_are_owner_scoped_and_contain_no_credentials(
    auth_client, app_context, monkeypatch
):
    manager = MagicMock()
    manager.send_to_user = AsyncMock()
    monkeypatch.setattr(app_context, "_connection_manager", manager)
    async with app_context.storage.transaction() as session:
        owner = await session.scalar(select(User).where(User.username == "testuser"))
        user = UserResponse.model_validate(owner, from_attributes=True)
        owner_id = owner.access_id
    await app_context.session_service.publish(owner_id, "recovery_code_used")
    manager.send_to_user.assert_awaited_once()
    username, message = manager.send_to_user.call_args.args
    assert username == "testuser"
    assert set(message) == {"type", "action", "owner_id", "timestamp", "event_id"}
    authorization = await app_context.access_service.snapshot(user)
    assert (
        await app_context.access_service.filter_message(authorization, message)
        == message
    )
    assert (
        await app_context.access_service.filter_message(
            replace(authorization, owner_id="other"), message
        )
        is None
    )
    assert (
        await app_context.access_service.filter_message(
            replace(authorization, token_id="token"), message
        )
        is None
    )


async def test_role_change_revokes_sessions_even_if_connection_cleanup_fails(
    auth_client, app_context, monkeypatch
):
    from bedrock_server_manager.error import IncompleteOperationError
    from bedrock_server_manager.state.updates import AccountPatch

    monkeypatch.setattr(
        app_context.user_service,
        "revoke_connections",
        AsyncMock(side_effect=RuntimeError("socket unavailable")),
    )
    with pytest.raises(IncompleteOperationError):
        await app_context.user_service.update_account(
            action="role", username="testuser", values=AccountPatch(role="moderator")
        )
    assert (await auth_client.get("/api/account")).status_code == 401
    async with app_context.storage.transaction() as session:
        owner = await session.scalar(select(User).where(User.username == "testuser"))
        assert owner.auth_revision > 0
        assert owner.role == "moderator"


async def test_throttle_cleanup_survives_configured_window_changes(
    auth_client, app_context
):
    now = int(time.time())
    async with app_context.storage.transaction() as session:
        session.add(AuthThrottle(key="old-window", window=now - 90000, attempts=1))
    await app_context.settings.set("security.auth_window_seconds", 60)
    await app_context.session_service.throttle("window-test", "window-peer")
    async with app_context.storage.transaction() as session:
        rows = (await session.scalars(select(AuthThrottle))).all()
        assert not any(row.key == "old-window" for row in rows)
        assert all(row.window >= now - 60 for row in rows)

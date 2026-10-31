"""
Integration tests for the register router endpoints, digest storage, and hardening.
"""

import asyncio
import hashlib
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from alembic import command
from alembic.config import Config
from httpx2 import AsyncClient
from sqlalchemy import select, text

import bedrock_server_manager.db.database as database_module
from bedrock_server_manager.db.models import RegistrationToken, User


async def test_generate_token_unauthorized(unauth_client: AsyncClient):
    response = await unauth_client.post(
        "/api/register/generate-token", json={"role": "user"}
    )
    assert response.status_code == 401


async def test_generate_token_forbidden(auth_client: AsyncClient):
    response = await auth_client.post(
        "/api/register/generate-token", json={"role": "user"}
    )
    assert response.status_code == 403


async def test_generate_token_success(admin_auth_client: AsyncClient, app_context):
    response = await admin_auth_client.post(
        "/api/register/generate-token", json={"role": "user"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "registration_url" in data

    raw_token = data["registration_url"].rsplit("/", 1)[-1]
    expected_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Verify only token_digest is stored in DB; plaintext token is absent
    async with app_context.db.session_manager() as db:
        res = await db.execute(
            select(RegistrationToken).filter(RegistrationToken.role == "user")
        )
        token_record = res.scalars().first()
        assert token_record is not None
        assert token_record.token_digest == expected_digest
        assert not hasattr(token_record, "token")


async def test_validate_token_success(unauth_client: AsyncClient, app_context):
    token_str = "valid_token_123"
    token_digest = hashlib.sha256(token_str.encode("utf-8")).hexdigest()
    async with app_context.db.session_manager() as db:
        token = RegistrationToken(
            token_digest=token_digest, role="user", expires=int(time.time()) + 3600
        )
        db.add(token)
        await db.commit()

    response = await unauth_client.get(f"/api/register/validate/{token_str}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


async def test_validate_token_not_found(unauth_client: AsyncClient):
    response = await unauth_client.get("/api/register/validate/invalid_token")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_validate_token_expired(unauth_client: AsyncClient, app_context):
    token_str = "expired_token_123"
    token_digest = hashlib.sha256(token_str.encode("utf-8")).hexdigest()
    async with app_context.db.session_manager() as db:
        token = RegistrationToken(
            token_digest=token_digest, role="user", expires=int(time.time()) - 3600
        )
        db.add(token)
        await db.commit()

    response = await unauth_client.get(f"/api/register/validate/{token_str}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_register_user_success(unauth_client: AsyncClient, app_context):
    token_str = "register_token_123"
    token_digest = hashlib.sha256(token_str.encode("utf-8")).hexdigest()
    async with app_context.db.session_manager() as db:
        token = RegistrationToken(
            token_digest=token_digest, role="user", expires=int(time.time()) + 3600
        )
        db.add(token)
        await db.commit()

    response = await unauth_client.post(
        f"/api/register/{token_str}",
        json={"username": "new_user", "password": "new password passphrase"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify token is deleted and user is created
    async with app_context.db.session_manager() as db:
        res = await db.execute(
            select(RegistrationToken).filter(
                RegistrationToken.token_digest == token_digest
            )
        )
        token = res.scalars().first()
        assert token is None

        res_user = await db.execute(select(User).filter(User.username == "new_user"))
        user = res_user.scalars().first()
        assert user is not None
        assert user.role == "user"


async def test_register_user_invalid_token(unauth_client: AsyncClient):
    response = await unauth_client.post(
        "/api/register/bad_token",
        json={"username": "new_user", "password": "new password passphrase"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_register_user_duplicate_username(
    unauth_client: AsyncClient, app_context, test_user
):
    token_str = "duplicate_token_123"
    token_digest = hashlib.sha256(token_str.encode("utf-8")).hexdigest()
    async with app_context.db.session_manager() as db:
        token = RegistrationToken(
            token_digest=token_digest, role="user", expires=int(time.time()) + 3600
        )
        db.add(token)
        await db.commit()

    response = await unauth_client.post(
        f"/api/register/{token_str}",
        json={"username": test_user.username, "password": "new password passphrase"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert "already exists" in response.json()["error"]["message"]


async def test_pre_hash_invitation_validation_skips_expensive_hashing(
    unauth_client: AsyncClient, app_context
):
    """Ensure invalid/expired invitations reject before computing Argon2id hashes."""
    token_str = "expired_invite_999"
    token_digest = hashlib.sha256(token_str.encode("utf-8")).hexdigest()
    async with app_context.db.session_manager() as db:
        token = RegistrationToken(
            token_digest=token_digest, role="user", expires=int(time.time()) - 100
        )
        db.add(token)
        await db.commit()

    with patch(
        "bedrock_server_manager.web.routers.register.get_password_hash_async",
        new=AsyncMock(),
    ) as mock_hash:
        # 1. Expired token
        res_expired = await unauth_client.post(
            f"/api/register/{token_str}",
            json={"username": "cheap_user1", "password": "secure passphrase 123"},
        )
        assert res_expired.status_code == 404
        mock_hash.assert_not_called()

        # 2. Non-existent token
        res_nonexistent = await unauth_client.post(
            "/api/register/nonexistent_invite_token",
            json={"username": "cheap_user2", "password": "secure passphrase 123"},
        )
        assert res_nonexistent.status_code == 404
        mock_hash.assert_not_called()


async def test_concurrent_invitation_redemption_allows_only_one_user(
    unauth_client: AsyncClient, app_context, monkeypatch
):
    """Deterministic concurrency test: two submissions for the same token yield at most one user."""
    token_str = "race_invite_token_777"
    token_digest = hashlib.sha256(token_str.encode("utf-8")).hexdigest()
    async with app_context.db.session_manager() as db:
        token = RegistrationToken(
            token_digest=token_digest, role="user", expires=int(time.time()) + 3600
        )
        db.add(token)
        await db.commit()

    # Force both requests to observe a valid invitation before either may consume it.
    barrier = asyncio.Barrier(2)
    original = app_context.user_service.validate_registration_token

    async def validated_together(candidate):
        valid = await original(candidate)
        assert valid
        await asyncio.wait_for(barrier.wait(), timeout=10)
        return valid

    monkeypatch.setattr(
        app_context.user_service, "validate_registration_token", validated_together
    )
    responses = await asyncio.gather(
        unauth_client.post(
            f"/api/register/{token_str}",
            json={"username": "concurrent_a", "password": "long valid passphrase 123"},
        ),
        unauth_client.post(
            f"/api/register/{token_str}",
            json={"username": "concurrent_b", "password": "long valid passphrase 123"},
        ),
    )

    statuses = [r.status_code for r in responses]
    # Exactly one succeeded (200) and one failed (404)
    assert statuses.count(200) == 1
    assert statuses.count(404) == 1

    # Verify database has exactly one user registered and token is consumed
    async with app_context.db.session_manager() as db:
        res = await db.execute(
            select(RegistrationToken).filter(
                RegistrationToken.token_digest == token_digest
            )
        )
        assert res.scalars().first() is None

        users = (
            (
                await db.execute(
                    select(User).filter(
                        User.username.in_(["concurrent_a", "concurrent_b"])
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(users) == 1


async def test_registration_peer_throttling(unauth_client: AsyncClient, app_context):
    """Verify peer throttling limits repeated registration attempts."""
    await app_context.settings.set("security.auth_peer_attempts", 10)
    try:
        # Rapidly attempt to validate non-existent tokens up to the configured limit
        for i in range(10):
            res = await unauth_client.get(f"/api/register/validate/probe_{i}")
            assert res.status_code == 404

        # 11th attempt from the same client should be throttled (429)
        throttled_res = await unauth_client.get("/api/register/validate/probe_blocked")
        assert throttled_res.status_code == 429
        assert "Retry-After" in throttled_res.headers
    finally:
        await app_context.settings.set("security.auth_peer_attempts", 60)


async def test_migrated_legacy_invitation_registers_once(
    unauth_client: AsyncClient, app_context
):
    raw_token = "legacy-invitation-before-digests"
    deadline = int(time.time()) + 3600
    config = Config(str(Path(database_module.__file__).parent / "alembic.ini"))
    config.set_main_option("skip_logging_config", "true")

    def migrate_legacy(connection):
        config.attributes["connection"] = connection
        command.downgrade(config, "i05e934a61c2")
        connection.execute(
            text(
                "INSERT INTO registration_tokens (token, role, expires) VALUES (:token, :role, :expires)"
            ),
            {"token": raw_token, "role": "moderator", "expires": deadline},
        )
        command.upgrade(config, "head")

    async with app_context.db.engine.begin() as connection:
        await connection.run_sync(migrate_legacy)
    async with app_context.db.session_manager() as session:
        record = await app_context.storage.user_repo.get_registration_token(
            session, raw_token
        )
        assert record.role == "moderator"
        assert record.expires == deadline

    assert (
        await unauth_client.get(f"/api/register/validate/{raw_token}")
    ).status_code == 200
    response = await unauth_client.post(
        f"/api/register/{raw_token}",
        json={
            "username": "legacy_invitee",
            "password": "migrated invitation passphrase",
        },
    )
    assert response.status_code == 200, response.text
    async with app_context.db.session_manager() as session:
        user = await session.scalar(
            select(User).where(User.username == "legacy_invitee")
        )
        assert user.role == "moderator"
        assert (
            await app_context.storage.user_repo.get_registration_token(
                session, raw_token
            )
            is None
        )
    assert (
        await unauth_client.get(f"/api/register/validate/{raw_token}")
    ).status_code == 404
    assert (
        await unauth_client.post(
            f"/api/register/{raw_token}",
            json={
                "username": "legacy_second",
                "password": "another invitation passphrase",
            },
        )
    ).status_code == 404


async def test_throttled_registration_post_never_hashes_or_consumes_invitation(
    unauth_client: AsyncClient, app_context, monkeypatch
):
    # Avoid a fixed-window boundary between the two requests.
    monkeypatch.setattr(
        "bedrock_server_manager.services.session_service.time.time", lambda: 2000000000
    )
    await app_context.settings.set("security.auth_peer_attempts", 10)
    token = await app_context.user_service.create_registration_token("user")
    for _ in range(10):
        assert (
            await unauth_client.get(f"/api/register/validate/{token}")
        ).status_code == 200
    with patch(
        "bedrock_server_manager.web.routers.register.get_password_hash_async",
        new_callable=AsyncMock,
    ) as hasher:
        response = await unauth_client.post(
            f"/api/register/{token}",
            json={
                "username": "throttled_invitee",
                "password": "valid registration passphrase",
            },
        )
        assert response.status_code == 429
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "Retry-After" in response.headers
        hasher.assert_not_awaited()
    assert await app_context.user_service.validate_registration_token(token)
    async with app_context.db.session_manager() as session:
        assert (
            await session.scalar(
                select(User).where(User.username == "throttled_invitee")
            )
            is None
        )


@pytest.mark.parametrize(
    "path", ["/api/register/validate/private-invite", "/app/register/private-invite"]
)
async def test_invitation_responses_are_not_cached_or_forwarded_as_referrers(
    unauth_client, path
):
    response = await unauth_client.get(path)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"

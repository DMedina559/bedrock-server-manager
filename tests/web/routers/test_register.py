"""
Integration tests for the register router endpoints, digest storage, and hardening.
"""

import asyncio
import hashlib
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

from alembic import command
from alembic.config import Config
from httpx2 import AsyncClient
from sqlalchemy import select, text

import bedrock_server_manager.db.database as database_module
from bedrock_server_manager.db.models import RegistrationToken, User


async def test_generate_validate_and_register_user_lifecycle(
    unauth_client: AsyncClient,
    auth_client: AsyncClient,
    admin_auth_client: AsyncClient,
    app_context,
    test_user,
):
    # Authorization checks on generate-token
    assert (
        await unauth_client.post("/api/register/generate-token", json={"role": "user"})
    ).status_code == 401
    assert (
        await auth_client.post("/api/register/generate-token", json={"role": "user"})
    ).status_code == 403

    # Admin generates token; only digest stored
    response = await admin_auth_client.post(
        "/api/register/generate-token", json={"role": "user"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success" and "registration_url" in data
    raw_token = data["registration_url"].rsplit("/", 1)[-1]
    expected_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    async with app_context.db.session_manager() as db:
        res = await db.execute(
            select(RegistrationToken).filter(RegistrationToken.role == "user")
        )
        token_record = res.scalars().first()
        assert token_record is not None
        assert token_record.token_digest == expected_digest
        assert not hasattr(token_record, "token")

    # Validate valid, missing, and expired tokens + cache/referrer headers
    for path in (
        "/api/register/validate/private-invite",
        "/app/register/private-invite",
    ):
        hdr_resp = await unauth_client.get(path)
        assert hdr_resp.headers["Cache-Control"] == "no-store"
        assert hdr_resp.headers["Referrer-Policy"] == "no-referrer"

    assert (
        await unauth_client.get(f"/api/register/validate/{raw_token}")
    ).status_code == 200
    assert (
        await unauth_client.get("/api/register/validate/invalid_token")
    ).status_code == 404

    expired_str = "expired_token_123"
    expired_digest = hashlib.sha256(expired_str.encode("utf-8")).hexdigest()
    async with app_context.db.session_manager() as db:
        db.add(
            RegistrationToken(
                token_digest=expired_digest,
                role="user",
                expires=int(time.time()) - 3600,
            )
        )
        await db.commit()
    assert (
        await unauth_client.get(f"/api/register/validate/{expired_str}")
    ).status_code == 404

    # Pre-hash invitation validation skips expensive hashing on expired/missing tokens
    with patch(
        "bedrock_server_manager.web.routers.register.get_password_hash_async",
        new=AsyncMock(),
    ) as mock_hash:
        assert (
            await unauth_client.post(
                f"/api/register/{expired_str}",
                json={"username": "cheap_user1", "password": "secure passphrase 123"},
            )
        ).status_code == 404
        assert (
            await unauth_client.post(
                "/api/register/nonexistent_invite_token",
                json={"username": "cheap_user2", "password": "secure passphrase 123"},
            )
        ).status_code == 404
        mock_hash.assert_not_called()

    # Duplicate username rejected without consuming valid token
    dup_resp = await unauth_client.post(
        f"/api/register/{raw_token}",
        json={"username": test_user.username, "password": "new password passphrase"},
    )
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.json()["error"]["message"]

    # Successful registration consumes token and creates user
    reg_resp = await unauth_client.post(
        f"/api/register/{raw_token}",
        json={"username": "new_user", "password": "new password passphrase"},
    )
    assert reg_resp.status_code == 200 and reg_resp.json()["status"] == "success"

    async with app_context.db.session_manager() as db:
        assert (
            await db.scalar(
                select(RegistrationToken).filter(
                    RegistrationToken.token_digest == expected_digest
                )
            )
            is None
        )
        user = await db.scalar(select(User).filter(User.username == "new_user"))
        assert user is not None and user.role == "user"


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
    assert statuses.count(200) == 1
    assert statuses.count(404) == 1

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


async def test_registration_peer_throttling_and_post_protection(
    unauth_client: AsyncClient, app_context, monkeypatch
):
    """Verify peer throttling limits validation probes and protects POST from hashing/consuming."""
    monkeypatch.setattr(
        "bedrock_server_manager.services.session_service.time.time", lambda: 2000000000
    )
    await app_context.settings.set("security.auth_peer_attempts", 10)
    token = await app_context.user_service.create_registration_token("user")

    for i in range(10):
        res = await unauth_client.get(f"/api/register/validate/probe_{i}")
        assert res.status_code == 404

    throttled_res = await unauth_client.get("/api/register/validate/probe_blocked")
    assert throttled_res.status_code == 429
    assert "Retry-After" in throttled_res.headers

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


async def test_migrated_legacy_invitation_registers_once(
    unauth_client: AsyncClient, app_context
):
    raw_token = "legacy-invitation-before-digests"
    deadline = int(time.time()) + 3600
    config = Config(str(Path(database_module.__file__).parent / "alembic.ini"))
    config.set_main_option("skip_logging_config", "true")

    def migrate_legacy(connection):
        config.attributes["connection"] = connection
        command.downgrade(config, "f72c401a908b")
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

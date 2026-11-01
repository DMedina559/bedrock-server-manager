"""Negative and concurrent ceremonies must enforce the same policy as ordinary logins."""

import asyncio

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bedrock_server_manager.db.models import AuthSecurityEvent, PasskeyChallenge, User
from tests.web.test_passkeys_and_credentials import FakeAuthenticator


async def enroll(client):
    device = FakeAuthenticator(sign_count=0)
    options = (
        await client.post("/api/account/security/passkeys/register/options")
    ).json()
    created = await client.post(
        "/api/account/security/passkeys/register/verify",
        json={
            "challenge_id": options["challenge_id"],
            "credential": device.create(challenge=options["public_key"]["challenge"]),
        },
    )
    assert created.status_code == 201, created.text
    return device, created.json()


async def assertion(client, device, *, uv=True, step_up=False):
    path = (
        "/api/account/security/passkeys/verify/options"
        if step_up
        else "/auth/passkey/options"
    )
    options = (await client.post(path, json={})).json()
    return {
        "challenge_id": options["challenge_id"],
        "credential": device.get(
            challenge=options["public_key"]["challenge"], uv=uv, increment=0
        ),
    }


async def test_passkey_only_admin_cannot_use_password_alone(
    admin_auth_client, unauth_client, app_context
):
    from bedrock_server_manager.web.auth import get_password_hash_async

    await app_context.settings.set("security.require_admin_mfa", True)
    await enroll(admin_auth_client)
    async with app_context.storage.transaction() as session:
        owner = await session.scalar(select(User).where(User.role == "admin"))
        username = owner.username
        owner.hashed_password = await get_password_hash_async("AuditPassword42!")
    response = await unauth_client.post(
        "/auth/token", data={"username": username, "password": "AuditPassword42!"}
    )
    assert response.status_code == 401
    assert response.headers["X-BSM-MFA"] == "passkey"
    assert "access_token_cookie" not in response.cookies
    response = await admin_auth_client.post(
        "/api/account/security/verify", json={"password": "AuditPassword42!"}
    )
    assert response.status_code == 401
    assert response.headers["X-BSM-MFA"] == "passkey"


async def test_user_verification_required_for_login_and_step_up(
    auth_client, unauth_client
):
    device, _ = await enroll(auth_client)
    for client, step_up, path in [
        (unauth_client, False, "/auth/passkey/verify"),
        (auth_client, True, "/api/account/security/passkeys/verify"),
    ]:
        response = await client.post(
            path, json=await assertion(client, device, uv=False, step_up=step_up)
        )
        assert response.status_code == 401, response.text


async def test_registration_requires_user_verification(auth_client):
    device = FakeAuthenticator()
    options = (
        await auth_client.post("/api/account/security/passkeys/register/options")
    ).json()
    assert (
        options["public_key"]["authenticatorSelection"]["userVerification"]
        == "required"
    )
    response = await auth_client.post(
        "/api/account/security/passkeys/register/verify",
        json={
            "challenge_id": options["challenge_id"],
            "credential": device.create(
                challenge=options["public_key"]["challenge"], uv=False
            ),
        },
    )
    assert response.status_code == 400


@pytest.mark.parametrize("step_up", [False, True])
async def test_concurrent_zero_counter_challenge_is_consumed_once(
    auth_client, unauth_client, monkeypatch, step_up
):
    device, _ = await enroll(auth_client)
    client = auth_client if step_up else unauth_client
    payload = await assertion(client, device, step_up=step_up)
    original = AsyncSession.get
    both_read = asyncio.Event()
    reads = 0

    async def synchronized_get(self, entity, ident, *args, **kwargs):
        nonlocal reads
        row = await original(self, entity, ident, *args, **kwargs)
        if entity is PasskeyChallenge and ident == payload["challenge_id"]:
            reads += 1
            if reads == 2:
                both_read.set()
            await asyncio.wait_for(both_read.wait(), 5)
        return row

    monkeypatch.setattr(AsyncSession, "get", synchronized_get)
    path = (
        "/api/account/security/passkeys/verify" if step_up else "/auth/passkey/verify"
    )
    responses = await asyncio.gather(
        *[client.post(path, json=payload) for _ in range(2)]
    )
    assert sorted(r.status_code for r in responses) == [200, 401], [
        r.text for r in responses
    ]


async def test_revoked_passkey_cannot_finish_new_login(
    auth_client, unauth_client, app_context, monkeypatch
):
    device, key = await enroll(auth_client)
    payload = await assertion(unauth_client, device)
    service = app_context.session_service
    original = service.complete_passkey_login

    async def revoke_before_return(payload, request):
        username, proof = await original(payload, request)
        await service.revoke_passkey(proof.owner_id, key["id"])
        return username, proof

    monkeypatch.setattr(service, "complete_passkey_login", revoke_before_return)
    response = await unauth_client.post("/auth/passkey/verify", json=payload)
    assert response.status_code == 401, response.text


async def test_oversized_auth_body_and_chunked_body_rejected(unauth_client):
    response = await unauth_client.post("/auth/passkey/verify", content=b"x" * 65537)
    assert response.status_code == 413

    async def chunks():
        for _ in range(5):
            yield b"x" * 16384

    response = await unauth_client.post("/auth/passkey/verify", content=chunks())
    assert response.status_code == 413


async def test_concurrent_counter_rejection_keeps_audit_event(
    auth_client, unauth_client, app_context, monkeypatch
):
    from bedrock_server_manager.db.models import PasskeyCredential

    service = app_context.session_service.passkeys
    device, key = await enroll(auth_client)
    options = (await unauth_client.post("/auth/passkey/options", json={})).json()
    payload = {
        "challenge_id": options["challenge_id"],
        "credential": device.get(challenge=options["public_key"]["challenge"]),
    }
    original = service._verify

    async def advance_counter(function, **kwargs):
        verified = await original(function, **kwargs)
        async with app_context.storage.transaction() as session:
            await session.execute(
                update(PasskeyCredential)
                .where(PasskeyCredential.id == key["id"])
                .values(sign_count=verified.sign_count)
            )
        return verified

    monkeypatch.setattr(service, "_verify", advance_counter)
    response = await unauth_client.post("/auth/passkey/verify", json=payload)
    assert response.status_code == 401
    async with app_context.storage.transaction() as session:
        event = await session.scalar(
            select(AuthSecurityEvent).where(
                AuthSecurityEvent.action == "passkey_clone_detected"
            )
        )
        assert event is not None


@pytest.mark.parametrize("change", ["origin", "rp_id", "challenge"])
async def test_assertion_must_match_origin_rp_and_challenge(
    auth_client, unauth_client, change
):
    device, _ = await enroll(auth_client)
    options = (await unauth_client.post("/auth/passkey/options", json={})).json()
    args = {"challenge": options["public_key"]["challenge"], "increment": 0}
    args[change] = (
        "https://untrusted.example" if change == "origin" else "untrusted.example"
    )
    response = await unauth_client.post(
        "/auth/passkey/verify",
        json={
            "challenge_id": options["challenge_id"],
            "credential": device.get(**args),
        },
    )
    assert response.status_code == 401


async def test_enrollment_revokes_other_password_sessions(
    auth_client, app_context, test_user
):
    from jose import jwt

    from bedrock_server_manager.web.auth import create_access_token

    other = await create_access_token(app_context, {"sub": test_user.username})
    other_session = jwt.get_unverified_claims(other)["sid"]
    await enroll(auth_client)
    assert await app_context.session_service.validate(other_session) is None
    assert (await auth_client.get("/api/account")).status_code == 200


async def test_old_password_only_session_cannot_inherit_enrolled_factor(
    auth_client, app_context
):
    from bedrock_server_manager.db.models import LoginSession

    await enroll(auth_client)
    account = (await auth_client.get("/api/account")).json()
    async with app_context.storage.transaction() as session:
        await session.execute(
            update(LoginSession)
            .where(LoginSession.id == account["session_id"])
            .values(factor_verified=False, authentication_method="unknown")
        )
    response = await auth_client.get("/api/account")
    assert response.status_code == 401
    assert response.headers["X-BSM-Session-Invalid"] == "1"

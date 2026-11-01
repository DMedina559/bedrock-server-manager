"""Remembered factors stay revocable, password-bound and scoped to one owner."""

import hashlib
import time

import pyotp
import pytest
from jose import jwt
from sqlalchemy import select, update

from bedrock_server_manager.db.models import LoginSession, TrustedDevice, User
from bedrock_server_manager.web.trusted_devices import cookie_name


@pytest.fixture
async def enrolled(auth_client):
    enrollment = await auth_client.post("/api/account/security/mfa/enroll")
    assert enrollment.status_code == 200, enrollment.text
    confirmed = await auth_client.post(
        "/api/account/security/mfa/confirm",
        json={"code": pyotp.TOTP(enrollment.json()["secret"]).now()},
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()["recovery_codes"]


async def login(
    client, *, otp="", proof=None, remember=False, cookie=False, password="testpassword"
):
    data = {
        "username": "testuser",
        "password": password,
        "otp": otp,
        "remember_device": str(remember).lower(),
    }
    if proof is not None:
        data["trusted_device_token"] = proof
    return await client.post(
        "/auth/token",
        data=data,
        headers={
            "X-BSM-Auth-Mode": "cookie" if cookie else "bearer",
            "Origin": "http://testserver",
        },
    )


def headers(response, proof=None):
    assert response.status_code == 200, response.text
    result = {"Authorization": "Bearer " + response.json()["access_token"]}
    if proof:
        result["X-BSM-Trusted-Device-Token"] = proof
    return result


async def test_fresh_factor_opt_in_stores_only_digest_and_never_renews_from_trust(
    auth_client, enrolled, app_context
):
    first = await login(auth_client, otp=enrolled[0], remember=True)
    proof = first.json()["trusted_device_token"]
    expiry = first.json()["trusted_device_expires_at"]
    assert proof.startswith("bsm_td_") and "set-cookie" not in first.headers
    assert 30 * 86400 - 5 <= expiry - int(time.time()) <= 30 * 86400
    async with app_context.storage.transaction() as session:
        row = await session.scalar(select(TrustedDevice))
        assert row.token_digest == hashlib.sha256(proof.encode()).hexdigest()
        assert row.token_digest != proof and proof not in repr(row.__dict__)
    again = await login(auth_client, proof=proof, remember=True)
    assert again.status_code == 200, again.text
    assert again.json()["trusted_device_token"] is None
    async with app_context.storage.transaction() as session:
        rows = list(await session.scalars(select(TrustedDevice)))
        assert len(rows) == 1 and rows[0].expires_at == expiry
    wrong = await login(auth_client, proof=proof, password="wrong")
    assert wrong.status_code == 401
    explicit_bad_otp = await login(auth_client, proof=proof, otp="wrong")
    assert explicit_bad_otp.status_code == 401
    assert (
        await auth_client.get(
            "/api/account", headers={"Authorization": f"Bearer {proof}"}
        )
    ).status_code == 401


async def test_password_only_accounts_cannot_mint_remembered_factors(
    auth_client, app_context
):
    response = await login(auth_client, remember=True)
    assert response.status_code == 200
    assert response.json()["trusted_device_token"] is None
    async with app_context.storage.transaction() as session:
        assert (await session.scalar(select(TrustedDevice))) is None


async def test_cookie_credentials_are_httponly_and_not_reused_by_bearer_mode(
    auth_client, enrolled, app_context
):
    remembered = await login(auth_client, otp=enrolled[0], remember=True, cookie=True)
    assert remembered.status_code == 200, remembered.text
    assert remembered.json()["trusted_device_token"] is None
    async with app_context.storage.transaction() as session:
        owner_id = await session.scalar(
            select(User.access_id).where(User.username == "testuser")
        )
    name = cookie_name(owner_id)
    cookie = auth_client.cookies.get(name)
    assert cookie and cookie not in remembered.text
    set_cookie = "\n".join(remembered.headers.get_list("set-cookie"))
    assert "HttpOnly" in set_cookie and "SameSite=lax" in set_cookie
    assert (await login(auth_client, cookie=True)).status_code == 200
    no_ambient_cookie = await login(auth_client)
    assert no_ambient_cookie.status_code == 401
    assert no_ambient_cookie.headers["X-BSM-MFA"] == "required"
    assert (await login(auth_client, cookie=True, proof="invalid")).status_code == 401


async def test_trust_allows_password_reverification_and_keeps_only_current_device_on_rotation(
    auth_client, enrolled, app_context
):
    first = await login(auth_client, otp=enrolled[0], remember=True)
    second = await login(auth_client, otp=enrolled[1], remember=True)
    proof = first.json()["trusted_device_token"]
    other = second.json()["trusted_device_token"]
    auth = headers(first, proof)
    sid = jwt.get_unverified_claims(first.json()["access_token"])["sid"]
    async with app_context.storage.transaction() as session:
        await session.execute(
            update(LoginSession).where(LoginSession.id == sid).values(verified_at=0)
        )
    denied = await auth_client.post(
        "/api/account/security/mfa/recovery-codes", headers=auth
    )
    assert (
        denied.status_code == 403 and denied.headers["X-BSM-Recent-Auth"] == "required"
    )
    wrong = await auth_client.post(
        "/api/account/security/verify",
        headers=auth,
        json={"password": "wrong", "trusted_device_token": proof},
    )
    assert wrong.status_code == 401
    verified = await auth_client.post(
        "/api/account/security/verify",
        headers=auth,
        json={"password": "testpassword", "trusted_device_token": proof},
    )
    assert verified.status_code == 200, verified.text
    rotated = await auth_client.post(
        "/api/account/security/mfa/recovery-codes", headers=auth
    )
    assert rotated.status_code == 200 and len(rotated.json()["recovery_codes"]) == 10
    assert (await login(auth_client, proof=proof)).status_code == 200
    assert (await login(auth_client, proof=other)).status_code == 401
    assert (await login(auth_client, proof=proof)).json()[
        "trusted_device_token"
    ] is None


async def test_device_revocation_invalidates_recent_proof_but_not_the_login(
    auth_client, enrolled, app_context
):
    remembered = await login(auth_client, otp=enrolled[0], remember=True)
    proof = remembered.json()["trusted_device_token"]
    auth = headers(await login(auth_client, proof=proof), proof)
    devices = await auth_client.get("/api/account/security/devices", headers=auth)
    assert devices.status_code == 200 and devices.json()[0]["current"]
    assert proof not in devices.text and "token_digest" not in devices.text
    device_id = devices.json()[0]["id"]
    revoked = await auth_client.delete(
        f"/api/account/security/devices/{device_id}", headers=auth
    )
    assert revoked.status_code == 200
    assert "set-cookie" not in revoked.headers
    assert (await auth_client.get("/api/account", headers=auth)).status_code == 200
    assert (
        await auth_client.post("/api/account/security/mfa/recovery-codes", headers=auth)
    ).status_code == 403
    assert (await login(auth_client, proof=proof)).status_code == 401


@pytest.mark.parametrize("mutation", ["expire", "disable", "password", "tamper"])
async def test_expired_or_invalidated_credentials_never_skip_otp(
    auth_client, enrolled, app_context, mutation
):
    remembered = await login(auth_client, otp=enrolled[0], remember=True)
    proof = remembered.json()["trusted_device_token"]
    if mutation == "expire":
        async with app_context.storage.transaction() as session:
            await session.execute(
                update(TrustedDevice).values(expires_at=int(time.time()))
            )
    elif mutation == "disable":
        await app_context.user_service.update_account(
            action="disable", username="testuser"
        )
    elif mutation == "password":
        await app_context.user_service.reset_password(
            "testuser", "replacement password phrase"
        )
    else:
        proof = proof[:-1] + ("A" if proof[-1] != "A" else "B")
    response = await login(
        auth_client,
        proof=proof,
        password=(
            "replacement password phrase" if mutation == "password" else "testpassword"
        ),
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()


async def test_reverify_can_remember_after_a_fresh_recovery_code(auth_client, enrolled):
    response = await auth_client.post(
        "/api/account/security/verify",
        json={"password": "testpassword", "otp": enrolled[0], "remember_device": True},
        headers={
            "Authorization": headers(await login(auth_client, otp=enrolled[1]))[
                "Authorization"
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["trusted_device_token"].startswith("bsm_td_")


async def test_forgetting_other_devices_preserves_current_absolute_expiry(
    auth_client, enrolled
):
    first = await login(auth_client, otp=enrolled[0], remember=True)
    second = await login(auth_client, otp=enrolled[1], remember=True)
    proof = first.json()["trusted_device_token"]
    response = await auth_client.post(
        "/api/account/security/devices/revoke",
        headers=headers(first, proof),
        json={"mode": "others"},
    )
    assert response.status_code == 200
    assert (await login(auth_client, proof=proof)).status_code == 200
    assert (
        await login(auth_client, proof=second.json()["trusted_device_token"])
    ).status_code == 401
    devices = await auth_client.get(
        "/api/account/security/devices", headers=headers(first, proof)
    )
    current = next(row for row in devices.json() if row["current"])
    assert current["expires_at"] == first.json()["trusted_device_expires_at"]
    assert (
        await auth_client.post(
            "/api/account/security/devices/revoke",
            headers=headers(first, proof),
            json={"mode": "all"},
        )
    ).status_code == 200
    assert (await login(auth_client, proof=proof)).status_code == 401


@pytest.mark.parametrize("action", ["login", "verify"])
async def test_revocation_after_factor_check_rejects_inflight_device_proof(
    auth_client, enrolled, app_context, monkeypatch, action
):
    remembered = await login(auth_client, otp=enrolled[0], remember=True)
    proof = remembered.json()["trusted_device_token"]
    service = app_context.trusted_device_service
    original = service.verify_factor

    async def revoke_after_check(*args, **kwargs):
        result = await original(*args, **kwargs)
        if result is not None and result.device_id:
            await service.revoke(result.owner_id, identifier=result.device_id)
        return result

    monkeypatch.setattr(service, "verify_factor", revoke_after_check)
    if action == "login":
        response = await login(auth_client, proof=proof)
    else:
        response = await auth_client.post(
            "/api/account/security/verify",
            headers=headers(remembered, proof),
            json={"password": "testpassword"},
        )
    assert response.status_code == 401
    assert response.headers["X-BSM-MFA"] == "required"


async def test_device_ownership_is_enforced_for_proof_and_revocation(
    auth_client, enrolled, app_context
):
    remembered = await login(auth_client, otp=enrolled[0], remember=True)
    proof = remembered.json()["trusted_device_token"]
    service = app_context.trusted_device_service
    assert await service.validate("other-owner", proof) is None
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as failure:
        await service.revoke("other-owner", identifier=service.identifier(proof))
    assert failure.value.status_code == 404
    assert (await login(auth_client, proof=proof)).status_code == 200


async def test_revoking_trust_preserves_independent_fresh_otp_verification(
    auth_client, enrolled
):
    remembered = await login(auth_client, otp=enrolled[0], remember=True)
    proof = remembered.json()["trusted_device_token"]
    auth = headers(remembered, proof)
    assert (
        await auth_client.post(
            "/api/account/security/devices/revoke", headers=auth, json={"mode": "all"}
        )
    ).status_code == 200
    assert (
        await auth_client.post("/api/account/security/mfa/recovery-codes", headers=auth)
    ).status_code == 200


async def test_device_expiry_removes_derived_recent_verification(
    auth_client, enrolled, app_context
):
    first = await login(auth_client, otp=enrolled[0], remember=True)
    proof = first.json()["trusted_device_token"]
    remembered_login = await login(auth_client, proof=proof)
    async with app_context.storage.transaction() as session:
        await session.execute(update(TrustedDevice).values(expires_at=int(time.time())))
    response = await auth_client.post(
        "/api/account/security/mfa/recovery-codes",
        headers=headers(remembered_login, proof),
    )
    assert (
        response.status_code == 403
        and response.headers["X-BSM-Recent-Auth"] == "required"
    )


async def test_device_limit_replaces_oldest_without_unbounded_active_grants(
    auth_client, enrolled, app_context
):
    from starlette.requests import Request

    from bedrock_server_manager.services.trusted_device_service import (
        MAX_DEVICES,
        FactorProof,
    )

    async with app_context.storage.transaction() as session:
        owner = await session.scalar(select(User).where(User.username == "testuser"))
        proof = FactorProof(owner.access_id, owner.auth_revision, True)
    request = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1)})
    first = None
    for _ in range(MAX_DEVICES + 1):
        token, _ = await app_context.trusted_device_service.remember(proof, request)
        if first is None:
            first = token
            async with app_context.storage.transaction() as session:
                await session.execute(update(TrustedDevice).values(created_at=1))
    assert (
        await app_context.trusted_device_service.validate(owner.access_id, first)
        is None
    )
    rows = await app_context.trusted_device_service.list(owner.access_id)
    assert sum(row["status"] == "active" for row in rows) == MAX_DEVICES

"""Cross-transport session revocation, factor recovery, and cookie boundaries."""

import time

import pyotp
import pytest
from jose import jwt
from sqlalchemy import select

from bedrock_server_manager.db.models import AccountSecurity, LoginSession


async def login(client, username="testuser", password="testpassword", **data):
    return await client.post(
        "/auth/token", data={"username": username, "password": password, **data}
    )


def bearer(response):
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_sessions_refresh_same_family_and_revoke_individually(
    auth_client, app_context
):
    first = await login(auth_client)
    second = await login(auth_client)
    first_headers, second_headers = bearer(first), bearer(second)
    one = (await auth_client.get("/api/account", headers=first_headers)).json()[
        "session_id"
    ]
    refreshed = await auth_client.post("/auth/reauth", headers=first_headers)
    assert refreshed.status_code == 200
    assert jwt.get_unverified_claims(refreshed.json()["access_token"])["sid"] == one
    assert refreshed.json()["access_token"] != first.json()["access_token"]
    assert (
        await auth_client.delete(f"/api/account/sessions/{one}", headers=second_headers)
    ).status_code == 200
    assert (
        await auth_client.get("/api/account", headers=first_headers)
    ).status_code == 401
    assert (
        await auth_client.get("/api/account", headers=bearer(refreshed))
    ).status_code == 401
    assert (
        await auth_client.get("/api/account", headers=second_headers)
    ).status_code == 200


async def test_logout_revokes_only_current_and_bearer_does_not_clear_cookie(
    auth_client,
):
    first, second = await login(auth_client), await login(auth_client)
    response = await auth_client.post("/auth/logout", headers=bearer(first))
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert (
        await auth_client.get("/api/account", headers=bearer(first))
    ).status_code == 401
    assert (
        await auth_client.get("/api/account", headers=bearer(second))
    ).status_code == 200


async def test_cookie_mode_never_returns_jwt_and_requires_csrf(auth_client):
    auth_client.cookies.clear()
    response = await auth_client.post(
        "/auth/token",
        data={"username": "testuser", "password": "testpassword"},
        headers={"X-BSM-Auth-Mode": "cookie", "Origin": "http://testserver"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"] == ""
    token = response.headers["X-BSM-CSRF-Token"]
    # Explicitly override the fixture's older session CSRF proof.
    assert (
        await auth_client.post(
            "/api/account/theme",
            json={"theme": "default"},
            headers={"X-CSRF-Token": ""},
        )
    ).status_code == 403
    assert (
        await auth_client.post(
            "/api/account/theme",
            json={"theme": "default"},
            headers={"X-CSRF-Token": token},
        )
    ).status_code == 200
    assert (
        await auth_client.post("/auth/logout", headers={"X-CSRF-Token": token})
    ).status_code == 200
    assert (await auth_client.get("/api/account")).status_code == 401


async def test_bearer_mutations_never_require_csrf_and_cookie_login_rejects_foreign_origin(
    auth_client,
):
    response = await login(auth_client)
    assert "set-cookie" not in response.headers
    assert (
        await auth_client.post(
            "/api/account/theme",
            headers={**bearer(response), "Origin": "https://remote-ui.example"},
            json={"theme": "default"},
        )
    ).status_code == 200
    response = await auth_client.post(
        "/auth/token",
        headers={"X-BSM-Auth-Mode": "cookie", "Origin": "https://evil.example"},
        data={"username": "testuser", "password": "testpassword"},
    )
    assert response.status_code == 403


async def test_recent_verification_cannot_be_renewed_by_token_refresh(
    auth_client, app_context
):
    account = (await auth_client.get("/api/account")).json()
    async with app_context.storage.transaction() as session:
        row = await session.get(LoginSession, account["session_id"])
        row.verified_at = int(time.time()) - 301
    response = await auth_client.post(
        "/api/account/tokens", json={"name": "blocked", "permissions": ["servers:read"]}
    )
    assert response.status_code == 403
    assert response.headers["X-BSM-Recent-Auth"] == "required"
    assert (
        await auth_client.post(
            "/api/account/security/verify", json={"password": "testpassword"}
        )
    ).status_code == 200
    assert (
        await auth_client.post(
            "/api/account/tokens",
            json={"name": "allowed", "permissions": ["servers:read"]},
        )
    ).status_code == 201


async def test_mfa_enrollment_encryption_replay_recovery_and_revocation(
    auth_client, app_context
):
    before = bearer(await login(auth_client))
    enrollment = await auth_client.post("/api/account/security/mfa/enroll")
    assert enrollment.status_code == 200, enrollment.text
    secret = enrollment.json()["secret"]
    code = pyotp.TOTP(secret).now()
    confirmed = await auth_client.post(
        "/api/account/security/mfa/confirm", json={"code": code}
    )
    assert confirmed.status_code == 200, confirmed.text
    recovery = confirmed.json()["recovery_codes"][0]
    assert (await auth_client.get("/api/account", headers=before)).status_code == 401
    assert (await login(auth_client)).status_code == 401
    # Enrollment consumes its time step; a captured code cannot be replayed.
    assert (await login(auth_client, otp=code)).status_code == 401
    assert (await login(auth_client, otp=recovery)).status_code == 200
    assert (await login(auth_client, otp=recovery)).status_code == 401
    async with app_context.storage.transaction() as session:
        row = await session.scalar(select(AccountSecurity))
        assert row.totp_secret != secret
        assert secret not in row.totp_secret
        assert recovery not in str(row.recovery_hashes)
    assert secret not in (await auth_client.get("/api/account/security")).text
    assert (
        recovery not in (await auth_client.get("/api/account/security/activity")).text
    )


async def test_password_reset_ends_existing_logins_without_revoking_integration_credentials(
    auth_client, app_context
):
    issued = await auth_client.post(
        "/api/account/tokens",
        json={"name": "independent", "permissions": ["account:read"]},
    )
    assert issued.status_code == 201
    assert await app_context.user_service.reset_password(
        "testuser", "replacementpassword"
    )
    assert (await auth_client.get("/api/account")).status_code == 401
    headers = {"Authorization": f"Bearer {issued.json()['token']}"}
    assert (await auth_client.get("/api/account", headers=headers)).status_code == 200


async def test_server_enforces_idle_and_absolute_expiry(auth_client, app_context):
    account = (await auth_client.get("/api/account")).json()
    async with app_context.storage.transaction() as session:
        row = await session.get(LoginSession, account["session_id"])
        row.last_seen_at = (
            int(time.time()) - app_context.session_service.idle_seconds() - 1
        )
    assert (await auth_client.get("/api/account")).status_code == 401


async def test_account_scope_and_throttle(
    auth_client, admin_auth_client, test_admin_user
):
    assert (
        await auth_client.get(f"/api/access/users/{test_admin_user.id}/sessions")
    ).status_code == 403
    own = (await auth_client.get("/api/account/sessions")).json()[0]["id"]
    assert (
        await admin_auth_client.delete(f"/api/account/sessions/{own}")
    ).status_code == 404
    for _ in range(10):
        assert (await login(auth_client, password="wrongpassword")).status_code == 401
    blocked = await login(auth_client, password="wrongpassword")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


async def test_rotation_replaces_only_the_selected_credential_and_preserves_limits(
    auth_client,
):
    issued = await auth_client.post(
        "/api/account/tokens",
        json={
            "name": "rotation",
            "permissions": ["account:read"],
            "expires_in_days": 1,
        },
    )
    original = issued.json()
    response = await auth_client.post(
        f"/api/account/tokens/{original['credential']['id']}/rotate"
    )
    assert response.status_code == 200, response.text
    rotated = response.json()
    assert rotated["credential"]["expires_at"] == original["credential"]["expires_at"]
    assert rotated["credential"]["permissions"] == original["credential"]["permissions"]
    assert (
        await auth_client.get(
            "/api/account", headers={"Authorization": f"Bearer {original['token']}"}
        )
    ).status_code == 401
    assert (
        await auth_client.get(
            "/api/account", headers={"Authorization": f"Bearer {rotated['token']}"}
        )
    ).status_code == 200
    assert (
        await auth_client.post(
            "/api/account/tokens",
            json={"name": "not delegable", "permissions": ["sessions:manage"]},
        )
    ).status_code == 422


async def test_password_reset_racing_login_cannot_create_a_new_session(
    auth_client, app_context, monkeypatch
):
    from bedrock_server_manager.web.routers import auth as auth_router

    original = auth_router.authenticate_user

    async def reset_after_verification(*args, **kwargs):
        result = await original(*args, **kwargs)
        await app_context.user_service.reset_password("testuser", "replacementpassword")
        return result

    monkeypatch.setattr(auth_router, "authenticate_user", reset_after_verification)
    response = await login(auth_client)
    assert response.status_code == 401
    assert "access_token" not in response.json()


async def test_session_revocation_closes_its_live_socket(auth_client, websocket_client):
    import json

    from websockets.exceptions import ConnectionClosed

    response = await login(auth_client)
    token = response.json()["access_token"]
    identifier = jwt.get_unverified_claims(token)["sid"]
    async with websocket_client() as socket:
        await socket.send(json.dumps({"action": "authenticate", "token": token}))
        assert json.loads(await socket.recv())["status"] == "success"
        assert (
            await auth_client.delete(f"/api/account/sessions/{identifier}")
        ).status_code == 200
        assert json.loads(await socket.recv())["type"] == "access_changed"
        with pytest.raises(ConnectionClosed):
            await socket.recv()


async def test_legacy_untracked_jwts_require_a_fresh_login(
    auth_client, app_context, test_user
):
    from bedrock_server_manager.web.auth import get_jwt_secret_key

    legacy = jwt.encode(
        {
            "sub": test_user.username,
            "aid": test_user.access_id,
            "exp": int(time.time()) + 1000,
        },
        await get_jwt_secret_key(app_context.settings),
        algorithm="HS256",
    )
    response = await auth_client.get(
        "/api/account", headers={"Authorization": f"Bearer {legacy}"}
    )
    assert response.status_code == 401
    assert response.headers["X-BSM-Session-Invalid"] == "1"


async def test_trusted_proxy_origin_for_cookie_mode_and_untrusted_header_rejection(
    app_context, test_user
):
    from httpx2 import ASGITransport, AsyncClient

    from bedrock_server_manager.web.app import create_web_app

    app = create_web_app(app_context)
    headers = {
        "X-BSM-Auth-Mode": "cookie",
        "X-Forwarded-Host": "bsm.example",
        "X-Forwarded-Proto": "https",
        "Origin": "https://bsm.example",
    }
    for peer, status in (("127.0.0.1", 200), ("192.0.2.9", 403)):
        async with AsyncClient(
            transport=ASGITransport(app=app, client=(peer, 1234)),
            base_url="http://internal",
        ) as client:
            response = await client.post(
                "/auth/token",
                headers=headers,
                data={"username": test_user.username, "password": "testpassword"},
            )
            assert response.status_code == status


async def test_successful_login_resets_account_failure_budget(auth_client):
    for _ in range(11):
        assert (await login(auth_client)).status_code == 200


async def test_missing_mfa_key_cannot_be_replaced_by_another_enrollment(
    auth_client, app_context
):
    headers = bearer(await login(auth_client))
    async with app_context.storage.transaction() as session:
        session.add(
            AccountSecurity(
                owner_id="another-owner",
                totp_secret="encrypted-existing-secret",
                recovery_hashes=[],
                last_counter=-1,
                version=0,
            )
        )
    response = await auth_client.post(
        "/api/account/security/mfa/enroll", headers=headers
    )
    assert response.status_code == 503

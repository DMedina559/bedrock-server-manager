"""Authorization precedes server probes; cookie proof and credential boundaries."""

import re
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, update

from bedrock_server_manager.db.models import LoginSession
from bedrock_server_manager.web.access_metadata import api_routes, dependency_tree
from bedrock_server_manager.web.deps.server import (
    validate_server_exists,
    validate_server_registered,
)
from bedrock_server_manager.web.schemas import UserResponse


@pytest.mark.parametrize("assigned", [False, True])
async def test_server_probes_never_run_for_anonymous_or_unprivileged_tokens(
    test_app, unauth_client, admin_auth_client, app_context, monkeypatch, assigned
):
    from bedrock_server_manager.db.models import Server
    from bedrock_server_manager.utils import server as server_utils
    from bedrock_server_manager.web.authorization import SERVER_PERMISSIONS

    await app_context.server_service.register_or_update_server(
        "allowed", status="STOPPED"
    )
    async with app_context.storage.transaction() as session:
        allowed = await session.scalar(
            select(Server.access_id).where(Server.server_name == "allowed")
        )
    payload = {
        "name": "No private server access",
        "permissions": sorted(SERVER_PERMISSIONS) if assigned else ["account:read"],
    }
    if assigned:
        payload["server_ids"] = [allowed]
    issued = await admin_auth_client.post("/api/account/tokens", json=payload)
    assert issued.status_code == 201
    token = issued.json()["token"]
    # Register a real identity so the same denial must hold for known and absent names.
    await app_context.server_service.register_or_update_server(
        "private", status="STOPPED"
    )
    probe = AsyncMock(
        side_effect=AssertionError("Resource probed before authorization")
    )
    monkeypatch.setattr(server_utils, "validate_server", probe)
    monkeypatch.setattr(
        app_context,
        "get_server",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Registered server probed")
        ),
    )
    routes = [
        route
        for route in api_routes(test_app)
        if any(
            node.call in {validate_server_exists, validate_server_registered}
            for node in dependency_tree(route.dependant)
        )
    ]
    assert routes
    for route in routes:
        for name in ("private", "missing"):
            path = re.sub(r"\{[^}]+\}", "1", route.path.replace("{server_name}", name))
            method = next(iter(route.methods - {"HEAD", "OPTIONS"}))
            anonymous = await unauth_client.request(method, path, json={})
            assert anonymous.status_code == 401, (method, path, anonymous.text)
            restricted = await unauth_client.request(
                method, path, json={}, headers={"Authorization": f"Bearer {token}"}
            )
            assert restricted.status_code == 403, (method, path, restricted.text)
    probe.assert_not_awaited()


async def test_cookie_mutations_fail_closed_when_authenticated_proof_is_missing(
    auth_client, monkeypatch
):
    from bedrock_server_manager.web.middleware import auth

    async def identity(request):
        request.state.credential_source = "cookie"
        return UserResponse(id=1, username="testuser", role="user", is_active=True)

    monkeypatch.setattr(auth, "get_current_user_optional", identity)
    response = await auth_client.post("/api/account/theme", json={"theme": "default"})
    assert response.status_code == 403
    assert "CSRF" in response.text


async def test_invalid_cookie_clears_only_cookie_authentication(auth_client):
    cookie = {"Cookie": "access_token_cookie=invalid-token"}
    response = await auth_client.get("/api/account", headers=cookie)
    assert response.status_code == 401
    assert response.headers["X-BSM-Session-Invalid"] == "1"
    assert 'access_token_cookie=""' in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    bearer = await auth_client.get(
        "/api/account", headers={**cookie, "Authorization": "Bearer invalid-token"}
    )
    assert bearer.status_code == 401
    assert "set-cookie" not in bearer.headers


@pytest.mark.parametrize(
    "path, bypass",
    [
        ("/themes/test.css", True),
        ("/themes", True),
        ("/themes-private", False),
        ("/assets-private", False),
    ],
)
async def test_theme_bypass_uses_path_boundaries(
    unauth_client, test_admin_user, monkeypatch, path, bypass
):
    from bedrock_server_manager.web.middleware import auth

    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(auth, "get_current_user_optional", lookup)
    await unauth_client.get(path)
    assert lookup.await_count == (0 if bypass else 1)


async def test_administrative_recent_proof_checked_once(
    admin_auth_client, app_context, test_user, monkeypatch
):
    service = app_context.session_service
    recent = AsyncMock(wraps=service.require_recent)
    monkeypatch.setattr(service, "require_recent", recent)
    response = await admin_auth_client.post(
        f"/api/access/users/{test_user.id}/sessions/revoke"
    )
    assert response.status_code == 200, response.text
    recent.assert_awaited_once()
    async with app_context.storage.transaction() as session:
        await session.execute(update(LoginSession).values(verified_at=0))
    recent.reset_mock()
    response = await admin_auth_client.post(
        f"/api/access/users/{test_user.id}/sessions/revoke"
    )
    assert response.status_code == 403
    assert response.headers["X-BSM-Recent-Auth"] == "required"
    recent.assert_awaited_once()


async def test_expired_mfa_step_up_is_explicit_and_retry_works(
    auth_client, app_context
):
    async with app_context.storage.transaction() as session:
        await session.execute(update(LoginSession).values(verified_at=0))
    response = await auth_client.post("/api/account/security/mfa/enroll")
    assert response.status_code == 403
    assert response.headers["X-BSM-Recent-Auth"] == "required"
    verified = await auth_client.post(
        "/api/account/security/verify", json={"password": "testpassword"}
    )
    assert verified.status_code == 200, verified.text
    assert (
        await auth_client.post("/api/account/security/mfa/enroll")
    ).status_code == 200


async def test_private_images_accept_bearer_credentials_and_prevent_caching(
    admin_auth_client, app_context, tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from bedrock_server_manager.utils import server as server_utils
    from bedrock_server_manager.web.routers import addon

    issued = await admin_auth_client.post(
        "/api/account/tokens",
        json={"name": "Icons", "permissions": ["worlds:read", "addons:read"]},
    )
    assert issued.status_code == 201
    image = tmp_path / "icon.png"
    image.write_bytes(b"synthetic-image")
    monkeypatch.setattr(server_utils, "validate_server", AsyncMock(return_value=True))
    monkeypatch.setattr(
        app_context,
        "get_server",
        lambda *args, **kwargs: SimpleNamespace(
            worlds=SimpleNamespace(
                get_world_icon_filesystem_path=AsyncMock(return_value=str(image)),
                has_world_icon=AsyncMock(return_value=True),
            )
        ),
    )
    pack = SimpleNamespace(uuid="pack", icon=str(image))
    monkeypatch.setattr(
        addon.addon_api,
        "list_installed_addons",
        AsyncMock(
            return_value=SimpleNamespace(
                addons=SimpleNamespace(behavior_packs=[pack], resource_packs=[])
            )
        ),
    )
    headers = {"Authorization": f"Bearer {issued.json()['token']}"}
    for path in (
        "/api/server/private/world/icon",
        "/api/server/private/addon/icon?pack_type=behavior&uuid=pack",
    ):
        response = await admin_auth_client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        assert response.content == b"synthetic-image"
        assert "no-store" in response.headers["Cache-Control"]

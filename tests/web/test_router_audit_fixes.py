"""Credential migration and effective router boundary regressions."""

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import APIRouter, Security
from jose import jwt

from bedrock_server_manager.error import ConfigurationError
from bedrock_server_manager.services import jwt_credentials
from bedrock_server_manager.state.changeset import ChangeSet
from bedrock_server_manager.web.auth import get_jwt_secret_key
from bedrock_server_manager.web.contract import export_contract
from bedrock_server_manager.web.deps.auth import require_permissions


def key_path(context):
    return Path(context.config_dir) / "credentials" / "jwt.key"


async def legacy_key(context, value):
    changes = ChangeSet()
    changes.add_setting("web")
    await context.storage.commit_settings(
        context.state,
        changes,
        lambda candidate: candidate.set("web.jwt_secret_key", value),
    )


async def test_migration_preserves_old_jwt_and_removes_database_secret(
    app_context, test_user, unauth_client
):
    secret = "synthetic-pre-migration-signing-key"
    await legacy_key(app_context, secret)
    session, _ = await app_context.session_service.create(
        test_user.access_id, int(time.time()) + 3600
    )
    token = jwt.encode(
        {
            "sub": test_user.username,
            "aid": test_user.access_id,
            "sid": session,
            "exp": int(time.time()) + 3600,
        },
        secret,
        algorithm="HS256",
    )
    assert await get_jwt_secret_key(app_context.settings) == secret
    assert (
        await unauth_client.get(
            "/api/account", headers={"Authorization": "Bearer " + token}
        )
    ).status_code == 200
    async with app_context.storage.transaction() as db:
        raw = await app_context.storage.settings_repo.get_all_settings(db)
    assert "jwt_secret_key" not in raw["web"]
    assert "web.jwt_secret_key" not in raw
    assert raw["web"]["jwt_key_initialized"] is True
    assert secret not in json.dumps(raw)
    app_context.settings._jwt_signing_credential = None
    await app_context.settings.reload()
    assert await get_jwt_secret_key(app_context.settings) == secret
    if os.name != "nt":
        assert key_path(app_context).stat().st_mode & 0o777 == 0o600
        assert key_path(app_context).parent.stat().st_mode & 0o777 == 0o700


async def test_failed_credential_write_leaves_legacy_value_retryable(
    app_context, monkeypatch
):
    secret = "synthetic-legacy-retry-key"
    await legacy_key(app_context, secret)
    write = jwt_credentials.atomic_bytes

    def fail(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr(jwt_credentials, "atomic_bytes", fail)
    with pytest.raises(ConfigurationError):
        await get_jwt_secret_key(app_context.settings)
    assert app_context.settings.get("web.jwt_secret_key") == secret
    monkeypatch.setattr(jwt_credentials, "atomic_bytes", write)
    assert await get_jwt_secret_key(app_context.settings) == secret


async def test_failed_db_commit_reuses_durable_file(app_context, monkeypatch):
    secret = "synthetic-legacy-commit-key"
    await legacy_key(app_context, secret)
    commit = app_context.storage.commit_settings
    monkeypatch.setattr(
        app_context.storage,
        "commit_settings",
        AsyncMock(side_effect=RuntimeError("commit failed")),
    )
    with pytest.raises(RuntimeError):
        await get_jwt_secret_key(app_context.settings)
    assert app_context.settings.get("web.jwt_secret_key") == secret
    assert key_path(app_context).exists()
    monkeypatch.setattr(app_context.storage, "commit_settings", commit)
    assert await get_jwt_secret_key(app_context.settings) == secret


async def test_existing_credential_never_silently_rotates(app_context, monkeypatch):
    await get_jwt_secret_key(app_context.settings)
    path = key_path(app_context)
    valid_bytes = path.read_bytes()

    # 1. protection error
    app_context.settings._jwt_signing_credential = None
    with monkeypatch.context() as fault:
        fault.setattr(
            jwt_credentials,
            "protect",
            lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("denied")),
        )
        with pytest.raises(ConfigurationError):
            await get_jwt_secret_key(app_context.settings)

    # 2. corrupt file
    app_context.settings._jwt_signing_credential = None
    path.write_text("{invalid")
    with pytest.raises(ConfigurationError):
        await get_jwt_secret_key(app_context.settings)

    # 3. missing file
    app_context.settings._jwt_signing_credential = None
    path.unlink()
    with pytest.raises(ConfigurationError):
        await get_jwt_secret_key(app_context.settings)
    assert not path.exists()

    # 4. conflict with legacy key
    path.write_bytes(valid_bytes)
    app_context.settings._jwt_signing_credential = None
    await legacy_key(app_context, "synthetic-mismatching-key")
    with pytest.raises(ConfigurationError):
        await get_jwt_secret_key(app_context.settings)


async def test_concurrent_first_use_has_one_persisted_key(app_context):
    values = await asyncio.gather(
        *(get_jwt_secret_key(app_context.settings) for _ in range(8))
    )
    assert len(set(values)) == 1
    assert key_path(app_context).read_text().strip() == values[0]


async def test_http_settings_keep_scope_boundaries(
    admin_auth_client, auth_client, app_context, real_bedrock_server
):
    await app_context.settings.set("custom.scope_audit", {"public": "global-field"})
    await app_context.settings.set(
        "plugin_settings.private_scope", {"own": "plugin-table-field"}
    )
    await app_context.server_service.update_setting(
        real_bedrock_server.server_name,
        "custom.scope_audit",
        {"public": "server-field"},
    )
    issued = await admin_auth_client.post(
        "/api/account/tokens",
        json={"name": "Settings reader", "permissions": ["settings:read"]},
    )
    assert issued.status_code == 201, issued.text
    response = await admin_auth_client.get(
        "/api/settings/get",
        headers={"Authorization": "Bearer " + issued.json()["token"]},
    )
    values = response.json()["settings"]
    assert (
        "jwt_secret_key" not in values["web"]
        and "jwt_key_initialized" not in values["web"]
    )
    assert "plugin_settings" not in values
    assert values["custom"]["scope_audit"]["public"] == "global-field"
    server = await auth_client.get(
        f"/api/server/{real_bedrock_server.server_name}/settings/get"
    )
    assert (
        server.json()["settings"]["custom"]["scope_audit"]["public"] == "server-field"
    )
    for key, value in [
        ("web.jwt_secret_key", "replacement"),
        ("web.jwt_key_initialized", False),
        ("web", {"jwt_secret_key": "replacement"}),
        ("plugin_settings.private_scope", {}),
        ("private_scope.own", "replacement"),
    ]:
        bad = await admin_auth_client.post(
            "/api/settings/set", json={"key": key, "value": value}
        )
        assert bad.status_code in (400, 403), (key, bad.text)
    await app_context.settings.set("web", {"host": "127.0.0.1"})
    assert app_context.settings.get("web.jwt_key_initialized") is True


async def test_plugin_settings_use_their_own_scope(
    auth_client, admin_auth_client, plugin_factory, app_context
):
    from tests.services.test_scoped_plugin_settings import SOURCE

    await plugin_factory("profiles", SOURCE)
    await app_context.server_service.register_or_update_server("one")
    path = "/api/plugins/profiles/settings"
    assert (
        await auth_client.get(path, params={"scope": "server", "server_name": "one"})
    ).status_code == 200
    assert (await auth_client.get(path)).status_code == 403
    assert (await auth_client.get(path, params={"scope": "global"})).status_code == 403
    issued = await admin_auth_client.post(
        "/api/account/tokens",
        json={"name": "Global profiles", "permissions": ["settings:read"]},
    )
    headers = {"Authorization": "Bearer " + issued.json()["token"]}
    assert (
        await admin_auth_client.get(path, params={"scope": "global"}, headers=headers)
    ).status_code == 200
    assert (await admin_auth_client.get(path, headers=headers)).status_code == 403


async def test_plugin_routes_reject_collisions_without_mounting(app_context, test_app):
    manager = app_context.plugin_manager
    original = list(test_app.routes)
    router = APIRouter()

    @router.get("/plugin-audit", operation_id="get_account")
    async def collision(user=Security(require_permissions, scopes=["account:read"])):
        return {}

    with pytest.raises(ValueError, match="operationId"):
        await manager._register_routers("collision", [router])
    assert list(test_app.routes) == original
    assert "collision" not in manager._router_owners
    another = APIRouter()

    @another.get("/api/server/{different}/status", operation_id="different_operation")
    async def same_binding(user=Security(require_permissions, scopes=["servers:read"])):
        return {}

    with pytest.raises(ValueError, match="Duplicate HTTP route"):
        await manager._register_routers("alias", [another])
    assert list(test_app.routes) == original


async def test_preview_is_not_a_mutation_step_up_exception(
    admin_auth_client, test_user, app_context
):
    from sqlalchemy import update

    from bedrock_server_manager.db.models import LoginSession

    account = (await admin_auth_client.get("/api/account")).json()
    async with app_context.storage.transaction() as db:
        await db.execute(
            update(LoginSession)
            .where(LoginSession.id == account["session_id"])
            .values(verified_at=0)
        )
    path = f"/api/access/users/{test_user.id}/servers"
    payload = {"mode": "assigned", "grants": []}
    assert (
        await admin_auth_client.post(path + "/preview", json=payload)
    ).status_code == 200
    assert (await admin_auth_client.put(path, json=payload)).status_code == 403


def test_tags_ids_and_contextual_metadata():
    schema = export_contract()
    declared = {t["name"] for t in schema["tags"]}
    ids = []
    for item in schema["paths"].values():
        for operation in item.values():
            assert set(operation["tags"]) <= declared
            ids.append(operation["operationId"])
    assert len(ids) == len(set(ids))
    assert (
        "recent-interactive-verification"
        in schema["paths"]["/api/account/tokens"]["post"]["x-bsm-access"][
            "additional_checks"
        ]
    )
    assert schema["paths"]["/api/plugins/{plugin_name}/settings"]["get"][
        "x-bsm-access"
    ]["credential_alternatives"]


async def test_server_scoped_plugin_tokens_cannot_cross_servers(
    admin_auth_client, app_context, plugin_factory
):
    from tests.services.test_scoped_plugin_settings import SOURCE

    await plugin_factory("profiles", SOURCE)
    for name in ("one", "two"):
        await app_context.server_service.register_or_update_server(name)
    identity = (await app_context.access_service.server_identities())["one"]
    issued = await admin_auth_client.post(
        "/api/account/tokens",
        json={
            "name": "One profile",
            "permissions": ["servers:read", "servers:configure"],
            "server_ids": [identity],
        },
    )
    assert issued.status_code == 201, issued.text
    headers = {"Authorization": "Bearer " + issued.json()["token"]}
    path = "/api/plugins/profiles/settings"
    for name, code in [("one", 200), ("two", 403)]:
        assert (
            await admin_auth_client.get(
                path, headers=headers, params={"scope": "server", "server_name": name}
            )
        ).status_code == code
        assert (
            await admin_auth_client.put(
                path,
                headers=headers,
                json={
                    "scope": "server",
                    "server_name": name,
                    "settings": {"a": 3, "b": True},
                },
            )
        ).status_code == code
    assert (await admin_auth_client.get(path, headers=headers)).status_code == 403


async def test_content_read_inventory_is_safe_and_does_not_grant_mutations(
    admin_auth_client, real_bedrock_server, monkeypatch
):
    from bedrock_server_manager.api.models.addon import (
        InstalledAddon,
        InstalledAddons,
        ListInstalledAddonsResponse,
    )
    from bedrock_server_manager.web.routers import addon

    private_path = "/synthetic/private/pack"
    monkeypatch.setattr(
        addon.addon_api,
        "list_installed_addons",
        AsyncMock(
            return_value=ListInstalledAddonsResponse(
                addons=InstalledAddons(
                    behavior_packs=[
                        InstalledAddon(
                            name="Pack",
                            uuid="pack-id",
                            version=[1, 0, 0],
                            status="ACTIVE",
                            path=private_path,
                            icon=private_path + "/pack_icon.png",
                        )
                    ]
                )
            )
        ),
    )
    issued = await admin_auth_client.post(
        "/api/account/tokens",
        json={"name": "Inventory", "permissions": ["addons:read"]},
    )
    assert issued.status_code == 201, issued.text
    headers = {"Authorization": "Bearer " + issued.json()["token"]}
    prefix = f"/api/server/{real_bedrock_server.server_name}"
    response = await admin_auth_client.get(prefix + "/addons", headers=headers)
    assert response.status_code == 200, response.text
    pack = response.json()["addons"]["behavior_packs"][0]
    assert pack["path"] is None and pack["icon"] == "pack_icon.png"
    assert private_path not in response.text
    assert (
        await admin_auth_client.post(
            prefix + "/addon/enable",
            headers=headers,
            json={"pack_uuid": "pack-id", "pack_type": "behavior"},
        )
    ).status_code == 403


async def test_core_content_routes_enforce_permissions(auth_client, admin_auth_client):
    assert (
        await auth_client.get("/api/content/worlds/sample.mcworld/download")
    ).status_code == 403
    issued = await admin_auth_client.post(
        "/api/account/tokens",
        json={"name": "Content files", "permissions": ["content:read"]},
    )
    headers = {"Authorization": "Bearer " + issued.json()["token"]}
    # content:read cannot upload or delete content
    response = await admin_auth_client.delete(
        "/api/content/worlds/sample.mcworld",
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_core_content_operation_ids_remain_stable():
    from bedrock_server_manager.web.routers.content import router as content_router

    assert [route.operation_id for route in content_router.routes] == [
        "upload_content_file",
        "download_content_file",
        "delete_content_file",
    ]


async def test_delete_server_snapshot_route(admin_auth_client, real_bedrock_server):
    server_name = real_bedrock_server.server_name
    backup_dir = Path(real_bedrock_server.backups._directory())
    backup_dir.mkdir(parents=True, exist_ok=True)
    archive = backup_dir / "20261101T120000Z_deadbeef.bsmbackup"
    archive.write_bytes(b"backup-data")

    response = await admin_auth_client.delete(
        f"/api/server/{server_name}/backups/{archive.name}"
    )
    assert response.status_code == 200, response.text
    assert not archive.exists()
    assert f"Deleted backup '{archive.name}'." in response.json()["message"]


async def test_unknown_plugin_scope_is_rejected_before_mount(app_context, test_app):
    original = list(test_app.routes)
    router = APIRouter()

    @router.get("/unknown-plugin-scope", operation_id="scope_audit_unknown")
    async def endpoint(user=Security(require_permissions, scopes=["missing:scope"])):
        return {}

    with pytest.raises(ValueError):
        await app_context.plugin_manager._register_routers("unknown-scope", [router])
    assert list(test_app.routes) == original
    assert "unknown-scope" not in app_context.plugin_manager._router_owners


@pytest.mark.parametrize("mixed", [False, True])
def test_legacy_role_forbidden_in_core_but_warns_for_plugin_routes(caplog, mixed):
    import logging

    from fastapi import Depends, FastAPI, Security

    from bedrock_server_manager.web.access_metadata import validate_core_access
    from bedrock_server_manager.web.access_policy import AccessPolicy
    from bedrock_server_manager.web.deps.auth import get_admin_user, require_permissions
    from bedrock_server_manager.web.openapi_tags import OPENAPI_TAGS
    from bedrock_server_manager.web.router_validation import validate_plugin_routes

    app = FastAPI()
    policy = AccessPolicy()

    dependencies = (
        [Security(require_permissions, scopes=["servers:read"])] if mixed else []
    )

    @app.get(
        "/legacy-core",
        operation_id="legacy_core_route",
        tags=[OPENAPI_TAGS[0]["name"]],
        dependencies=dependencies,
    )
    async def legacy_core(user=Depends(get_admin_user)):
        return {}

    with pytest.raises(ValueError, match="deprecated legacy role dependency"):
        validate_core_access(app, policy)

    plugin_app = FastAPI()
    router = APIRouter()

    @router.get(
        "/legacy-plugin",
        operation_id="legacy_plugin_route",
        dependencies=dependencies,
    )
    async def legacy_plugin(user=Depends(get_admin_user)):
        return {}

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        validate_plugin_routes(plugin_app.routes, [router], policy)

    assert any(
        "uses deprecated legacy role dependenc" in record.getMessage()
        for record in caplog.records
    )

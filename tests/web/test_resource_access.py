"""Credential and resource boundaries, including alternate transports and identity reuse."""

import hashlib
import time

import pytest
from fastapi import Security
from sqlalchemy import delete, select

from bedrock_server_manager.db.models import IntegrationToken, Server, User
from bedrock_server_manager.web.access_policy import Permission
from bedrock_server_manager.web.deps.auth import get_admin_user, require_permissions
from bedrock_server_manager.web.schemas import UserResponse


@pytest.fixture
async def access_servers(app_context):
    for name in ("alpha", "beta"):
        await app_context.server_service.register_or_update_server(
            name, status="STOPPED"
        )
    async with app_context.storage.transaction() as session:
        return dict(
            (await session.execute(select(Server.server_name, Server.access_id))).all()
        )


@pytest.fixture
def scoped_test_routes(test_app):
    @test_app.get("/_resource/{server_name}")
    async def read(
        server_name: str,
        user=Security(require_permissions, scopes=[Permission.SERVERS_READ]),
    ):
        return {"server": server_name}

    @test_app.post("/_resource/{server_name}")
    async def control(
        server_name: str,
        user=Security(require_permissions, scopes=[Permission.SERVERS_CONTROL]),
    ):
        return {"server": server_name}

    @test_app.get("/_legacy")
    async def legacy(user=Security(get_admin_user)):
        return {"username": user.username}


async def issue(client, permissions=None, **options):
    response = await client.post(
        "/api/account/tokens",
        json={
            "name": "Monitoring",
            "permissions": permissions
            or ["account:read", "servers:read", "tasks:read"],
            **options,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_integration_token_scope_ceiling_secret_storage_and_legacy_isolation(
    admin_auth_client, app_context, access_servers, scoped_test_routes
):
    issued = await issue(admin_auth_client, server_ids=[access_servers["alpha"]])
    bearer = {"Authorization": f"Bearer {issued['token']}"}
    assert (
        await admin_auth_client.get("/_resource/alpha", headers=bearer)
    ).status_code == 200
    assert (
        await admin_auth_client.get("/_resource/beta", headers=bearer)
    ).status_code == 403
    assert (
        await admin_auth_client.post("/_resource/alpha", headers=bearer)
    ).status_code == 403
    for path in ("/_legacy", "/api/account/tokens", "/api/users/list"):
        assert (await admin_auth_client.get(path, headers=bearer)).status_code == 403
    assert (
        await admin_auth_client.post("/auth/reauth", headers=bearer)
    ).status_code == 403
    account = (await admin_auth_client.get("/api/account", headers=bearer)).json()
    assert account["credential_id"] == issued["credential"]["id"]
    assert account["permissions"] == ["account:read", "servers:read", "tasks:read"]
    assert set(account["server_permissions"]) == {access_servers["alpha"]}
    listing = await admin_auth_client.get("/api/account/tokens")
    assert issued["token"] not in listing.text
    assert "digest" not in listing.text
    async with app_context.storage.transaction() as session:
        token = await session.get(IntegrationToken, issued["credential"]["id"])
        assert token.digest == hashlib.sha256(issued["token"].encode()).hexdigest()
        assert token.last_used_at is not None
    assert (
        await admin_auth_client.get(
            "/api/account", headers={"Authorization": f"Bearer {issued['token']}x"}
        )
    ).status_code == 401


async def test_revoke_expire_and_role_ceiling(auth_client, app_context):
    forbidden = await auth_client.post(
        "/api/account/tokens",
        json={"name": "Escalation", "permissions": ["users:manage"]},
    )
    assert forbidden.status_code in {403, 422}
    unknown = await auth_client.post(
        "/api/account/tokens",
        json={"name": "Unknown", "permissions": ["not:registered"]},
    )
    assert unknown.status_code == 422
    issued = await issue(auth_client)
    bearer = {"Authorization": f"Bearer {issued['token']}"}
    assert (
        await auth_client.delete(f"/api/account/tokens/{issued['credential']['id']}")
    ).status_code == 200
    assert (await auth_client.get("/api/account", headers=bearer)).status_code == 401
    expired = await issue(auth_client)
    async with app_context.storage.transaction() as session:
        record = await session.get(IntegrationToken, expired["credential"]["id"])
        record.expires_at = int(time.time()) - 1
    assert (
        await auth_client.get(
            "/api/account", headers={"Authorization": f"Bearer {expired['token']}"}
        )
    ).status_code == 401


async def test_assignments_filter_resources_and_do_not_elevate_roles(
    admin_auth_client, auth_client, test_user, access_servers, scoped_test_routes
):
    path = f"/api/access/users/{test_user.id}/servers"
    before = (await auth_client.get("/api/account")).json()["policy_revision"]
    response = await admin_auth_client.put(
        path,
        json={
            "mode": "assigned",
            "grants": [
                {
                    "server_id": access_servers["alpha"],
                    "permissions": ["servers:read", "servers:control"],
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert (await auth_client.get("/_resource/alpha")).status_code == 200
    assert (await auth_client.get("/_resource/beta")).status_code == 403
    assert (await auth_client.post("/_resource/alpha")).status_code == 403
    visible = (await auth_client.get("/api/access/servers")).json()
    assert [server["name"] for server in visible] == ["alpha"]
    account = (await auth_client.get("/api/account")).json()
    assert account["policy_revision"] != before
    assert account["server_access"] == "assigned"
    assert (
        "servers:control" not in account["server_permissions"][access_servers["alpha"]]
    )
    assert (
        await auth_client.put(path, json={"mode": "all", "grants": []})
    ).status_code == 403


async def test_server_deletion_never_transfers_grants_to_recreated_name(
    admin_auth_client,
    auth_client,
    test_user,
    app_context,
    access_servers,
    scoped_test_routes,
):
    path = f"/api/access/users/{test_user.id}/servers"
    assert (
        await admin_auth_client.put(
            path,
            json={
                "mode": "assigned",
                "grants": [
                    {
                        "server_id": access_servers["alpha"],
                        "permissions": ["servers:read"],
                    }
                ],
            },
        )
    ).status_code == 200
    async with app_context.storage.transaction() as session:
        await session.execute(delete(Server).where(Server.server_name == "alpha"))
        session.add(Server(server_name="alpha"))
    assert (await auth_client.get("/_resource/alpha")).status_code == 403


async def test_user_identity_reuse_does_not_transfer_token_or_new_session(
    auth_client, test_user, app_context
):
    issued = await issue(auth_client)
    async with app_context.storage.transaction() as session:
        await session.execute(delete(User).where(User.id == test_user.id))
        session.add(
            User(
                id=test_user.id,
                username=test_user.username,
                role="admin",
                is_active=True,
                hashed_password=test_user.hashed_password,
            )
        )
    assert (
        await auth_client.get(
            "/api/account", headers={"Authorization": f"Bearer {issued['token']}"}
        )
    ).status_code == 401
    assert (await auth_client.get("/api/account")).status_code == 401


async def test_task_reads_do_not_cross_integration_credentials(
    admin_auth_client, app_context
):
    first = await issue(admin_auth_client)
    second = await issue(admin_auth_client)
    from bedrock_server_manager.web.authorization import current_authorization

    user = UserResponse(id=1, username="adminuser", role="admin", is_active=True)
    # Use the authenticated owner returned by the API, independent of fixture IDs.
    user = UserResponse.model_validate(
        {
            key: value
            for key, value in (await admin_auth_client.get("/api/account"))
            .json()
            .items()
            if key in UserResponse.model_fields
        }
    )
    authorization = await app_context.access_service.snapshot(
        user, first["credential"]["id"]
    )

    async def completed():
        return {"status": "success"}

    ticket = current_authorization.set(authorization)
    try:
        identifier = await app_context.task_manager.run_task(
            completed, username=user.username
        )
    finally:
        current_authorization.reset(ticket)
    assert (
        await admin_auth_client.get(
            f"/api/tasks/status/{identifier}",
            headers={"Authorization": f"Bearer {first['token']}"},
        )
    ).status_code == 200
    assert (
        await admin_auth_client.get(
            f"/api/tasks/status/{identifier}",
            headers={"Authorization": f"Bearer {second['token']}"},
        )
    ).status_code == 404


async def test_websocket_token_topics_and_revocation(
    admin_auth_client, websocket_client, app_context, access_servers
):
    import json

    from websockets.exceptions import ConnectionClosed

    issued = await issue(
        admin_auth_client,
        permissions=["account:read", "servers:read"],
        server_ids=[access_servers["alpha"]],
    )
    async with websocket_client() as socket:
        await socket.send(
            json.dumps({"action": "authenticate", "token": issued["token"]})
        )
        assert json.loads(await socket.recv())["status"] == "success"
        for topic, expected in (
            ("resource-monitor:alpha", "success"),
            ("resource-monitor:beta", "error"),
            ("app_log", "error"),
            ("*", "error"),
            ("plugin:unknown", "error"),
        ):
            await socket.send(json.dumps({"action": "subscribe", "topic": topic}))
            assert json.loads(await socket.recv())["status"] == expected
        await admin_auth_client.delete(
            f"/api/account/tokens/{issued['credential']['id']}"
        )
        assert json.loads(await socket.recv())["type"] == "access_changed"
        with pytest.raises(ConnectionClosed):
            await socket.recv()


async def test_policy_revision_changes_when_plugin_grants_change(
    auth_client, app_context
):
    before = (await auth_client.get("/api/account")).json()
    policy = app_context.plugin_manager.access_policy
    policy.register("access_test", "plugin:access_test:read", "Read plugin", ["user"])
    after = (await auth_client.get("/api/account")).json()
    assert before["policy_revision"] != after["policy_revision"]
    assert "plugin:access_test:read" in after["permissions"]
    policy.remove_owner("access_test")
    assert (
        "plugin:access_test:read"
        not in (await auth_client.get("/api/account")).json()["permissions"]
    )


async def test_token_tracks_role_and_assignment_changes(
    admin_auth_client, app_context, access_servers, scoped_test_routes
):
    issued = await issue(
        admin_auth_client,
        permissions=["account:read", "servers:read", "servers:control", "backups:keys"],
    )
    bearer = {"Authorization": f"Bearer {issued['token']}"}
    assert (
        await admin_auth_client.post("/_resource/alpha", headers=bearer)
    ).status_code == 200
    owner = (await admin_auth_client.get("/api/account")).json()
    async with app_context.storage.transaction() as session:
        record = await session.get(User, owner["id"])
        record.role = "user"
    assert (
        await admin_auth_client.post("/_resource/alpha", headers=bearer)
    ).status_code == 403
    assert (
        await admin_auth_client.get("/_resource/alpha", headers=bearer)
    ).status_code == 200


async def test_server_limited_token_cannot_read_global_backup_keys(
    admin_auth_client, access_servers
):
    issued = await issue(
        admin_auth_client,
        permissions=["account:read", "servers:read", "backups:keys"],
        server_ids=[access_servers["alpha"]],
    )
    bearer = {"Authorization": f"Bearer {issued['token']}"}
    account = (await admin_auth_client.get("/api/account", headers=bearer)).json()
    assert "backups:keys" not in account["permissions"]
    # Actual global routes remain guarded even though the owning account is admin.
    response = await admin_auth_client.get("/api/backups/keys", headers=bearer)
    assert response.status_code == 403


async def test_task_results_follow_current_server_grants(
    admin_auth_client, auth_client, test_user, app_context, access_servers
):
    from bedrock_server_manager.web.authorization import (
        current_authorization,
        operation_permissions,
    )

    owner = UserResponse.model_validate(
        {
            key: value
            for key, value in (await auth_client.get("/api/account")).json().items()
            if key in UserResponse.model_fields
        }
    )
    authorization = await app_context.access_service.snapshot(owner)

    async def completed(**kwargs):
        return {"status": "success"}

    ticket = current_authorization.set(authorization)
    permissions = operation_permissions.set(frozenset({"servers:read"}))
    try:
        task_id = await app_context.task_manager.run_task(
            completed,
            username=owner.username,
            server_name="alpha",
            app_context=app_context,
        )
    finally:
        current_authorization.reset(ticket)
        operation_permissions.reset(permissions)
    assert (
        app_context.task_manager.tasks[task_id].access_server_id
        == access_servers["alpha"]
    )
    path = f"/api/access/users/{test_user.id}/servers"
    assert (
        await admin_auth_client.put(
            path,
            json={
                "mode": "assigned",
                "grants": [
                    {
                        "server_id": access_servers["alpha"],
                        "permissions": ["servers:read"],
                    }
                ],
            },
        )
    ).status_code == 200
    assert (await auth_client.get(f"/api/tasks/status/{task_id}")).status_code == 200
    assert (
        await admin_auth_client.put(path, json={"mode": "assigned", "grants": []})
    ).status_code == 200
    assert (await auth_client.get(f"/api/tasks/status/{task_id}")).status_code == 404

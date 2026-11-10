"""Regression coverage for scope discovery, credential lifecycle and execution boundaries."""

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select, update

from bedrock_server_manager.db.models import (
    AccountSecurity,
    AccountServerAccess,
    AuthSecurityEvent,
    IntegrationToken,
    LoginSession,
    Server,
    ServerAccessGrant,
    TrustedDevice,
)
from bedrock_server_manager.services.task_service import TaskManager
from bedrock_server_manager.web.authorization import (
    current_authorization,
    operation_permissions,
)
from bedrock_server_manager.web.contract import export_contract
from bedrock_server_manager.web.log_streamer import LogHistoryPage
from bedrock_server_manager.web.websocket_manager import ConnectionManager


async def test_bearer_login_and_failures_are_not_cacheable(unauth_client, test_user):
    for password, status in (("testpassword", 200), ("incorrect", 401)):
        response = await unauth_client.post(
            "/auth/token", data={"username": test_user.username, "password": password}
        )
        assert response.status_code == status, response.text
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Pragma"] == "no-cache"
    response = await unauth_client.get("/api/setup/status")
    assert response.headers["Cache-Control"] == "no-store"


def test_conditional_access_contract_has_actual_capabilities():
    document = export_contract()
    for path, method, permission, local in (
        ("/api/health", "get", "health:read", "LocalReadiness"),
        ("/api/runtime/shutdown", "post", "runtime:shutdown", "APIKeyHeader"),
    ):
        operation = document["paths"][path][method]
        alternatives = operation["x-bsm-access"]["credential_alternatives"]
        assert any(item["permissions"] == [permission] for item in alternatives)
        assert {"OAuth2PasswordBearer": [permission]} in operation["security"]
        assert {local: []} in operation["security"]
    operation = document["paths"]["/api/logs/history"]["get"]
    assert {"OAuth2PasswordBearer": ["application:logs"]} in operation["security"]
    assert {"OAuth2PasswordBearer": ["servers:logs"]} in operation["security"]


async def issue(client, permissions, **extra):
    response = await client.post(
        "/api/account/tokens",
        json={"name": "Audit integration", "permissions": permissions, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_application_log_http_and_socket_scopes_agree(
    admin_auth_client, app_context, monkeypatch
):
    token = await issue(admin_auth_client, ["application:logs"])
    headers = {"Authorization": f"Bearer {token['token']}"}
    read = AsyncMock(
        return_value=LogHistoryPage(
            data="safe", start=0, end=4, file_id="file", has_more=False
        )
    )
    monkeypatch.setattr(app_context.log_streamer, "read_history", read)
    response = await admin_auth_client.get(
        "/api/logs/history?topic=app_log", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"] == "safe"
    assert (
        await admin_auth_client.get(
            "/api/logs/history?topic=server_log:private", headers=headers
        )
    ).status_code == 403
    _, authorization = await app_context.access_service.authenticate(token["token"])
    assert await app_context.access_service.topic_allowed(authorization, "app_log")
    assert not await app_context.access_service.topic_allowed(
        authorization, "server_log:private"
    )
    read.assert_awaited_once()


async def test_mfa_key_protects_new_and_existing_paths(app_context, monkeypatch):
    from bedrock_server_manager.backups import credentials

    actual = credentials.protect
    calls = []

    def protect(path, *, directory=False):
        calls.append((path.name, directory))
        actual(path, directory=directory)

    monkeypatch.setattr(credentials, "protect", protect)
    cipher = app_context.session_service._cipher(create=True)
    path = Path(app_context.config_dir) / "credentials" / "mfa.key"
    original = path.read_bytes()
    if os.name != "nt":
        path.chmod(0o644)
        path.parent.chmod(0o755)
    assert (
        app_context.session_service._cipher().decrypt(cipher.encrypt(b"secret"))
        == b"secret"
    )
    assert path.read_bytes() == original
    assert ("mfa.key", False) in calls and ("credentials", True) in calls
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700


async def test_token_history_pagination_retention_and_nonexpiring_credentials(
    auth_client, app_context
):
    tokens = [
        await issue(auth_client, ["account:read"], expires_in_days=None)
        for _ in range(3)
    ]
    ids = {item["credential"]["id"] for item in tokens}
    first = await auth_client.get("/api/account/tokens?limit=2")
    second = await auth_client.get("/api/account/tokens?limit=2&offset=2")
    assert len(first.json()) == 2 and len(second.json()) == 1
    assert {item["id"] for item in first.json() + second.json()} == ids
    assert not (
        {item["id"] for item in first.json()} & {item["id"] for item in second.json()}
    )
    assert (await auth_client.get("/api/account/tokens?limit=501")).status_code == 422
    now = int(time.time())
    async with app_context.storage.transaction() as session:
        await session.execute(
            update(IntegrationToken)
            .where(IntegrationToken.id == tokens[0]["credential"]["id"])
            .values(revoked_at=now - 91 * 86400)
        )
        await session.execute(
            update(IntegrationToken)
            .where(IntegrationToken.id == tokens[1]["credential"]["id"])
            .values(expires_at=now - 91 * 86400)
        )
    await app_context.session_service.cleanup()
    response = await auth_client.get("/api/account/tokens")
    assert [item["id"] for item in response.json()] == [tokens[2]["credential"]["id"]]
    assert (
        await auth_client.get(
            "/api/account", headers={"Authorization": f"Bearer {tokens[2]['token']}"}
        )
    ).status_code == 200


async def test_account_deletion_removes_security_material_but_keeps_history(
    auth_client, test_user, app_context
):
    token = await issue(auth_client, ["account:read"])
    async with app_context.storage.transaction() as session:
        from bedrock_server_manager.db.models import User

        user = await session.get(User, test_user.id)
        owner = user.access_id
        session.add(
            AccountSecurity(
                owner_id=owner,
                totp_secret="encrypted",
                recovery_hashes=["digest"],
                version=0,
                last_counter=-1,
            )
        )
        session.add(AccountServerAccess(owner_id=owner, assigned_only=True))
        session.add(
            ServerAccessGrant(
                owner_id=owner, server_id="a" * 32, permissions=["servers:read"]
            )
        )
        session.add(
            TrustedDevice(
                id="b" * 32,
                owner_id=owner,
                token_digest="c" * 64,
                auth_revision=0,
                name="device",
                user_agent="",
                ip_address="",
                created_at=1,
                last_used_at=1,
                expires_at=2000000000,
            )
        )
        await session.flush()
        await app_context.storage.user_repo.delete_user(session, user)
    async with app_context.storage.transaction() as session:
        for model in (
            AccountSecurity,
            AccountServerAccess,
            ServerAccessGrant,
            TrustedDevice,
            IntegrationToken,
            LoginSession,
        ):
            assert not list(
                await session.scalars(select(model).where(model.owner_id == owner))
            )
        assert list(
            await session.scalars(
                select(AuthSecurityEvent).where(AuthSecurityEvent.owner_id == owner)
            )
        )
    assert (await app_context.access_service.authenticate(token["token"])) is None


async def test_access_previews_explain_role_and_resource_ceilings(
    admin_auth_client, auth_client, test_user, app_context
):
    await app_context.server_service.register_or_update_server(
        "alpha", status="STOPPED"
    )
    async with app_context.storage.transaction() as session:
        identity = await session.scalar(
            select(Server.access_id).where(Server.server_name == "alpha")
        )
    path = f"/api/access/users/{test_user.id}/servers"
    payload = {
        "mode": "assigned",
        "grants": [
            {
                "server_id": identity,
                "permissions": ["servers:read", "servers:lifecycle"],
            }
        ],
    }
    preview = await admin_auth_client.post(path + "/preview", json=payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["server_permissions"] == {identity: ["servers:read"]}
    assert preview.json()["unavailable_permissions"] == ["servers:lifecycle"]
    assert (await admin_auth_client.get(path)).json()["mode"] == "all"
    assert (await auth_client.post(path + "/preview", json=payload)).status_code == 403
    response = await admin_auth_client.post(
        "/api/account/tokens/preview",
        json={
            "name": "Preview",
            "permissions": ["servers:read", "settings:read", "users:manage"],
            "server_ids": [identity],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["effective_permissions"] == ["servers:read"]
    assert response.json()["unavailable_permissions"] == [
        "settings:read",
        "users:manage",
    ]
    assert (await admin_auth_client.get("/api/account/tokens")).json() == []


async def test_outbound_delivery_authorizes_once_under_lock_and_encodes_filtered_data(
    test_user,
):
    from bedrock_server_manager.web.authorization import Authorization

    authorization = Authorization(
        user_id=test_user.id,
        username=test_user.username,
        owner_id="owner",
        permissions=frozenset(),
        servers={},
        grants=None,
    )
    resolver = AsyncMock(return_value=authorization)
    filtering = AsyncMock(return_value={"redacted": True})
    manager = ConnectionManager(
        authorization_resolver=resolver, message_filter=filtering
    )
    socket = MagicMock(send_text=AsyncMock())
    identifier = await manager.connect(socket, test_user, authorization=authorization)
    client = manager.active_connections[identifier]
    await client.send_lock.acquire()
    pending = asyncio.create_task(
        manager.send_to_client({"secret": "not delivered"}, identifier)
    )
    await asyncio.sleep(0)
    resolver.assert_not_awaited()
    client.send_lock.release()
    result = await pending
    assert result.sent == 1
    resolver.assert_awaited_once()
    assert json.loads(socket.send_text.call_args.args[0]) == {"redacted": True}
    # A subsequent committed revocation is still checked for every delivery.
    resolver.return_value = None
    result = await manager.send_to_client({"secret": "not delivered"}, identifier)
    assert result.sent == 0 and identifier not in manager.active_connections


async def test_queued_http_work_rechecks_credential_at_start(auth_client, app_context):
    from tests.services.test_task_service import finish_task

    for revoke in (False, True):
        issued = await issue(auth_client, ["account:read"])
        user, authorization = await app_context.access_service.authenticate(
            issued["token"]
        )
        manager = TaskManager(None, max_workers=1)
        ran = []
        await manager._execution_slots.acquire()

        async def work(*, app_context, r=ran):
            r.append(True)
            return {"done": True}

        ticket = current_authorization.set(authorization)
        permission_ticket = operation_permissions.set(frozenset({"account:read"}))
        try:
            identifier = await manager.run_task(
                work, username=user.username, app_context=app_context
            )
        finally:
            current_authorization.reset(ticket)
            operation_permissions.reset(permission_ticket)
        await asyncio.sleep(0)
        if revoke:
            await app_context.access_service.revoke_token(
                user, user.id, issued["credential"]["id"]
            )
        manager._execution_slots.release()

        result = await finish_task(manager, identifier)
        assert result.status == ("cancelled" if revoke else "completed")
        assert bool(ran) is not revoke
        await manager.shutdown()


async def test_backup_recovery_secret_requires_recent_interactive_auth(
    admin_auth_client, app_context, monkeypatch
):
    account = (await admin_auth_client.get("/api/account")).json()
    async with app_context.storage.transaction() as session:
        await session.execute(
            update(LoginSession)
            .where(LoginSession.id == account["session_id"])
            .values(verified_at=0)
        )
    from bedrock_server_manager.web.routers import backup_restore

    export = AsyncMock(return_value="private-key")
    monkeypatch.setattr(
        backup_restore.backup_transfer, "get_backup_emergency_kit", export
    )
    response = await admin_auth_client.get("/api/backups/keys/example/emergency-kit")
    assert response.status_code == 403
    assert response.headers["X-BSM-Recent-Auth"] == "required"
    export.assert_not_awaited()


async def test_queued_work_cannot_outlive_assignment_resource_or_session(
    auth_client, admin_auth_client, test_user, app_context
):
    from types import SimpleNamespace
    from uuid import uuid4

    from bedrock_server_manager.web.schemas import UserResponse
    from tests.services.test_task_service import finish_task

    await app_context.server_service.register_or_update_server(
        "alpha", status="STOPPED"
    )
    account = (await auth_client.get("/api/account")).json()
    user = UserResponse.model_validate(test_user, from_attributes=True)

    for change in ("assignment", "server_identity", "session"):
        if change != "assignment":
            await admin_auth_client.put(
                f"/api/access/users/{user.id}/servers",
                json={"mode": "all", "grants": []},
            )
        authorization = await app_context.access_service.snapshot(
            user, session_id=account["session_id"]
        )
        manager = TaskManager(None, max_workers=1)
        await manager._execution_slots.acquire()
        ran = []

        async def work(*, request, app_context, r=ran):
            r.append(request.server_name)

        ticket = current_authorization.set(authorization)
        scopes = operation_permissions.set(frozenset({"servers:read"}))
        try:
            identifier = await manager.run_task(
                work,
                username=user.username,
                request=SimpleNamespace(server_name="alpha"),
                app_context=app_context,
            )
        finally:
            current_authorization.reset(ticket)
            operation_permissions.reset(scopes)
        await asyncio.sleep(0)
        if change == "assignment":
            response = await admin_auth_client.put(
                f"/api/access/users/{user.id}/servers",
                json={"mode": "assigned", "grants": []},
            )
            assert response.status_code == 200, response.text
        elif change == "server_identity":
            async with app_context.storage.transaction() as session:
                await session.execute(
                    update(Server)
                    .where(Server.server_name == "alpha")
                    .values(access_id=uuid4().hex)
                )
        else:
            await app_context.session_service.revoke(
                authorization.owner_id, identifier=authorization.session_id
            )
        manager._execution_slots.release()
        result = await finish_task(manager, identifier)
        assert result.status == "cancelled" and ran == []
        await manager.shutdown()


async def test_revocation_does_not_interrupt_work_already_running(
    auth_client, app_context
):
    from tests.services.test_task_service import finish_task

    issued = await issue(auth_client, ["account:read"])
    user, authorization = await app_context.access_service.authenticate(issued["token"])
    manager = TaskManager(None)
    started, release = asyncio.Event(), asyncio.Event()

    async def work(*, app_context):
        started.set()
        await release.wait()
        return {"committed": True}

    ticket = current_authorization.set(authorization)
    scopes = operation_permissions.set(frozenset({"account:read"}))
    try:
        identifier = await manager.run_task(
            work, username=user.username, app_context=app_context
        )
    finally:
        current_authorization.reset(ticket)
        operation_permissions.reset(scopes)
    async with asyncio.timeout(5):
        await started.wait()
    await app_context.access_service.revoke_token(
        user, user.id, issued["credential"]["id"]
    )
    release.set()
    result = await finish_task(manager, identifier)
    assert result.status == "completed" and result.result == {"committed": True}
    await manager.shutdown()


async def test_maintenance_removes_historical_orphaned_secrets(app_context):
    async with app_context.storage.transaction() as session:
        session.add(
            AccountSecurity(
                owner_id="missing",
                totp_secret="old-secret",
                recovery_hashes=["old-digest"],
                last_counter=-1,
                version=0,
            )
        )
        session.add(
            ServerAccessGrant(
                owner_id="missing", server_id="a" * 32, permissions=["servers:read"]
            )
        )
        session.add(
            AuthSecurityEvent(
                id="historical",
                owner_id="missing",
                action="account_deleted",
                timestamp=int(time.time()),
                details={},
            )
        )
    await app_context.session_service.cleanup()
    async with app_context.storage.transaction() as session:
        assert await session.get(AccountSecurity, "missing") is None
        assert await session.get(ServerAccessGrant, ("missing", "a" * 32)) is None
        assert await session.get(AuthSecurityEvent, "historical") is not None


async def test_emergency_export_explicit_integration_capability_is_preserved(
    admin_auth_client, app_context, monkeypatch
):
    from bedrock_server_manager.web.routers import backup_restore

    issued = await issue(admin_auth_client, ["backups:keys"])
    export = AsyncMock(return_value="explicit-recovery-key")
    monkeypatch.setattr(
        backup_restore.backup_transfer, "get_backup_emergency_kit", export
    )
    response = await admin_auth_client.get(
        "/api/backups/keys/example/emergency-kit",
        headers={"Authorization": f"Bearer {issued['token']}"},
    )
    assert response.status_code == 200 and response.text == "explicit-recovery-key"
    assert response.headers["Cache-Control"] == "no-store"

"""Authorization migration invariants and schema agreement."""

import pytest
from fastapi import APIRouter, FastAPI, Security
from httpx2 import ASGITransport, AsyncClient

from bedrock_server_manager.web.access_metadata import configure_access_schema
from bedrock_server_manager.web.access_policy import AccessPolicy, Permission
from bedrock_server_manager.web.auth import create_access_token
from bedrock_server_manager.web.contract import export_contract
from bedrock_server_manager.web.deps.auth import get_current_user, require_permissions
from bedrock_server_manager.web.schemas import UserResponse


def test_core_schema_is_classified_and_scopes_match():
    schema = export_contract()
    policy = AccessPolicy()
    for item in schema["paths"].values():
        for operation in item.values():
            access = operation["x-bsm-access"]
            assert access["classification"] != "unknown"
            policy.validate(access["required_permissions"])
            if access["classification"] == "permission":
                assert access["required_permissions"]
                assert access["allowed_roles"] == [
                    role
                    for role in ("user", "moderator", "admin")
                    if set(access["required_permissions"]) <= policy.resolve(role)
                ]
                assert {
                    "OAuth2PasswordBearer": access["required_permissions"]
                } in operation["security"]
                assert {"APIKeyCookie": []} in operation["security"]
    assert (
        "permissions"
        not in schema["components"]["schemas"]["UserResponse"]["properties"]
    )
    assert (
        "permissions"
        in schema["components"]["schemas"]["CurrentAccountResponse"]["properties"]
    )


@pytest.mark.parametrize("role", ["user", "moderator", "admin"])
@pytest.mark.parametrize(
    "scopes",
    [
        [Permission.SERVERS_READ],
        [Permission.SERVERS_CONTROL],
        [Permission.SERVERS_READ, Permission.USERS_MANAGE],
        ["unknown:permission"],
    ],
)
async def test_permissions_require_all_and_fail_closed(role, scopes):
    app = FastAPI()
    app.state.access_policy = AccessPolicy()
    app.dependency_overrides[get_current_user] = lambda: UserResponse(
        id=1, username="operator", role=role, is_active=True
    )

    @app.get("/")
    async def endpoint(user=Security(require_permissions, scopes=scopes)):
        return user.username

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
    assert response.status_code == (
        200 if set(scopes) <= app.state.access_policy.resolve(role) else 403
    )


def test_nested_dependencies_and_plugin_invalidation():
    app = FastAPI()
    policy = AccessPolicy(lambda: setattr(app, "openapi_schema", None))
    router = APIRouter(
        dependencies=[Security(require_permissions, scopes=[Permission.SERVERS_READ])]
    )

    @router.get("/nested")
    async def nested(
        user=Security(require_permissions, scopes=[Permission.SERVERS_CONTROL])
    ):
        pass

    @router.get("/unknown")
    async def unknown():
        pass

    app.include_router(router)
    configure_access_schema(app, policy)
    schema = app.openapi()
    assert schema["paths"]["/nested"]["get"]["x-bsm-access"][
        "required_permissions"
    ] == ["servers:control", "servers:read"]
    policy.register("example", "plugin:example:jobs:run", "Run jobs", ["user"])
    assert app.openapi_schema is None
    assert "plugin:example:jobs:run" in policy.resolve("user")
    assert "plugin:example:jobs:run" not in policy.resolve("admin")
    with pytest.raises(ValueError):
        policy.register("example", "plugin:example:jobs:run", "Collision", ["admin"])
    with pytest.raises(ValueError):
        policy.register("other", "plugin:example:jobs:run", "Wrong owner", ["admin"])
    policy.remove_owner("example")
    assert "plugin:example:jobs:run" not in policy.resolve("user")
    standalone = FastAPI()

    @standalone.get("/unknown")
    async def no_policy():
        pass

    configure_access_schema(standalone, policy)
    assert (
        standalone.openapi()["paths"]["/unknown"]["get"]["x-bsm-access"][
            "classification"
        ]
        == "unknown"
    )


@pytest.mark.parametrize(
    "header", ["Basic abc", "Bearer", "Bearer bad", "Bearer one two", ""]
)
async def test_explicit_invalid_header_never_uses_cookie(auth_client, header):
    response = await auth_client.get("/api/account", headers={"Authorization": header})
    assert response.status_code == 401


async def test_bearer_wins_over_cookie(
    auth_client, app_context, test_admin_user, test_user
):
    token = await create_access_token(app_context, {"sub": test_admin_user.username})
    response = await auth_client.get(
        "/api/account", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == test_admin_user.username
    permissions = await auth_client.get("/api/account/permissions")
    account = await auth_client.get("/api/account")
    assert account.json()["username"] == test_user.username
    assert (
        account.json()["permissions"]
        == permissions.json()
        == sorted(AccessPolicy().resolve("user"))
    )


async def test_swagger_transport_and_ingress(unauth_client):
    response = await unauth_client.get("/docs")
    assert response.status_code == 200
    assert "credentials: 'omit'" in response.text
    assert 'request.credentials = "omit"' in response.text
    assert '"persistAuthorization": false' in response.text


# Static role baseline captured before route migration. Contextual restrictions
# are tested separately; these are only the dependency-level role grants.
ROLE_BASELINE = {
    "reauthenticate": ["user", "moderator", "admin"],
    "logout": ["user", "moderator", "admin"],
    "list_application_events": ["admin"],
    "get_event_activity": ["admin"],
    "get_account": ["user", "moderator", "admin"],
    "update_account_theme": ["user", "moderator", "admin"],
    "update_account_profile": ["user", "moderator", "admin"],
    "change_password": ["user", "moderator", "admin"],
    "get_web_runtime": ["admin"],
    "get_task_status": ["user", "moderator", "admin"],
    "list_tasks": ["user", "moderator", "admin"],
    "get_application_metrics": ["user", "moderator", "admin"],
    "generate_registration_token": ["admin"],
    "list_audit_logs": ["admin"],
    "list_schedules": ["admin"],
    "save_schedule": ["admin"],
    "delete_schedule": ["admin"],
    "control_schedule": ["admin"],
    "get_settings": ["admin"],
    "set_setting": ["admin"],
    "reload_settings": ["admin"],
    "list_available_worlds": ["moderator", "admin"],
    "install_world": ["admin"],
    "export_world": ["admin"],
    "reset_world": ["admin"],
    "scan_players": ["moderator", "admin"],
    "list_players": ["moderator", "admin"],
    "add_players": ["moderator", "admin"],
    "add_allowlist_players": ["moderator", "admin"],
    "get_allowlist": ["moderator", "admin"],
    "remove_allowlist_players": ["moderator", "admin"],
    "list_available_addons": ["moderator", "admin"],
    "list_server_addons": ["admin"],
    "enable_addon": ["admin"],
    "disable_addon": ["admin"],
    "update_addon_subpack": ["admin"],
    "uninstall_addon": ["admin"],
    "reorder_addons": ["admin"],
    "install_addon": ["admin"],
    "set_permissions": ["moderator", "admin"],
    "get_permissions": ["moderator", "admin"],
    "get_log_history": ["moderator", "admin"],
    "get_server_summary": ["moderator", "admin"],
    "start_server": ["moderator", "admin"],
    "stop_server": ["moderator", "admin"],
    "restart_server": ["moderator", "admin"],
    "send_command": ["moderator", "admin"],
    "update_server": ["admin"],
    "delete_server": ["admin"],
    "get_server_status": ["user", "moderator", "admin"],
    "validate_server": ["user", "moderator", "admin"],
    "get_server_process_info": ["user", "moderator", "admin"],
    "list_servers": ["user", "moderator", "admin"],
    "get_application_diagnostics": ["admin"],
    "get_diagnostic_activity": ["admin"],
    "get_diagnostic_history": ["admin"],
    "get_diagnostic_report": ["admin"],
    "get_diagnostic_runs": ["admin"],
    "get_diagnostic_trace": ["admin"],
    "compare_diagnostic_snapshots": ["admin"],
    "get_subsystem_diagnostics": ["admin"],
    "list_users": ["moderator", "admin"],
    "delete_user": ["admin"],
    "disable_user": ["admin"],
    "enable_user": ["admin"],
    "update_user_role": ["admin"],
    "get_server_bans": ["admin"],
    "add_server_ban": ["admin"],
    "remove_server_ban": ["admin"],
    "list_downloads": ["moderator", "admin"],
    "prune_downloads": ["admin"],
    "install_server": ["admin"],
    "get_server_settings": ["user", "moderator", "admin"],
    "set_server_setting": ["admin"],
    "get_plugin_pages": ["user", "moderator", "admin"],
    "list_plugins": ["admin"],
    "trigger_plugin_event": ["admin"],
    "set_plugin_status": ["admin"],
    "reload_plugin": ["admin"],
    "reload_plugins": ["admin"],
    "get_plugin_settings": ["admin"],
    "update_plugin_settings": ["admin"],
    "set_properties": ["moderator", "admin"],
    "get_properties": ["moderator", "admin"],
    "get_raw_properties": ["moderator", "admin"],
    "prune_backups": ["moderator", "admin"],
    "list_server_backups": ["moderator", "admin"],
    "create_backup": ["moderator", "admin"],
    "restore_backup": ["moderator", "admin"],
    "list_server_snapshots": ["moderator", "admin"],
    "create_server_snapshot": ["moderator", "admin"],
    "inspect_server_snapshot": ["moderator", "admin"],
    "plan_snapshot_restore": ["moderator", "admin"],
    "restore_server_snapshot": ["moderator", "admin"],
    "download_server_snapshot": ["moderator", "admin"],
    "import_server_snapshot": ["moderator", "admin"],
    "export_decrypted_snapshot": ["admin"],
    "list_backup_keys": ["admin"],
    "rotate_backup_key": ["admin"],
    "download_backup_emergency_kit": ["admin"],
    "get_restore_recovery": ["moderator", "admin"],
    "recover_server_backup": ["moderator", "admin"],
    "get_backup_health": ["moderator", "admin"],
    "manage_server_snapshot": ["moderator", "admin"],
    "prepare_backup_copy": ["admin"],
    "dry_run_server_restore": ["moderator", "admin"],
    "cleanup_backup_destination": ["admin"],
    "download_backup_recovery_report": ["moderator", "admin"],
}


def test_migration_preserves_existing_role_grants():
    schema = export_contract()
    operations = {
        operation["operationId"]: operation
        for item in schema["paths"].values()
        for operation in item.values()
    }
    for identifier, roles in ROLE_BASELINE.items():
        assert (
            operations[identifier]["x-bsm-access"]["allowed_roles"] == roles
        ), identifier


async def test_plugin_permission_lifecycle(app_context, test_app, plugin_factory):
    schema = test_app.openapi()
    plugin = await plugin_factory(
        "permission_example",
        """
from bedrock_server_manager.plugins.plugin_base import PluginBase
class Plugin(PluginBase):
    version = "1.0.0"
    def on_load(self):
        self.api.runtime.register_http_permission(
            "plugin:permission_example:jobs:run", "Run jobs", ["moderator"]
        )
""",
    )
    policy = app_context.plugin_manager.access_policy
    assert "plugin:permission_example:jobs:run" in policy.resolve("moderator")
    assert test_app.openapi_schema is None
    assert test_app.openapi() is not schema
    assert await app_context.plugin_manager.unload_plugin_by_name("permission_example")
    assert "plugin:permission_example:jobs:run" not in policy.descriptions
    with pytest.raises(Exception):
        plugin.api.runtime.register_http_permission(
            "plugin:permission_example:jobs:run", "Stale", ["admin"]
        )

"""Regression coverage for the supported plugin/HTTP capability boundaries."""

import runpy
from pathlib import Path

import pytest

from bedrock_server_manager.permissions import (
    NON_DELEGATABLE,
    PERMISSION_SPECS,
    PERSONAL_PERMISSIONS,
    ROLE_GRANTS,
    SERVER_PERMISSIONS,
    STEP_UP_PERMISSIONS,
    Permission,
)
from bedrock_server_manager.plugins.api_bridge import create_app_api

SOURCE = """
from pydantic import BaseModel
from bedrock_server_manager import PluginBase
class Settings(BaseModel):
    value: int = 1
class Probe(PluginBase):
    version = "1.0"
    settings_model = Settings
    global_settings_model = Settings
    server_settings_model = Settings
    permissions = PERMISSIONS
"""


@pytest.mark.parametrize(
    "permissions",
    [
        None,
        [],
        ["settings:read"],
        ["settings:manage"],
        ["servers:read"],
        ["servers:configure"],
    ],
)
async def test_plugin_settings_scopes_are_enforced_on_helpers_and_bridge(
    plugin_factory,
    app_context,
    permissions,
):
    plugin = await plugin_factory(
        "scoped_settings", SOURCE.replace("PERMISSIONS", repr(permissions))
    )
    await app_context.server_service.register_or_update_server("one")
    # Intrinsic own-table access does not grant global or server settings access.
    await plugin.set_plugin_setting("value", 2)
    assert await plugin.get_plugin_setting("value") == 2
    for scope, read, write, extra in (
        ("global", "settings:read", "settings:manage", {}),
        ("server", "servers:read", "servers:configure", {"server_name": "one"}),
    ):
        if permissions is None or read in permissions:
            assert await plugin.get_plugin_setting("value", scope=scope, **extra) == 1
        else:
            with pytest.raises(PermissionError, match=read):
                await plugin.get_plugin_setting("value", scope=scope, **extra)
        if permissions is None or write in permissions:
            await plugin.set_plugin_setting("value", 3, scope=scope, **extra)
            assert (
                app_context.plugin_service.get_setting(
                    "scoped_settings", "value", scope, extra.get("server_name")
                )
                == 3
            )
        else:
            with pytest.raises(PermissionError, match=write):
                await plugin.api.plugins.set_plugin_setting(
                    {"key": "value", "value": 3, "scope": scope, **extra}
                )
    with pytest.raises(TypeError, match="injected"):
        await plugin.api.plugins.get_plugin_setting({}, plugin_name="someone_else")


async def test_path_grant_is_not_global_settings_access(plugin_factory, app_context):
    plugin = await plugin_factory(
        "path_probe", SOURCE.replace("PERMISSIONS", repr(["path:servers"]))
    )
    response = await plugin.api.settings.get_global_setting({"key": "paths.servers"})
    assert response.value == app_context.settings.get("paths.servers")
    for key in ("web.port", "paths", "paths.plugins", "paths.credentials"):
        with pytest.raises(PermissionError):
            await plugin.api.settings.get_global_setting({"key": key})
    with pytest.raises(PermissionError, match="settings:read"):
        await plugin.api.settings.get_all_global_settings({})


@pytest.mark.parametrize("permissions", [None, [], ["diagnostics:read"]])
async def test_global_event_and_operation_history_requires_diagnostics(
    plugin_factory, permissions
):
    plugin = await plugin_factory(
        "diagnostic_probe", SOURCE.replace("PERMISSIONS", repr(permissions))
    )
    for read in (plugin.api.events.diagnostics, plugin.api.operations.activity):
        if permissions is None or "diagnostics:read" in permissions:
            assert read() is not None
        else:
            with pytest.raises(PermissionError, match="diagnostics:read"):
                read()
    # Local coordination remains available without installation-wide diagnostic access.
    assert plugin.api.operations.current() is None
    with plugin.api.operations.scope("diagnostic_probe:local"):
        assert plugin.api.operations.current() is not None
        assert plugin.api.operations.sequence() is not None
        assert plugin.api.operations.results() == ()
    if permissions == []:
        plugin.permissions.append("diagnostics:read")
        with pytest.raises(PermissionError):
            plugin.api.events.diagnostics()


def test_discovery_distinguishes_conditional_owner_public_and_internal():
    operations = {
        item["name"]: item
        for item in create_app_api("catalog", None).list_available_apis()
    }
    conditional = operations["get_global_setting"]["access"]
    assert conditional["mode"] == "conditional"
    assert {item["required_scope"] for item in conditional["conditions"]} == {
        "settings:read",
        "path:servers",
        "path:backups",
        "path:content",
        "path:downloads",
        "path:themes",
    }
    assert operations["get_plugin_setting"]["access"]["mode"] == "conditional"
    assert operations["websocket_unregister_data_provider"]["access"]["mode"] == "owner"
    assert operations["validate_property_value"]["access"]["mode"] == "public"
    assert "set_global_setting" not in operations
    internal = {
        item["name"]: item
        for item in create_app_api(
            "application", None, is_core=True
        ).list_available_apis()
    }
    assert internal["set_global_setting"]["access"]["mode"] == "internal"
    conditional["conditions"].clear()
    refreshed = {
        item["name"]: item
        for item in create_app_api("catalog", None).list_available_apis()
    }
    assert refreshed["get_global_setting"]["access"]["conditions"]


def test_catalog_covers_every_permission_and_derived_policy():
    assert set(PERMISSION_SPECS) == set(Permission)
    assert ROLE_GRANTS["user"] <= ROLE_GRANTS["moderator"] <= ROLE_GRANTS["admin"]
    assert ROLE_GRANTS["admin"] == frozenset(Permission)
    assert not SERVER_PERMISSIONS & PERSONAL_PERMISSIONS
    assert STEP_UP_PERMISSIONS <= NON_DELEGATABLE
    assert Permission.SERVERS_LOGS in SERVER_PERMISSIONS
    assert Permission.APPLICATION_LOGS not in SERVER_PERMISSIONS
    assert (
        "jobs run as the application"
        in PERMISSION_SPECS[Permission.SCHEDULER_MANAGE].description
    )


def test_generated_permission_reference_is_current():
    root = Path(__file__).resolve().parents[2]
    generator = runpy.run_path(str(root / "scripts/generate_permission_reference.py"))
    current = generator["DEFAULT_PATH"].read_text(encoding="utf-8")
    assert generator["updated_document"](current) == current

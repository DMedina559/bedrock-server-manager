from pathlib import Path

import pytest

from bedrock_server_manager.api.models.settings import (
    GetGlobalSettingRequest,
    SetCustomGlobalSettingRequest,
)
from bedrock_server_manager.plugins.api_bridge import create_app_api


async def test_plugin_api_calls_real_settings_and_persistence(app_context):
    api = create_app_api("test_plugin", app_context)
    response = await api.settings.set_custom_global_setting(
        SetCustomGlobalSettingRequest(key="bridge", value={"saved": True})
    )
    assert response.status == "success"
    await app_context.settings.reload()
    response = await api.settings.get_global_setting(
        GetGlobalSettingRequest(key="custom.bridge")
    )
    assert response.value == {"saved": True}

    with pytest.raises(PermissionError):
        await api.settings.get_global_setting(
            GetGlobalSettingRequest(key="paths.servers")
        )
    all_settings = await api.settings.get_all_global_settings({})
    assert "paths" not in all_settings.settings

    await api.runtime.write_plugin_file("private.json", {"owner": "test_plugin"})
    assert await api.runtime.read_plugin_file("private.json") == {
        "owner": "test_plugin"
    }
    await api.runtime.write_plugin_file("shared.json", {"shared": 1}, scope="public")
    other_api = create_app_api("other_plugin", app_context)
    assert await other_api.runtime.read_plugin_file("shared.json", scope="public") == {
        "shared": 1
    }
    private_dir = await api.runtime.get_plugin_data_path()
    public_dir = await api.runtime.get_plugin_data_path(scope="public")
    assert private_dir.name == "test_plugin"
    assert private_dir.parent.name == "plugins"
    assert public_dir.name == "public"
    assert public_dir.parent.name == "plugins"


async def test_plugin_api_delivers_actual_events(app_context, plugin_factory):
    plugin = await plugin_factory(
        "listener",
        "from bedrock_server_manager import PluginBase\nclass Listener(PluginBase):\n    version = '1.0'\n",
    )
    api = plugin.api
    received = []

    async def listener(*args, **kwargs):
        received.append((args, kwargs))

    from pydantic import BaseModel

    class Payload(BaseModel):
        key: str

    api.events.define("listener:integration_event", Payload)
    api.listen_for_event("listener:integration_event", listener)
    await api.send_event("listener:integration_event", key="value")
    assert len(received) == 1
    assert received[0][0] == ()
    assert received[0][1]["key"] == "value"
    assert received[0][1]["_triggering_plugin"] == "listener"


def test_plugin_api_describes_actual_registry(app_context):
    api = create_app_api("test_plugin", app_context)
    descriptions = api.list_available_apis()
    assert any(item["name"] == "start_server" for item in descriptions)
    for description in descriptions:
        assert all(
            item["name"] not in {"app_context", "plugin_name"}
            for item in description["parameters"]
        )


def test_unregistered_api_is_not_exposed(app_context):
    api = create_app_api("test_plugin", app_context)
    with pytest.raises(AttributeError):
        api.nonexistent_api()


async def test_plugin_cannot_supply_runtime_dependencies(app_context):
    api = create_app_api("test_plugin", app_context)
    with pytest.raises(TypeError, match="injected"):
        await api.settings.get_global_setting(
            {"key": "web.port"}, app_context=app_context
        )


async def test_runtime_lifecycle_positional_options_match_protocol(
    app_context, real_bedrock_server, plugin_factory
):
    plugin = await plugin_factory(
        "example",
        "from bedrock_server_manager import PluginBase\nclass Example(PluginBase):\n    version = '1.0'\n    permissions = ['servers:lifecycle']\n",
    )
    api = plugin.api
    async with api.runtime.server_lifecycle_manager(
        real_bedrock_server.server_name, False, False
    ):
        pass
    assert not await real_bedrock_server.is_running()
    with pytest.raises(TypeError):
        api.runtime.server_lifecycle_manager("server", False, app_context=app_context)


@pytest.mark.parametrize("value", [None, False, 0, ""])
async def test_plugin_settings_preserve_falsy_values(app_context, value):
    import logging

    from bedrock_server_manager.plugins.plugin_base import PluginBase

    plugin = PluginBase(
        "settings",
        create_app_api("settings", app_context),
        logging.getLogger("test.plugin"),
    )
    result = await plugin.set_plugin_setting("key", value)
    assert result.status == "success"
    assert await plugin.get_plugin_setting("key", default="fallback") == (
        "fallback" if value is None else value
    )
    await app_context.storage.load_state(app_context.state)
    assert await plugin.get_plugin_setting("key", default="fallback") == (
        "fallback" if value is None else value
    )


async def test_plugin_task_bridge_runs_actual_server_api(
    app_context, real_bedrock_server, wait_for_task
):
    import logging

    from bedrock_server_manager.plugins.plugin_base import PluginBase

    class AutostartPlugin(PluginBase):
        permissions = ["servers:lifecycle"]

    plugin = AutostartPlugin(
        "autostart",
        create_app_api("autostart", app_context),
        logging.getLogger("test"),
    )
    app_context.plugin_manager.plugins.append(plugin)
    api = plugin.api
    task_id = await api.runtime.run_task(
        api.server.start,
        request={"server_name": real_bedrock_server.server_name},
        username="System (Autostart)",
    )
    snapshot = await wait_for_task(app_context, task_id)
    assert snapshot.result["server_name"] == real_bedrock_server.server_name
    assert snapshot.result["outcome"] == "started"
    assert await real_bedrock_server.is_running()
    assert app_context.task_manager._plugin_owners[task_id] == "autostart"
    assert await app_context.task_manager.get_task(task_id, username="other") is None


async def test_unscoped_api_access_is_backward_compatible_and_logs_deprecation(
    app_context, caplog
):
    import logging

    api = create_app_api("legacy_caller", app_context)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        response = await api.set_custom_global_setting(
            SetCustomGlobalSettingRequest(key="unscoped_test", value={"ok": 1})
        )
        assert response.status == "success"
        data_dir = await api.get_plugin_data_path()
        assert data_dir.name == "legacy_caller"

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "deprecated unscoped API 'self.api.set_custom_global_setting'" in messages
    assert "use 'self.api.settings.set_custom_global_setting' instead" in messages
    assert (
        "deprecated unscoped runtime capability 'self.api.get_plugin_data_path'"
        in messages
    )


async def test_plugin_path_permissions_and_blacklist(app_context, plugin_factory):
    granted_plugin = await plugin_factory(
        "granted_plugin",
        """
from bedrock_server_manager import PluginBase

class GrantedPlugin(PluginBase):
    version = "1.0.0"
    permissions = ["path:servers"]
""",
    )
    res = await granted_plugin.api.settings.get_global_setting(
        GetGlobalSettingRequest(key="paths.servers")
    )
    assert res.status == "success"
    assert res.value == app_context.settings.get("paths.servers")

    servers_path = await granted_plugin.api.runtime.get_system_path("servers")
    assert str(servers_path) == str(
        Path(app_context.settings.get("paths.servers")).resolve()
    )

    with pytest.raises(PermissionError):
        await granted_plugin.api.settings.get_global_setting(
            GetGlobalSettingRequest(key="paths.backups")
        )
    with pytest.raises(PermissionError):
        await granted_plugin.api.runtime.get_system_path("backups")

    with pytest.raises(PermissionError):
        await granted_plugin.api.settings.get_global_setting(
            GetGlobalSettingRequest(key="paths.plugins")
        )
    with pytest.raises(PermissionError):
        await granted_plugin.api.settings.get_global_setting(
            GetGlobalSettingRequest(key="paths")
        )

    all_settings = await granted_plugin.api.settings.get_all_global_settings({})
    assert "paths" in all_settings.settings
    assert "servers" in all_settings.settings["paths"]
    assert "plugins" not in all_settings.settings["paths"]
    assert "backups" not in all_settings.settings["paths"]

    denied_plugin = await plugin_factory(
        "denied_plugin",
        """
from bedrock_server_manager import PluginBase

class DeniedPlugin(PluginBase):
    version = "1.0.0"
    permissions = []
""",
    )
    with pytest.raises(PermissionError):
        await denied_plugin.api.settings.get_global_setting(
            GetGlobalSettingRequest(key="paths.servers")
        )
    with pytest.raises(PermissionError):
        await denied_plugin.api.runtime.get_system_path("servers")
    all_denied = await denied_plugin.api.settings.get_all_global_settings({})
    assert "paths" not in all_denied.settings


async def test_scoped_server_lifecycle_and_command_permissions(
    app_context, plugin_factory
):
    from bedrock_server_manager.api.models import SendCommandRequest, StartServerRequest

    plugin = await plugin_factory(
        "restricted_plugin",
        """
from bedrock_server_manager import PluginBase

class RestrictedPlugin(PluginBase):
    version = "1.0.0"
    permissions = []
""",
    )
    with pytest.raises(PermissionError, match="servers:lifecycle"):
        await plugin.api.server.start(StartServerRequest(server_name="test"))
    with pytest.raises(PermissionError, match="servers:command"):
        await plugin.api.server.send_command(
            SendCommandRequest(server_name="test", command="list")
        )

    allowed_plugin = await plugin_factory(
        "allowed_plugin",
        """
from bedrock_server_manager import PluginBase

class AllowedPlugin(PluginBase):
    version = "1.0.0"
    permissions = ["servers:lifecycle", "servers:command"]
""",
    )
    assert allowed_plugin.permissions == ["servers:lifecycle", "servers:command"]


async def test_unexposed_api_methods_raise_attribute_error_for_plugins(
    app_context, plugin_factory
):
    plugin = await plugin_factory(
        "probe_plugin",
        """
from bedrock_server_manager import PluginBase

class ProbePlugin(PluginBase):
    version = "1.0.0"
""",
    )
    with pytest.raises(AttributeError, match="is not exposed to plugins"):
        _ = plugin.api.settings.set_global_setting

    with pytest.raises(AttributeError, match="is not exposed to plugins"):
        _ = plugin.api.backup_restore.delete_server_backup

    with pytest.raises(AttributeError, match="is not exposed to plugins"):
        _ = plugin.api.server.delete_server_data

    with pytest.raises(AttributeError, match="is not exposed to plugins"):
        _ = plugin.api.plugins.reload_plugins


async def test_granular_capability_scopes(app_context, plugin_factory):
    from bedrock_server_manager.api.models import (
        AddPlayersManuallyRequest,
        AddServerBanRequest,
        AddToAllowlistRequest,
        BackupWorldRequest,
        EnableAddonRequest,
        ExportWorldRequest,
        GetAllKnownPlayersRequest,
        GetAllowlistRequest,
        GetAllServersDataRequest,
        GetApplicationDiagnosticsRequest,
        GetApplicationHealthRequest,
        GetApplicationMetricsRequest,
        GetPermissionsRequest,
        GetPluginStatusesRequest,
        GetPropertiesRequest,
        GetServerBansRequest,
        GetServerSettingRequest,
        GetWorldNameRequest,
        ListAvailableAddonsRequest,
        ListInstalledAddonsRequest,
        ListSchedulesRequest,
        ListSnapshotsRequest,
        ManageSnapshotRequest,
        PlanSnapshotRestoreRequest,
        ResetWorldRequest,
        RestoreSnapshotRequest,
        SetPermissionsRequest,
        SetPropertiesRequest,
        UpdateServerRequest,
    )

    unscoped_plugin = await plugin_factory(
        "unscoped_test_plugin",
        """
from bedrock_server_manager import PluginBase

class UnscopedPlugin(PluginBase):
    version = "1.0.0"
    permissions = []
""",
    )

    with pytest.raises(PermissionError, match="servers:read"):
        await unscoped_plugin.api.application.get_all_servers_data(
            GetAllServersDataRequest()
        )

    with pytest.raises(PermissionError, match="servers:read"):
        await unscoped_plugin.api.server.get_setting(
            GetServerSettingRequest(server_name="test", key="settings.autostart")
        )

    with pytest.raises(PermissionError, match="health:read"):
        await unscoped_plugin.api.system.get_application_health(
            GetApplicationHealthRequest()
        )

    with pytest.raises(PermissionError, match="runtime:metrics"):
        await unscoped_plugin.api.system.get_application_metrics(
            GetApplicationMetricsRequest()
        )

    with pytest.raises(PermissionError, match="servers:install"):
        await unscoped_plugin.api.install.update_server(
            UpdateServerRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="properties:read"):
        await unscoped_plugin.api.properties.get_properties(
            GetPropertiesRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="properties:manage"):
        await unscoped_plugin.api.properties.set_properties(
            SetPropertiesRequest(server_name="test", properties_to_update={})
        )

    with pytest.raises(PermissionError, match="permissions:read"):
        await unscoped_plugin.api.permissions.get_permissions(
            GetPermissionsRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="permissions:manage"):
        await unscoped_plugin.api.permissions.set_permissions(
            SetPermissionsRequest(
                server_name="test",
                player_name="player",
                xuid="123",
                permission="operator",
            )
        )

    with pytest.raises(PermissionError, match="allowlist:read"):
        await unscoped_plugin.api.allowlist.get_allowlist(
            GetAllowlistRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="allowlist:manage"):
        await unscoped_plugin.api.allowlist.add_to_allowlist(
            AddToAllowlistRequest(server_name="test", new_players_data=[])
        )

    with pytest.raises(PermissionError, match="bans:read"):
        await unscoped_plugin.api.ban.get_server_bans(
            GetServerBansRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="bans:manage"):
        await unscoped_plugin.api.ban.add_server_ban(
            AddServerBanRequest(server_name="test", player_name="p", xuid="123")
        )

    with pytest.raises(PermissionError, match="players:read"):
        await unscoped_plugin.api.player.get_all_known_players(
            GetAllKnownPlayersRequest()
        )

    with pytest.raises(PermissionError, match="players:manage"):
        await unscoped_plugin.api.player.add_players_manually(
            AddPlayersManuallyRequest(player_strings=["player:123"])
        )

    with pytest.raises(PermissionError, match="worlds:read"):
        await unscoped_plugin.api.world.get_world_name(
            GetWorldNameRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="worlds:manage"):
        await unscoped_plugin.api.world.export_world(
            ExportWorldRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="worlds:reset"):
        await unscoped_plugin.api.world.reset_world(
            ResetWorldRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="content:read"):
        await unscoped_plugin.api.addon.list_available_addons(
            ListAvailableAddonsRequest()
        )

    with pytest.raises(PermissionError, match="addons:read"):
        await unscoped_plugin.api.addon.list_installed_addons(
            ListInstalledAddonsRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="addons:manage"):
        await unscoped_plugin.api.addon.enable_addon(
            EnableAddonRequest(
                server_name="test", pack_uuid="uuid", pack_type="behavior"
            )
        )

    with pytest.raises(PermissionError, match="backups:read"):
        await unscoped_plugin.api.backup_restore.list_server_snapshots(
            ListSnapshotsRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="backups:create"):
        await unscoped_plugin.api.backup_restore.backup_world(
            BackupWorldRequest(server_name="test")
        )

    with pytest.raises(PermissionError, match="backups:restore"):
        await unscoped_plugin.api.backup_restore.plan_server_restore(
            PlanSnapshotRestoreRequest(
                server_name="test",
                backup_id="snap1",
                components=["world"],
            )
        )

    with pytest.raises(PermissionError, match="backups:restore"):
        await unscoped_plugin.api.backup_restore.restore_server_snapshot(
            RestoreSnapshotRequest(
                server_name="test",
                backup_id="snap1",
                components=["world"],
                token="tok",
            )
        )

    with pytest.raises(PermissionError, match="backups:manage"):
        await unscoped_plugin.api.backup_restore.manage_server_snapshot(
            ManageSnapshotRequest(
                server_name="test",
                backup_id="snap1",
                action="pin",
            )
        )

    with pytest.raises(PermissionError, match="plugins:read"):
        await unscoped_plugin.api.plugins.get_plugin_statuses(
            GetPluginStatusesRequest()
        )

    with pytest.raises(PermissionError, match="scheduler:read"):
        await unscoped_plugin.api.scheduler.list_schedules(ListSchedulesRequest())

    with pytest.raises(PermissionError, match="diagnostics:read"):
        await unscoped_plugin.api.diagnostics.get_application_diagnostics(
            GetApplicationDiagnosticsRequest()
        )

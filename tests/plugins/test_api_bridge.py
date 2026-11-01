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
    app_context, real_bedrock_server
):
    api = create_app_api("example", app_context)
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
    api = create_app_api("autostart", app_context)
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

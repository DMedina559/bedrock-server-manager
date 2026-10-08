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


async def test_plugin_api_delivers_actual_events(app_context, plugin_factory):
    plugin = await plugin_factory(
        "listener",
        "from bedrock_server_manager import PluginBase\nclass Listener(PluginBase):\n    version = '1.0'\n",
    )
    api = plugin.api
    received = []

    async def listener(*args, **kwargs):
        received.append((args, kwargs))

    api.listen_for_event("integration_event", listener)
    await api.send_event("integration_event", 1, key="value")
    assert len(received) == 1
    assert received[0][0] == (1,)
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

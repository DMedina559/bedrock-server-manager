import pytest

from bedrock_server_manager.api.models import (
    GetPluginStatusesRequest,
    ReloadPluginsRequest,
    SetPluginStatusRequest,
    TriggerExternalAppEventRequest,
)
from bedrock_server_manager.api.plugins import (
    get_plugin_statuses,
    reload_plugins,
    set_plugin_status,
    trigger_external_app_event,
)
from bedrock_server_manager.error import UserInputError


async def test_plugin_status_changes_persist_and_reload(app_context, plugin_factory):
    await plugin_factory(
        "integration",
        "from bedrock_server_manager import PluginBase\nclass Integration(PluginBase):\n    version = '1.0'\n",
    )

    async def status():
        return (
            await get_plugin_statuses(
                GetPluginStatusesRequest(), app_context=app_context
            )
        ).plugins["integration"]

    assert (await status()).enabled
    await set_plugin_status(
        SetPluginStatusRequest(target_plugin_name="integration", enabled=False),
        app_context=app_context,
    )
    assert not (await status()).enabled
    assert app_context.plugin_manager.plugins == []
    await reload_plugins(ReloadPluginsRequest(), app_context=app_context)
    assert not (await status()).enabled
    await set_plugin_status(
        SetPluginStatusRequest(target_plugin_name="integration", enabled=True),
        app_context=app_context,
    )
    assert (await status()).enabled
    assert len(app_context.plugin_manager.plugins) == 1


async def test_external_event_reaches_loaded_plugin(app_context, plugin_factory):
    plugin = await plugin_factory(
        "events",
        "from bedrock_server_manager import PluginBase\nclass Events(PluginBase):\n    version = '1.0'\n",
    )
    received = []

    async def listener(*args, **kwargs):
        received.append(kwargs)

    plugin.api.listen_for_event("integration_event", listener)
    response = await trigger_external_app_event(
        TriggerExternalAppEventRequest(
            event_name="integration_event", payload={"saved": True}
        ),
        app_context=app_context,
    )
    assert response.status == "success"
    assert received[0]["saved"] is True


async def test_unknown_plugin_is_rejected_without_configuration_change(app_context):
    with pytest.raises(UserInputError):
        await set_plugin_status(
            SetPluginStatusRequest(target_plugin_name="missing", enabled=True),
            app_context=app_context,
        )
    assert app_context.plugin_manager.plugin_config == {}

from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.api.models.application import GetAllServersDataResponse
from bedrock_server_manager.api.models.common import ServerSummary
from bedrock_server_manager.api.models.server import (
    GetServerSettingResponse,
    GetServerSummaryResponse,
)
from bedrock_server_manager.api.models.settings import (
    GetGlobalSettingResponse,
    SetGlobalSettingResponse,
)
from bedrock_server_manager.plugins.default.autostart_plugin import AutostartServers
from bedrock_server_manager.plugins.default.server_lifecycle_notifications import (
    ServerLifecycleNotificationsPlugin,
)
from bedrock_server_manager.plugins.plugin_base import PluginBase


async def test_autostart_consumes_nested_server_models():
    api = MagicMock()
    api.get_all_servers_data = AsyncMock(
        return_value=GetAllServersDataResponse(
            servers=[ServerSummary(name="test", status="STOPPED", version="1.0")]
        )
    )
    api.get_server_setting = AsyncMock(
        return_value=GetServerSettingResponse(value=True)
    )
    api.run_task = AsyncMock()
    plugin = AutostartServers("autostart", api, MagicMock())

    await plugin.autostart_servers()

    api.run_task.assert_awaited_once_with(
        api.start_server, request={"server_name": "test"}, username="System (Autostart)"
    )


async def test_shutdown_notification_consumes_nested_summary(monkeypatch):
    api = MagicMock()
    api.get_server_summary = AsyncMock(
        return_value=GetServerSummaryResponse(
            summary=ServerSummary(
                name="test", status="RUNNING", version="1.0", player_count=1
            )
        )
    )
    plugin = ServerLifecycleNotificationsPlugin("notifications", api, MagicMock())
    plugin.stop_warning_delay = 3
    monkeypatch.setattr(plugin, "_is_server_running", AsyncMock(return_value=True))
    send = AsyncMock()
    monkeypatch.setattr(plugin, "_send_ingame_message", send)
    sleep = AsyncMock()
    monkeypatch.setattr(
        "bedrock_server_manager.plugins.default.server_lifecycle_notifications.asyncio.sleep",
        sleep,
    )

    await plugin.send_shutdown_warning(server_name="test")

    send.assert_awaited_once_with(
        "test", "Server is stopping in 3 seconds...", "shutdown warning"
    )
    sleep.assert_awaited_once_with(3)


@pytest.mark.parametrize("value", [None, False, 0, ""])
async def test_plugin_settings_preserve_falsy_values(value):
    api = MagicMock()
    api.get_global_setting = AsyncMock(
        return_value=GetGlobalSettingResponse(value=value)
    )
    saved = SetGlobalSettingResponse(message="saved")
    api.set_global_setting = AsyncMock(return_value=saved)
    plugin = PluginBase("settings", api, MagicMock())

    assert await plugin.get_plugin_setting("key", default="fallback") == (
        "fallback" if value is None else value
    )
    assert await plugin.set_plugin_setting("key", value) is saved

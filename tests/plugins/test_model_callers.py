import asyncio
import logging
from pathlib import Path

import pytest

from bedrock_server_manager.plugins.api_bridge import create_app_api
from bedrock_server_manager.plugins.default.autostart_plugin import AutostartServers
from bedrock_server_manager.plugins.default.server_lifecycle_notifications import (
    ServerLifecycleNotificationsPlugin,
)
from bedrock_server_manager.plugins.plugin_base import PluginBase


async def test_autostart_consumes_real_server_models(
    app_context, real_bedrock_server, wait_for_task
):
    await real_bedrock_server.set_autostart(True)
    plugin = AutostartServers(
        "autostart",
        create_app_api("autostart", app_context),
        logging.getLogger("test.plugin"),
    )
    await plugin.autostart_servers()
    tasks = await app_context.task_manager.get_all_tasks(username="System (Autostart)")
    assert len(tasks) == 1
    snapshot = await wait_for_task(app_context, next(iter(tasks)))
    assert snapshot.result["outcome"] == "started"
    assert snapshot.result["server_name"] == real_bedrock_server.server_name
    assert await real_bedrock_server.is_running()
    assert app_context.task_manager._plugin_owners[snapshot.id] == "autostart"
    await real_bedrock_server.stop()
    await real_bedrock_server.set_autostart(False)
    await plugin.autostart_servers()
    assert (
        len(await app_context.task_manager.get_all_tasks(username="System (Autostart)"))
        == 1
    )


async def test_shutdown_notification_consumes_real_summary(
    app_context, real_bedrock_server, caplog
):
    server = real_bedrock_server
    await server.start()
    await server.send_command("__DUMMY__ PLAYER_JOIN Steve")
    async with asyncio.timeout(5):
        while not await server.player_tracker.update_online_players():
            await asyncio.sleep(0.01)
    plugin = ServerLifecycleNotificationsPlugin(
        "notifications",
        create_app_api("notifications", app_context),
        logging.getLogger("test.plugin"),
    )
    plugin.stop_warning_delay = 0
    with caplog.at_level(logging.INFO):
        await plugin.send_shutdown_warning(server_name=server.server_name)
    assert "Sent shutdown warning" in caplog.text
    async with asyncio.timeout(5):
        while (
            "Server is stopping in 0 seconds"
            not in Path(server.paths.server_log_path).read_text()
        ):
            await asyncio.sleep(0.01)


@pytest.mark.parametrize("value", [None, False, 0, ""])
async def test_plugin_settings_preserve_falsy_values(app_context, value):
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

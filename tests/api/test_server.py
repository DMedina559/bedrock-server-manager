import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    DeleteServerDataRequest,
    GetAllServerSettingsRequest,
    GetServerSettingRequest,
    RestartServerRequest,
    SendCommandRequest,
    SetServerCustomValueRequest,
    SetServerSettingRequest,
    SetServerStatusRequest,
    StartServerRequest,
    StopServerRequest,
    UpdateServerPlayerStatsRequest,
)
from bedrock_server_manager.api.server import (
    delete_server_data,
    get_all_server_settings,
    get_server_setting,
    restart_server,
    send_command,
    server_lifecycle_manager,
    set_server_custom_value,
    set_server_setting,
    set_server_status,
    start_server,
    stop_server,
    update_server_player_stats,
)
from bedrock_server_manager.error import BlockedCommandError, ServerRunningError


async def test_server_api_lifecycle_settings_commands_and_deletion(
    app_context, real_bedrock_server
):
    name = real_bedrock_server.server_name
    path = Path(real_bedrock_server.paths.server_dir)

    # Settings persistence
    await set_server_setting(
        SetServerSettingRequest(
            server_name=name, key="settings.autoupdate", value=True
        ),
        app_context=app_context,
    )
    assert (
        await get_server_setting(
            GetServerSettingRequest(server_name=name, key="settings.autoupdate"),
            app_context=app_context,
        )
    ).value is True
    await set_server_custom_value(
        SetServerCustomValueRequest(
            server_name=name, key="integration", value={"value": 42}
        ),
        app_context=app_context,
    )
    result = await get_all_server_settings(
        GetAllServerSettingsRequest(server_name=name), app_context=app_context
    )
    assert result.settings["custom"]["integration"] == {"value": 42}
    await app_context.reload()
    assert await real_bedrock_server.get_autoupdate()

    # Blocked command rejected
    with pytest.raises(BlockedCommandError):
        await send_command(
            SendCommandRequest(server_name=name, command="stop"),
            app_context=app_context,
        )

    # Status and lifecycle controls
    assert (
        await set_server_status(
            SetServerStatusRequest(server_name=name, status="STOPPED"),
            app_context=app_context,
        )
    ).new_status == "STOPPED"

    assert (
        await start_server(
            StartServerRequest(server_name=name), app_context=app_context
        )
    ).outcome == "started"
    first_pid = real_bedrock_server.process._process.pid
    assert (
        await start_server(
            StartServerRequest(server_name=name), app_context=app_context
        )
    ).outcome == "already_running"
    assert real_bedrock_server.process._process.pid == first_pid

    # Runtime stats and send_command while running
    stats_resp = await update_server_player_stats(
        UpdateServerPlayerStatsRequest(
            server_name=name, player_count=1, players=[{"name": "Steve", "xuid": "123"}]
        ),
        app_context=app_context,
    )
    assert stats_resp.status == "success"
    assert (await real_bedrock_server.get_summary_info()).player_count == 1

    cmd_resp = await send_command(
        SendCommandRequest(server_name=name, command="__DUMMY__ PLAYER_JOIN APIPlayer"),
        app_context=app_context,
    )
    assert cmd_resp.status == "success"

    # Delete without stop preserves running server
    with pytest.raises(ServerRunningError):
        await delete_server_data(
            DeleteServerDataRequest(server_name=name, stop_if_running=False),
            app_context=app_context,
        )
    assert path.exists() and await real_bedrock_server.is_running()

    # Restart and cancelled maintenance
    restart_res = await restart_server(
        RestartServerRequest(server_name=name, send_message=False),
        app_context=app_context,
    )
    assert restart_res.outcome == "restarted"
    assert real_bedrock_server.process._process.pid != first_pid

    with pytest.raises(asyncio.CancelledError):
        async with server_lifecycle_manager(name, True, app_context=app_context):
            assert not await real_bedrock_server.is_running()
            raise asyncio.CancelledError
    assert not await real_bedrock_server.is_running()

    assert (
        await stop_server(StopServerRequest(server_name=name), app_context=app_context)
    ).outcome == "already_stopped"

    # Delete removes actual installation
    del_res = await delete_server_data(
        DeleteServerDataRequest(server_name=name),
        app_context=app_context,
    )
    assert del_res.status == "success" and del_res.server_name == name
    assert not path.exists() and name not in app_context._servers


def test_server_request_validations():
    for model in (StartServerRequest, StopServerRequest, DeleteServerDataRequest):
        with pytest.raises(ValidationError):
            model(server_name="")

    with pytest.raises(ValidationError):
        UpdateServerPlayerStatsRequest(
            server_name="test_server", player_count=2, players=[]
        )

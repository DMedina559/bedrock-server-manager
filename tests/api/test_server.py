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
    set_server_custom_value,
    set_server_setting,
    set_server_status,
    start_server,
    stop_server,
    update_server_player_stats,
)
from bedrock_server_manager.error import BlockedCommandError
from bedrock_server_manager.plugins.runtime_capabilities import server_lifecycle_manager


async def test_server_lifecycle_api_controls_real_process(
    app_context, real_bedrock_server
):
    name = real_bedrock_server.server_name
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
    result = await restart_server(
        RestartServerRequest(server_name=name, send_message=False),
        app_context=app_context,
    )
    assert result.outcome == "restarted"
    assert real_bedrock_server.process._process.pid != first_pid
    assert (
        await stop_server(StopServerRequest(server_name=name), app_context=app_context)
    ).outcome == "stopped"
    assert not await real_bedrock_server.is_running()
    assert (
        await stop_server(StopServerRequest(server_name=name), app_context=app_context)
    ).outcome == "already_stopped"


async def test_server_setting_api_persists_typed_and_custom_values(
    app_context, real_bedrock_server
):
    name = real_bedrock_server.server_name
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


async def test_server_runtime_stats_api_updates_summary(
    app_context, real_bedrock_server
):
    name = real_bedrock_server.server_name
    response = await set_server_status(
        SetServerStatusRequest(server_name=name, status="STOPPED"),
        app_context=app_context,
    )
    assert response.new_status == "STOPPED"
    await real_bedrock_server.start()
    response = await update_server_player_stats(
        UpdateServerPlayerStatsRequest(
            server_name=name, player_count=1, players=[{"name": "Steve", "xuid": "123"}]
        ),
        app_context=app_context,
    )
    assert response.status == "success"
    assert (await real_bedrock_server.get_summary_info()).player_count == 1


async def test_command_api_sends_to_actual_dummy_server(
    app_context, real_bedrock_server
):
    await real_bedrock_server.start()
    response = await send_command(
        SendCommandRequest(
            server_name=real_bedrock_server.server_name,
            command="__DUMMY__ PLAYER_JOIN APIPlayer",
        ),
        app_context=app_context,
    )
    assert response.status == "success"


async def test_blocked_command_is_rejected(app_context, real_bedrock_server):
    with pytest.raises(BlockedCommandError):
        await send_command(
            SendCommandRequest(
                server_name=real_bedrock_server.server_name, command="stop"
            ),
            app_context=app_context,
        )


async def test_delete_api_removes_actual_installation(app_context, real_bedrock_server):
    path = Path(real_bedrock_server.paths.server_dir)
    result = await delete_server_data(
        DeleteServerDataRequest(server_name=real_bedrock_server.server_name),
        app_context=app_context,
    )
    assert result.status == "success"
    assert not path.exists()
    assert real_bedrock_server.server_name not in app_context._servers


async def test_cancelled_maintenance_does_not_restart_server(
    app_context, real_bedrock_server
):
    await real_bedrock_server.start()
    with pytest.raises(asyncio.CancelledError):
        async with server_lifecycle_manager(
            real_bedrock_server.server_name, True, app_context=app_context
        ):
            assert not await real_bedrock_server.is_running()
            raise asyncio.CancelledError
    assert not await real_bedrock_server.is_running()


@pytest.mark.parametrize(
    "model", [StartServerRequest, StopServerRequest, DeleteServerDataRequest]
)
def test_lifecycle_request_rejects_empty_server(model):
    with pytest.raises(ValidationError):
        model(server_name="")


def test_runtime_player_request_rejects_mismatched_count():
    with pytest.raises(ValidationError):
        UpdateServerPlayerStatsRequest(
            server_name="test_server", player_count=2, players=[]
        )

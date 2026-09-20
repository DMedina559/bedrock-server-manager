from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.api.server import (
    delete_server_data,
    send_command,
    server_lifecycle_manager,
    set_server_status_api,
    start_server,
    stop_server,
    update_server_player_stats_api,
)
from bedrock_server_manager.error import BlockedCommandError, InvalidServerNameError


async def test_start_server_success(app_context, monkeypatch):
    """Test start_server dispatches to BedrockServer successfully."""
    mock_server = MagicMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.is_running = AsyncMock()
    mock_server.send_command = AsyncMock()
    mock_server.delete_all_data = AsyncMock()
    mock_server.is_running.return_value = False
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Mock the BedrockProcessManager globally mapped onto app_context
    mock_bpm = MagicMock()
    mock_bpm.add_server = AsyncMock()
    mock_bpm.remove_server = AsyncMock()
    monkeypatch.setattr(app_context, "_bedrock_process_manager", mock_bpm)

    result = await start_server("test_server", app_context)

    assert result["status"] == "success"

    mock_bpm.add_server.assert_awaited_once_with(mock_server)


async def test_start_server_missing_name(app_context):
    """Test start_server triggers early failure with invalid names."""
    with pytest.raises(InvalidServerNameError):
        await start_server("", app_context)


async def test_stop_server_success(app_context, monkeypatch):
    """Test stop_server executes successfully on target server."""
    mock_server = MagicMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.is_running = AsyncMock()
    mock_server.send_command = AsyncMock()
    mock_server.delete_all_data = AsyncMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    mock_bpm = MagicMock()
    mock_bpm.remove_server = AsyncMock()
    monkeypatch.setattr(app_context, "_bedrock_process_manager", mock_bpm)

    result = await stop_server("test_server", app_context)

    assert result["status"] == "success"


async def test_stop_server_missing_name(app_context):
    """Test stop_server triggers early failure with invalid names."""
    with pytest.raises(InvalidServerNameError):
        await stop_server("", app_context)


async def test_send_command_success(app_context, monkeypatch):
    """Test send_command correctly transmits cleanly verified commands."""
    mock_server = MagicMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.is_running = AsyncMock()
    mock_server.send_command = AsyncMock()
    mock_server.delete_all_data = AsyncMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = await send_command("test_server", "say hello", app_context)

    assert result["status"] == "success"
    mock_server.send_command.assert_called_once_with("say hello")


async def test_send_command_missing_name(app_context):
    """Test send_command correctly throws on missing server string."""
    with pytest.raises(InvalidServerNameError):
        await send_command("", "say hello", app_context)


async def test_send_command_blocked(app_context):
    """Test send_command throws an exception against restricted operations like stop."""
    with pytest.raises(BlockedCommandError):
        await send_command("test_server", "stop", app_context)


async def test_delete_server_data_success(app_context, monkeypatch):
    """Test delete_server_data properly purges the cache and directory logic."""
    mock_server = AsyncMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.is_running = AsyncMock()
    mock_server.send_command = AsyncMock()
    mock_server.delete_all_data = AsyncMock()
    mock_server.is_running.return_value = False
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)
    monkeypatch.setattr(app_context, "remove_server", AsyncMock())

    result = await delete_server_data("test_server", app_context)

    assert result["status"] == "success"


async def test_delete_server_data_missing_name(app_context):
    """Test delete_server_data catches empty missing server string."""
    with pytest.raises(InvalidServerNameError):
        await delete_server_data("", app_context)


async def test_server_lifecycle_manager(app_context, monkeypatch):
    """Test the context manager properly sequences start/stop flows based on arguments."""
    mock_server = AsyncMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.is_running = AsyncMock()
    mock_server.send_command = AsyncMock()
    mock_server.delete_all_data = AsyncMock()
    mock_server.is_running.return_value = True
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    mock_stop = AsyncMock(return_value={"status": "success"})
    mock_start = AsyncMock(return_value={"status": "success"})

    monkeypatch.setattr("bedrock_server_manager.api.server.stop_server", mock_stop)
    monkeypatch.setattr("bedrock_server_manager.api.server.start_server", mock_start)

    async with server_lifecycle_manager(
        "test_server", stop_before=True, app_context=app_context
    ):
        # The operation happens here
        pass

    mock_stop.assert_called_once()
    mock_start.assert_called_once()


async def test_set_server_status_api(app_context, monkeypatch):
    """Test internal set_server_status_api modifies JSON configuration effectively."""
    mock_server = MagicMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.is_running = AsyncMock()
    mock_server.send_command = AsyncMock()
    mock_server.delete_all_data = AsyncMock()
    mock_server.get_status_from_config = AsyncMock(return_value="STOPPED")
    mock_server._manage_json_config = AsyncMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = await set_server_status_api("test_server", "RUNNING", app_context)

    assert result["status"] == "success"
    assert result["previous_status"] == "STOPPED"
    mock_server._manage_json_config.assert_called_once_with(
        key="server_info.status", operation="write", value="RUNNING"
    )


async def test_update_server_player_stats_api(app_context):
    """Test update_server_player_stats_api effectively builds dictionary outputs for socket notifications."""
    result = update_server_player_stats_api(
        "test_server", 5, [{"name": "p1"}], app_context
    )

    assert result["status"] == "success"
    assert result["server_name"] == "test_server"
    assert result["player_count"] == 5
    assert len(result["players"]) == 1


async def test_set_server_setting_success(app_context, monkeypatch):
    """Test setting generic server configs via API correctly targets the managed config map."""
    from bedrock_server_manager.api.server import set_server_setting

    mock_server = MagicMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.is_running = AsyncMock()
    mock_server.send_command = AsyncMock()
    mock_server.delete_all_data = AsyncMock()
    mock_server._manage_json_config = AsyncMock(return_value=None)
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = await set_server_setting(
        "test_server", "test.key", "test_val", app_context
    )

    assert result["status"] == "success"
    mock_server._manage_json_config.assert_called_once_with(
        "test.key", "write", "test_val"
    )


async def test_set_server_custom_value_success(app_context, monkeypatch):
    """Test custom section configuration correctly delegates to BedrockServer layer."""
    from bedrock_server_manager.api.server import set_server_custom_value

    mock_server = MagicMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.is_running = AsyncMock()
    mock_server.send_command = AsyncMock()
    mock_server.delete_all_data = AsyncMock()
    mock_server.set_custom_config_value = AsyncMock(return_value=None)
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = await set_server_custom_value(
        "test_server", "my_custom", "custom_val", app_context
    )

    assert result["status"] == "success"
    mock_server.set_custom_config_value.assert_called_once_with(
        "my_custom", "custom_val"
    )


async def test_get_all_server_settings_success(app_context, monkeypatch):
    """Test fetching all configs correctly retrieves the underlying dict from core server."""
    from bedrock_server_manager.api.server import get_all_server_settings

    mock_server = AsyncMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.is_running = AsyncMock()
    mock_server.send_command = AsyncMock()
    mock_server.delete_all_data = AsyncMock()
    mock_server._load_server_config.return_value = {"key1": "val1"}
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = await get_all_server_settings("test_server", app_context)

    assert result["status"] == "success"
    assert result["key1"] == "val1"


async def test_get_server_setting_success(app_context, monkeypatch):
    """Test grabbing a single server setting works accurately targeting core mappings."""
    from bedrock_server_manager.api.server import get_server_setting

    mock_server = MagicMock()
    mock_server.start = AsyncMock()
    mock_server.stop = AsyncMock()
    mock_server.is_running = AsyncMock()
    mock_server.send_command = AsyncMock()
    mock_server.delete_all_data = AsyncMock()
    mock_server._manage_json_config = AsyncMock(return_value="secret")
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = await get_server_setting("test_server", "secret.key", app_context)

    assert result["status"] == "success"
    assert result["value"] == "secret"
    mock_server._manage_json_config.assert_called_once_with("secret.key", "read")

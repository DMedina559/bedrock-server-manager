from unittest.mock import MagicMock

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


def test_start_server_success(app_context, monkeypatch):
    """Test start_server dispatches to BedrockServer successfully."""
    mock_server = MagicMock()
    mock_server.is_running.return_value = False
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Mock the BedrockProcessManager globally mapped onto app_context
    mock_bpm = MagicMock()
    monkeypatch.setattr(app_context, "_bedrock_process_manager", mock_bpm)

    result = start_server("test_server", app_context)

    assert result["status"] == "success"
    mock_server.start.assert_called_once()
    mock_bpm.add_server.assert_called_once_with(mock_server)


def test_start_server_missing_name(app_context):
    """Test start_server triggers early failure with invalid names."""
    with pytest.raises(InvalidServerNameError):
        start_server("", app_context)


def test_stop_server_success(app_context, monkeypatch):
    """Test stop_server executes successfully on target server."""
    mock_server = MagicMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = stop_server("test_server", app_context)

    assert result["status"] == "success"
    mock_server.stop.assert_called_once()


def test_stop_server_missing_name(app_context):
    """Test stop_server triggers early failure with invalid names."""
    with pytest.raises(InvalidServerNameError):
        stop_server("", app_context)


def test_send_command_success(app_context, monkeypatch):
    """Test send_command correctly transmits cleanly verified commands."""
    mock_server = MagicMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = send_command("test_server", "say hello", app_context)

    assert result["status"] == "success"
    mock_server.send_command.assert_called_once_with("say hello")


def test_send_command_missing_name(app_context):
    """Test send_command correctly throws on missing server string."""
    with pytest.raises(InvalidServerNameError):
        send_command("", "say hello", app_context)


def test_send_command_blocked(app_context):
    """Test send_command throws an exception against restricted operations like stop."""
    with pytest.raises(BlockedCommandError):
        send_command("test_server", "stop", app_context)


def test_delete_server_data_success(app_context, monkeypatch):
    """Test delete_server_data properly purges the cache and directory logic."""
    mock_server = MagicMock()
    mock_server.is_running.return_value = False
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)
    monkeypatch.setattr(app_context, "remove_server", MagicMock())

    result = delete_server_data("test_server", app_context)

    assert result["status"] == "success"
    mock_server.delete_all_data.assert_called_once()


def test_delete_server_data_missing_name(app_context):
    """Test delete_server_data catches empty missing server string."""
    with pytest.raises(InvalidServerNameError):
        delete_server_data("", app_context)


def test_server_lifecycle_manager(app_context, monkeypatch):
    """Test the context manager properly sequences start/stop flows based on arguments."""
    mock_server = MagicMock()
    mock_server.is_running.return_value = True
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    mock_stop = MagicMock(return_value={"status": "success"})
    mock_start = MagicMock(return_value={"status": "success"})

    monkeypatch.setattr("bedrock_server_manager.api.server.stop_server", mock_stop)
    monkeypatch.setattr("bedrock_server_manager.api.server.start_server", mock_start)

    with server_lifecycle_manager(
        "test_server", stop_before=True, app_context=app_context
    ):
        # The operation happens here
        pass

    mock_stop.assert_called_once()
    mock_start.assert_called_once()


def test_set_server_status_api(app_context, monkeypatch):
    """Test internal set_server_status_api modifies JSON configuration effectively."""
    mock_server = MagicMock()
    mock_server.get_status_from_config.return_value = "STOPPED"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = set_server_status_api("test_server", "RUNNING", app_context)

    assert result["status"] == "success"
    assert result["previous_status"] == "STOPPED"
    mock_server._manage_json_config.assert_called_once_with(
        key="server_info.status", operation="write", value="RUNNING"
    )


def test_update_server_player_stats_api(app_context):
    """Test update_server_player_stats_api effectively builds dictionary outputs for socket notifications."""
    result = update_server_player_stats_api(
        "test_server", 5, [{"name": "p1"}], app_context
    )

    assert result["status"] == "success"
    assert result["server_name"] == "test_server"
    assert result["player_count"] == 5
    assert len(result["players"]) == 1


def test_set_server_setting_success(app_context, monkeypatch):
    """Test setting generic server configs via API correctly targets the managed config map."""
    from bedrock_server_manager.api.server import set_server_setting

    mock_server = MagicMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = set_server_setting("test_server", "test.key", "test_val", app_context)

    assert result["status"] == "success"
    mock_server._manage_json_config.assert_called_once_with(
        "test.key", "write", "test_val"
    )


def test_set_server_custom_value_success(app_context, monkeypatch):
    """Test custom section configuration correctly delegates to BedrockServer layer."""
    from bedrock_server_manager.api.server import set_server_custom_value

    mock_server = MagicMock()
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = set_server_custom_value(
        "test_server", "my_custom", "custom_val", app_context
    )

    assert result["status"] == "success"
    mock_server.set_custom_config_value.assert_called_once_with(
        "my_custom", "custom_val"
    )


def test_get_all_server_settings_success(app_context, monkeypatch):
    """Test fetching all configs correctly retrieves the underlying dict from core server."""
    from bedrock_server_manager.api.server import get_all_server_settings

    mock_server = MagicMock()
    mock_server._load_server_config.return_value = {"key1": "val1"}
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = get_all_server_settings("test_server", app_context)

    assert result["status"] == "success"
    assert result["key1"] == "val1"


def test_get_server_setting_success(app_context, monkeypatch):
    """Test grabbing a single server setting works accurately targeting core mappings."""
    from bedrock_server_manager.api.server import get_server_setting

    mock_server = MagicMock()
    mock_server._manage_json_config.return_value = "secret"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = get_server_setting("test_server", "secret.key", app_context)

    assert result["status"] == "success"
    assert result["value"] == "secret"
    mock_server._manage_json_config.assert_called_once_with("secret.key", "read")

import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.core.server.process_mixin import ServerProcessMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    ServerStartError,
    ServerNotRunningError,
    MissingArgumentError,
)


def test_is_running(app_context):
    server = app_context.get_server("test_server")
    with patch("bedrock_server_manager.core.system.base.is_server_running") as mock_is_server_running:
        mock_is_server_running.return_value = True
        assert server.is_running() is True
        mock_is_server_running.assert_called_once_with(
            server.server_name, server.server_dir, server.app_config_dir
        )


def test_is_not_running(app_context):
    server = app_context.get_server("test_server")
    with patch("bedrock_server_manager.core.system.base.is_server_running") as mock_is_server_running:
        mock_is_server_running.return_value = False
        assert server.is_running() is False
        mock_is_server_running.assert_called_once_with(
            server.server_name, server.server_dir, server.app_config_dir
        )


def test_send_command(app_context):
    server = app_context.get_server("test_server")
    with patch.object(server, "is_running", return_value=True):
        with patch.object(server.process_manager, "send_command") as mock_send:
            server.send_command("say hello")
            mock_send.assert_called_once_with(server.server_name, "say hello")


def test_send_command_not_running(app_context):
    server = app_context.get_server("test_server")
    with patch.object(server, "is_running", return_value=False):
        with pytest.raises(ServerNotRunningError):
            server.send_command("say hello")


def test_start(app_context):
    """Tests the start method."""
    server = app_context.get_server("test_server")
    with patch.object(server, "is_running", return_value=False):
        with patch.object(server.process_manager, "start_server") as mock_start:
            with patch.object(server, "set_status_in_config") as mock_set_status:
                server.start()
                mock_start.assert_called_once_with(server.server_name)
                mock_set_status.assert_any_call("STARTING")
                mock_set_status.assert_any_call("RUNNING")


def test_start_already_running(app_context):
    server = app_context.get_server("test_server")
    with patch.object(server, "is_running", return_value=True):
        with pytest.raises(ServerStartError):
            server.start()


def test_stop(app_context):
    server = app_context.get_server("test_server")
    with patch.object(server, "is_running", return_value=True):
        with patch.object(server.process_manager, "stop_server") as mock_stop:
            server.stop()
            mock_stop.assert_called_once_with(server.server_name)


@patch("bedrock_server_manager.core.system.process.get_verified_bedrock_process")
def test_get_process_info(mock_get_verified_process, app_context):
    server = app_context.get_server("test_server")
    mock_process = MagicMock()
    mock_get_verified_process.return_value = mock_process
    with patch.object(server, "_resource_monitor") as mock_monitor:
        mock_monitor.get_stats.return_value = {"cpu": 50}

        info = server.get_process_info()
        assert info == {"cpu": 50}
        mock_get_verified_process.assert_called_once_with(
            server.server_name, server.server_dir, server.app_config_dir
        )
        mock_monitor.get_stats.assert_called_once_with(mock_process)

import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.core.server.process_mixin import ServerProcessMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import (
    ServerStartError,
    ServerNotRunningError,
    MissingArgumentError,
)


def test_is_running(real_bedrock_server):
    server = real_bedrock_server
    with patch.object(server.process_manager, "get_server_process") as mock_get_process:
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_get_process.return_value = mock_process
        assert server.is_running() is True
        mock_get_process.assert_called_once_with(server.server_name)


def test_send_command(real_bedrock_server):
    server = real_bedrock_server
    with patch.object(server, "is_running", return_value=True):
        with patch.object(server.process_manager, "send_command") as mock_send:
            server.send_command("say hello")
            mock_send.assert_called_once_with(server.server_name, "say hello")


def test_send_command_not_running(real_bedrock_server):
    server = real_bedrock_server
    with patch.object(server, "is_running", return_value=False):
        with pytest.raises(ServerNotRunningError):
            server.send_command("say hello")


def test_start(real_bedrock_server):
    """Tests the start method."""
    server = real_bedrock_server
    with patch.object(server, "is_running", return_value=False):
        with patch.object(server.process_manager, "start_server") as mock_start:
            with patch.object(server, "set_status_in_config") as mock_set_status:
                server.start()
                mock_start.assert_called_once_with(server.server_name)
                mock_set_status.assert_any_call("STARTING")
                mock_set_status.assert_any_call("RUNNING")


def test_start_already_running(real_bedrock_server):
    server = real_bedrock_server
    with patch.object(server, "is_running", return_value=True):
        with pytest.raises(ServerStartError):
            server.start()


def test_stop(real_bedrock_server):
    server = real_bedrock_server
    with patch.object(server, "is_running", return_value=True):
        with patch.object(server.process_manager, "stop_server") as mock_stop:
            server.stop()
            mock_stop.assert_called_once_with(server.server_name)


@patch("bedrock_server_manager.core.system.process.get_verified_bedrock_process")
def test_get_process_info(mock_get_verified_process, real_bedrock_server):
    server = real_bedrock_server
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

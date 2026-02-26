from unittest.mock import MagicMock, mock_open, patch

import pytest

from bedrock_server_manager.error import ServerNotRunningError, ServerStartError


def test_is_running(app_context):
    server = app_context.get_server("test_server")
    with patch(
        "bedrock_server_manager.core.system.base.is_server_running"
    ) as mock_is_server_running:
        mock_is_server_running.return_value = True
        assert server.is_running() is True
        mock_is_server_running.assert_called_once_with(
            server.server_name, server.server_dir, server.app_config_dir
        )


def test_is_not_running(app_context):
    server = app_context.get_server("test_server")
    with patch(
        "bedrock_server_manager.core.system.base.is_server_running"
    ) as mock_is_server_running:
        mock_is_server_running.return_value = False
        assert server.is_running() is False
        mock_is_server_running.assert_called_once_with(
            server.server_name, server.server_dir, server.app_config_dir
        )


def test_send_command(app_context):
    server = app_context.get_server("test_server")
    mock_process = MagicMock()
    mock_process.poll.return_value = None
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.flush = MagicMock()
    server._process = mock_process

    with patch.object(server, "is_running", return_value=True):
        server.send_command("say hello")
        mock_process.stdin.write.assert_called_once_with(b"say hello\n")
        mock_process.stdin.flush.assert_called_once()


def test_send_command_not_running(app_context):
    server = app_context.get_server("test_server")
    with patch.object(server, "is_running", return_value=False):
        with pytest.raises(ServerNotRunningError):
            server.send_command("say hello")


@patch("subprocess.Popen")
@patch(
    "bedrock_server_manager.core.server.process_mixin.system_process.write_pid_to_file"
)
@patch("builtins.open", new_callable=mock_open)
def test_start(mock_file_open, mock_write_pid, mock_popen, app_context):
    """Tests the start method."""
    server = app_context.get_server("test_server")
    mock_process = MagicMock()
    mock_popen.return_value = mock_process

    with (
        patch.object(server, "is_running", return_value=False),
        patch.object(server, "set_status_in_config") as mock_set_status,
    ):

        server.start()

        mock_popen.assert_called_once()
        mock_write_pid.assert_called_once_with(
            server.get_pid_file_path(), mock_process.pid
        )
        assert server._process is mock_process
        mock_set_status.assert_any_call("STARTING")
        mock_set_status.assert_any_call("RUNNING")


def test_start_already_running(app_context):
    server = app_context.get_server("test_server")
    with patch.object(server, "is_running", return_value=True):
        with pytest.raises(ServerStartError):
            server.start()


@patch(
    "bedrock_server_manager.core.server.process_mixin.system_process.remove_pid_file_if_exists"
)
def test_stop(mock_remove_pid, app_context):
    server = app_context.get_server("test_server")
    mock_process = MagicMock()
    mock_process.poll.return_value = None
    server._process = mock_process

    with patch.object(server, "is_running", return_value=True):
        server.stop()

        mock_process.stdin.write.assert_called_once_with(b"stop\n")
        mock_process.wait.assert_called_once()
        mock_remove_pid.assert_called_once_with(server.get_pid_file_path())
        assert server._process is None


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

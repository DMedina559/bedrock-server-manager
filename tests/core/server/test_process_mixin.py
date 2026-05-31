import subprocess
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


def test_send_command(app_context, fp):
    server = app_context.get_server("test_server")

    fp.register(["test_server"])
    mock_process = subprocess.Popen(["test_server"], stdin=subprocess.PIPE)
    server._process = mock_process

    with patch.object(server, "is_running", return_value=True):
        server.send_command("say hello")
        assert mock_process.stdin.getvalue() == b"say hello\n"


def test_send_command_not_running(app_context):
    server = app_context.get_server("test_server")
    with patch.object(server, "is_running", return_value=False):
        with pytest.raises(ServerNotRunningError):
            server.send_command("say hello")


@patch(
    "bedrock_server_manager.core.server.process_mixin.system_process.write_pid_to_file"
)
@patch("builtins.open", new_callable=mock_open)
def test_start(mock_file_open, mock_write_pid, app_context, fp):
    """Tests the start method."""
    server = app_context.get_server("test_server")

    # We must register the exact command that the server attempts to launch
    expected_command = [server.bedrock_executable_path]
    fp.register(expected_command)

    with (
        patch.object(server, "is_running", return_value=False),
        patch.object(server, "set_status_in_config") as mock_set_status,
    ):

        server.start()

        assert fp.call_count(expected_command) == 1

        # Popen mock PID is usually available on the process object
        mock_write_pid.assert_called_once_with(
            server.get_pid_file_path(), server._process.pid
        )
        assert server._process is not None
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
def test_stop(mock_remove_pid, app_context, fp):
    server = app_context.get_server("test_server")

    fp.register(["test_server"])
    mock_process = subprocess.Popen(["test_server"], stdin=subprocess.PIPE)
    server._process = mock_process

    with patch.object(server, "is_running", return_value=True):
        server.stop()

        assert mock_process.stdin.getvalue() == b"stop\n"
        mock_process.wait(timeout=10)
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

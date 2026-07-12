from unittest.mock import MagicMock, patch

import pytest


def test_start_server(real_bedrock_server, fp):
    """Test starting the server."""
    server = real_bedrock_server

    with patch.object(server, "is_installed", return_value=True):
        with patch.object(server, "is_running", return_value=False):
            # fp will mock the executable path call.
            fp.register([server.bedrock_executable_path], stdout=b"server started\n")

            # Need to mock the write of PID file that happens in start()
            with patch(
                "bedrock_server_manager.core.server.process_mixin.system_process.write_pid_to_file"
            ) as mock_write_pid:
                server.start()

                # Check that process was registered as called.
                assert fp.call_count([server.bedrock_executable_path]) == 1

                mock_write_pid.assert_called_once()


def test_start_server_already_running(real_bedrock_server):
    """Test starting a server that is already running."""
    server = real_bedrock_server
    with patch.object(server, "is_running", return_value=True):
        from bedrock_server_manager.error import ServerStartError

        with pytest.raises(ServerStartError):
            server.start()


def test_stop_server(real_bedrock_server):
    """Test stopping the server."""
    server = real_bedrock_server

    with patch.object(server, "is_running", return_value=True):
        with patch(
            "bedrock_server_manager.core.server.process_mixin.system_process.remove_pid_file_if_exists"
        ) as mock_remove_pid:
            mock_proc = MagicMock()
            mock_proc.pid = 1234
            mock_proc.stdin = MagicMock()
            server._process = mock_proc

            # Mock wait to return quickly
            mock_proc.wait.return_value = 0

            server.stop()
            mock_proc.stdin.write.assert_called_with(b"stop\n")
            mock_remove_pid.assert_called_once()


def test_stop_server_already_stopped(real_bedrock_server):
    """Test stopping a server that is already stopped."""
    server = real_bedrock_server
    with patch.object(server, "is_running", return_value=False):
        # Stop on stopped server doesn't raise error, just returns early (None)
        assert server.stop() is None


def test_send_command(real_bedrock_server):
    """Test sending a command to the server."""
    server = real_bedrock_server

    with patch.object(server, "is_running", return_value=True):
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        server._process = mock_proc

        server.send_command("say hello")
        mock_proc.stdin.write.assert_called_once_with(b"say hello\n")

import os
import time
import pytest
from unittest.mock import MagicMock, patch

from bedrock_server_manager.core.bedrock_process_manager import BedrockProcessManager
from bedrock_server_manager.error import ServerNotRunningError, ServerStartError


@pytest.fixture
def manager(app_context):
    """Fixture to get a BedrockProcessManager instance and cleanup servers."""
    manager = BedrockProcessManager(app_context=app_context)
    yield manager
    # Cleanup: stop any running servers after the test
    for server_name in list(manager.servers.keys()):
        try:
            manager.stop_server(server_name)
        except ServerNotRunningError:
            continue


def test_start_server_success(manager):
    # Arrange
    server = manager.app_context.get_server("test_server")
    server_name = server.server_name

    # Act
    manager.start_server(server_name)

    # Assert
    assert server_name in manager.servers
    process = manager.servers[server_name]
    assert process.poll() is None  # Check if the process is running

    # Verify PID file is created
    pid_file_path = server.get_pid_file_path()
    assert os.path.exists(pid_file_path)
    with open(pid_file_path, "r") as f:
        pid = int(f.read())
        assert pid == process.pid


def test_start_server_already_running(manager):
    # Arrange
    server_name = "test_server"
    manager.start_server(server_name)  # Start the server once

    # Assert
    with pytest.raises(ServerStartError):
        manager.start_server(server_name)  # Try to start it again


def test_stop_server_success(manager):
    # Arrange
    server_name = "test_server"
    manager.start_server(server_name)
    assert server_name in manager.servers

    # Act
    manager.stop_server(server_name)

    # Assert
    assert server_name not in manager.servers
    assert manager.intentionally_stopped[server_name] is True


def test_stop_server_not_running(manager):
    # Arrange
    server_name = "test_server"

    # Assert
    with pytest.raises(ServerNotRunningError):
        manager.stop_server(server_name)


def test_send_command_success(manager):
    # Arrange
    server_name = "test_server"
    command = "say Hello"
    manager.start_server(server_name)

    # Act
    manager.send_command(server_name, command)

    # Assert - For now, we just check that it doesn't raise an error.
    # A more advanced test could involve checking server output.
    pass


def test_send_command_server_not_running(manager):
    # Arrange
    server_name = "test_server"
    command = "say Hello"

    # Assert
    with pytest.raises(ServerNotRunningError):
        manager.send_command(server_name, command)


def test_get_server_process(manager):
    # Arrange
    server_name = "test_server"
    manager.start_server(server_name)
    expected_process = manager.servers[server_name]

    # Act
    process = manager.get_server_process(server_name)

    # Assert
    assert process is expected_process


def test_get_server_process_not_found(manager):
    # Arrange
    server_name = "test_server"

    # Act
    process = manager.get_server_process(server_name)

    # Assert
    assert process is None


def test_server_restart_failsafe(manager):
    # Arrange
    server_name = "test_server"
    manager.failure_counts[server_name] = 3
    manager.app_context.settings.set("server.max_restarts", 3)

    with patch.object(manager, "start_server") as mock_start_server:
        # Act
        manager._try_restart_server(server_name)

        # Assert
        mock_start_server.assert_not_called()


def test_start_server_already_running_with_pid_file(manager):
    # Arrange
    server = manager.app_context.get_server("test_server")
    server_name = server.server_name
    pid_file_path = server.get_pid_file_path()

    # Create a dummy PID file to simulate a stale process
    with open(pid_file_path, "w") as f:
        f.write("12345")

    # Act & Assert
    with pytest.raises(
        ServerStartError, match=f"Server '{server_name}' has a stale PID file."
    ):
        manager.start_server(server_name)

    # Cleanup
    os.remove(pid_file_path)

import os
import time
import pytest
from unittest.mock import MagicMock, patch

from bedrock_server_manager.core.bedrock_process_manager import BedrockProcessManager
from bedrock_server_manager.error import ServerNotRunningError, ServerStartError


@pytest.fixture(autouse=True)
def reset_singleton():
    BedrockProcessManager._instance = None
    yield
    BedrockProcessManager._instance = None


def test_singleton_pattern():
    assert BedrockProcessManager() is BedrockProcessManager()


@pytest.fixture
def manager(real_bedrock_server):
    """Fixture to get a BedrockProcessManager instance and cleanup servers."""
    # The real_bedrock_server fixture is included to ensure the server files are created
    # before the manager is instantiated.
    manager = BedrockProcessManager()
    yield manager
    # Cleanup: stop any running servers after the test
    for server_name in list(manager.servers.keys()):
        try:
            manager.stop_server(server_name)
        except ServerNotRunningError:
            continue


def test_start_server_success(manager, real_bedrock_server):
    # Arrange
    server_name = real_bedrock_server.server_name

    # Act
    manager.start_server(server_name)

    # Assert
    assert server_name in manager.servers
    process = manager.servers[server_name]
    assert process.poll() is None  # Check if the process is running

    # Verify PID file is created
    pid_file_path = real_bedrock_server.get_pid_file_path()
    assert os.path.exists(pid_file_path)
    with open(pid_file_path, "r") as f:
        pid = int(f.read())
        assert pid == process.pid


def test_start_server_already_running(manager, real_bedrock_server):
    # Arrange
    server_name = real_bedrock_server.server_name
    manager.start_server(server_name)  # Start the server once

    # Assert
    with pytest.raises(ServerStartError):
        manager.start_server(server_name)  # Try to start it again


def test_stop_server_success(manager, real_bedrock_server):
    # Arrange
    server_name = real_bedrock_server.server_name
    manager.start_server(server_name)
    assert server_name in manager.servers

    # Act
    manager.stop_server(server_name)

    # Assert
    assert server_name not in manager.servers
    assert manager.intentionally_stopped[server_name] is True


def test_stop_server_not_running(manager, real_bedrock_server):
    # Arrange
    server_name = real_bedrock_server.server_name

    # Assert
    with pytest.raises(ServerNotRunningError):
        manager.stop_server(server_name)


def test_send_command_success(manager, real_bedrock_server):
    # Arrange
    server_name = real_bedrock_server.server_name
    command = "say Hello"
    manager.start_server(server_name)

    # Act
    manager.send_command(server_name, command)

    # Assert - For now, we just check that it doesn't raise an error.
    # A more advanced test could involve checking server output.
    pass


def test_send_command_server_not_running(manager, real_bedrock_server):
    # Arrange
    server_name = real_bedrock_server.server_name
    command = "say Hello"

    # Assert
    with pytest.raises(ServerNotRunningError):
        manager.send_command(server_name, command)


def test_get_server_process(manager, real_bedrock_server):
    # Arrange
    server_name = real_bedrock_server.server_name
    manager.start_server(server_name)
    expected_process = manager.servers[server_name]

    # Act
    process = manager.get_server_process(server_name)

    # Assert
    assert process is expected_process


def test_get_server_process_not_found(manager, real_bedrock_server):
    # Arrange
    server_name = real_bedrock_server.server_name

    # Act
    process = manager.get_server_process(server_name)

    # Assert
    assert process is None


def test_server_restart_failsafe(
    manager, mock_get_settings_instance, real_bedrock_server
):
    # Arrange
    server_name = real_bedrock_server.server_name
    manager.failure_counts[server_name] = 3
    mock_get_settings_instance.get.return_value = 3

    with patch.object(manager, "start_server") as mock_start_server:
        # Act
        manager._try_restart_server(server_name)

        # Assert
        mock_start_server.assert_not_called()

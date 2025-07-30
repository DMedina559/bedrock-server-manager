import pytest
from unittest.mock import MagicMock, patch, mock_open

from bedrock_server_manager.core.bedrock_process_manager import BedrockProcessManager
from bedrock_server_manager.error import ServerNotRunningError, ServerStartError


@pytest.fixture(autouse=True)
def reset_singleton():
    BedrockProcessManager._instance = None


@patch("bedrock_server_manager.core.bedrock_process_manager.threading.Thread")
def test_singleton_pattern(mock_thread):
    assert BedrockProcessManager() is BedrockProcessManager()


@pytest.fixture
def mock_get_server_instance(mocker, mock_bedrock_server):
    """Fixture to patch get_server_instance for the core.bedrock_process_manager module."""
    mock_bedrock_server.server_dir = "dummy_dir"
    mock_bedrock_server.bedrock_executable_path = "dummy_executable"
    mock_bedrock_server.get_pid_file_path.return_value = "dummy_pid_file"
    return mocker.patch(
        "bedrock_server_manager.core.bedrock_process_manager.get_server_instance",
        return_value=mock_bedrock_server,
    )


@patch("bedrock_server_manager.core.bedrock_process_manager.threading.Thread")
def test_start_server_success(mock_thread, mock_get_server_instance):
    # Arrange
    manager = BedrockProcessManager()
    server_name = "test_server"

    with (
        patch(
            "bedrock_server_manager.core.bedrock_process_manager.subprocess.Popen"
        ) as mock_popen,
        patch(
            "bedrock_server_manager.core.bedrock_process_manager.core_process.write_pid_to_file"
        ) as mock_write_pid,
        patch(
            "bedrock_server_manager.core.bedrock_process_manager.open", mock_open()
        ) as mock_file,
    ):
        # Act
        manager.start_server(server_name)

        # Assert
        assert server_name in manager.servers
        mock_popen.assert_called_once()
        mock_write_pid.assert_called_once()


@patch("bedrock_server_manager.core.bedrock_process_manager.threading.Thread")
def test_start_server_already_running(mock_thread):
    # Arrange
    manager = BedrockProcessManager()
    server_name = "test_server"
    manager.servers[server_name] = MagicMock()
    manager.servers[server_name].poll.return_value = None

    # Assert
    with pytest.raises(ServerStartError):
        manager.start_server(server_name)


@patch("bedrock_server_manager.core.bedrock_process_manager.threading.Thread")
def test_stop_server_success(mock_thread, mock_get_settings_instance):
    # Arrange
    manager = BedrockProcessManager()
    server_name = "test_server"
    mock_process = MagicMock()
    mock_process.poll.return_value = None
    manager.servers[server_name] = mock_process

    mock_get_settings_instance.get.return_value = 1

    # Act
    manager.stop_server(server_name)

    # Assert
    assert server_name not in manager.servers
    assert manager.intentionally_stopped[server_name] is True
    mock_process.stdin.write.assert_called_with(b"stop\n")
    mock_process.stdin.flush.assert_called_once()
    mock_process.wait.assert_called_once()


@patch("bedrock_server_manager.core.bedrock_process_manager.threading.Thread")
def test_stop_server_not_running(mock_thread):
    # Arrange
    manager = BedrockProcessManager()
    server_name = "test_server"

    # Assert
    with pytest.raises(ServerNotRunningError):
        manager.stop_server(server_name)


@patch("bedrock_server_manager.core.bedrock_process_manager.threading.Thread")
def test_send_command_success(mock_thread):
    # Arrange
    manager = BedrockProcessManager()
    server_name = "test_server"
    command = "say Hello"
    mock_process = MagicMock()
    mock_process.poll.return_value = None
    manager.servers[server_name] = mock_process

    # Act
    manager.send_command(server_name, command)

    # Assert
    mock_process.stdin.write.assert_called_with(f"{command}\n".encode())
    mock_process.stdin.flush.assert_called_once()


@patch("bedrock_server_manager.core.bedrock_process_manager.threading.Thread")
def test_send_command_server_not_running(mock_thread):
    # Arrange
    manager = BedrockProcessManager()
    server_name = "test_server"
    command = "say Hello"

    # Assert
    with pytest.raises(ServerNotRunningError):
        manager.send_command(server_name, command)


@patch("bedrock_server_manager.core.bedrock_process_manager.threading.Thread")
def test_get_server_process(mock_thread):
    # Arrange
    manager = BedrockProcessManager()
    server_name = "test_server"
    mock_process = MagicMock()
    manager.servers[server_name] = mock_process

    # Act
    process = manager.get_server_process(server_name)

    # Assert
    assert process == mock_process


@patch("bedrock_server_manager.core.bedrock_process_manager.threading.Thread")
def test_get_server_process_not_found(mock_thread):
    # Arrange
    manager = BedrockProcessManager()
    server_name = "test_server"

    # Act
    process = manager.get_server_process(server_name)

    # Assert
    assert process is None


@patch("bedrock_server_manager.core.bedrock_process_manager.threading.Thread")
def test_server_restart_failsafe(mock_thread, mock_get_settings_instance):
    # Arrange
    manager = BedrockProcessManager()
    server_name = "test_server"
    manager.failure_counts[server_name] = 3

    mock_get_settings_instance.get.return_value = 3

    with patch.object(manager, "start_server") as mock_start_server:
        # Act
        manager._try_restart_server(server_name)

        # Assert
        mock_start_server.assert_not_called()

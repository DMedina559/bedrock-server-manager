import time
from unittest.mock import MagicMock, patch

import pytest

from bedrock_server_manager.core.bedrock_process_manager import BedrockProcessManager
from bedrock_server_manager.error import ServerStartError


@pytest.fixture
def manager(app_context):
    """Fixture to get a BedrockProcessManager instance."""
    with patch("threading.Thread"):
        manager = BedrockProcessManager(app_context=app_context)
        yield manager


def test_add_and_remove_server(manager):
    # Arrange
    server = manager.app_context.get_server("test_server")
    # Act
    manager.add_server(server)
    # Assert
    assert "test_server" in manager.servers
    assert manager.servers["test_server"] is server
    # Act
    manager.remove_server("test_server")
    # Assert
    assert "test_server" not in manager.servers


def test_monitor_restarts_crashed_server(manager):
    # Arrange
    server = manager.app_context.get_server("test_server")
    server.intentionally_stopped = False
    manager.add_server(server)

    with (
        patch.object(server, "is_running", return_value=False),
        patch.object(server, "start") as mock_start,
    ):

        # This is a simplified version of the monitor loop for testing
        # We need to temporarily remove the while loop for testing
        original_monitor = manager._monitor_servers

        def single_pass_monitor():
            with patch("time.sleep"):  # Don't sleep in test
                for server_name, server_obj in list(manager.servers.items()):
                    if not server_obj.is_running():
                        if not server_obj.intentionally_stopped:
                            server_obj.failure_count += 1
                            manager._try_restart_server(server_obj)
                        else:
                            manager.remove_server(server_name)

        manager._monitor_servers = single_pass_monitor
        manager._monitor_servers()

        mock_start.assert_called_once()
        assert server.failure_count == 1

        manager._monitor_servers = original_monitor


def test_monitor_does_not_restart_intentional_stop(manager):
    # Arrange
    server = manager.app_context.get_server("test_server")
    server.intentionally_stopped = True
    manager.add_server(server)

    with (
        patch.object(server, "is_running", return_value=False),
        patch.object(server, "start") as mock_start,
    ):

        original_monitor = manager._monitor_servers

        def single_pass_monitor():
            with patch("time.sleep"):
                for server_name, server_obj in list(manager.servers.items()):
                    if not server_obj.is_running():
                        if not server_obj.intentionally_stopped:
                            server_obj.failure_count += 1
                            manager._try_restart_server(server_obj)
                        else:
                            manager.remove_server(server_name)

        manager._monitor_servers = single_pass_monitor
        manager._monitor_servers()

        mock_start.assert_not_called()
        assert "test_server" not in manager.servers

        manager._monitor_servers = original_monitor


def test_monitor_respects_max_retries(manager):
    # Arrange
    server = manager.app_context.get_server("test_server")
    server.intentionally_stopped = False
    server.failure_count = 3  # The server has already failed 3 times
    manager.add_server(server)
    manager.settings.set("SERVER_MAX_RESTART_RETRIES", 3)

    with (
        patch.object(server, "is_running", return_value=False),
        patch.object(server, "start") as mock_start,
        patch.object(manager, "write_error_status") as mock_write_error,
    ):

        # Simulate the monitor loop finding a crash
        server.failure_count += 1  # This increments to 4
        manager._try_restart_server(server)

        # Assert
        mock_start.assert_not_called()  # Should not be called because 4 > 3
        mock_write_error.assert_called_once_with("test_server")
        assert "test_server" not in manager.servers

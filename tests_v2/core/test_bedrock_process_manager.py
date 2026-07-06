"""
Integration tests for bedrock_server_manager/core/bedrock_process_manager.py
"""

from unittest.mock import MagicMock, patch

import pytest

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.core.bedrock_process_manager import BedrockProcessManager
from bedrock_server_manager.error import BSMError, FileOperationError


def test_process_manager_add_remove_server(app_context: AppContext):
    """Test adding and removing servers from the manager."""
    manager = BedrockProcessManager(app_context)
    mock_server = MagicMock()
    mock_server.server_name = "test_server"

    # Add server
    manager.add_server(mock_server)
    assert "test_server" in manager.servers

    # Remove server
    manager.remove_server("test_server")
    assert "test_server" not in manager.servers


def test_process_manager_shutdown(app_context: AppContext):
    """Test shutting down the process manager stops the thread."""
    manager = BedrockProcessManager(app_context)
    manager._shutdown_event = MagicMock()
    manager.monitoring_thread = MagicMock()

    manager.shutdown()

    manager._shutdown_event.set.assert_called_once()
    manager.monitoring_thread.join.assert_called_once_with(timeout=5)


def test_try_restart_server_success(app_context: AppContext):
    """Test successfully attempting to restart a server."""
    manager = BedrockProcessManager(app_context)

    with patch.object(app_context.settings, "get", return_value=3):
        mock_server = MagicMock()
        mock_server.server_name = "test_server"
        mock_server.failure_count = 1

        manager._try_restart_server(mock_server)

        # Verify the start method was called
        mock_server.start.assert_called_once()


def test_try_restart_server_max_retries_reached(app_context: AppContext):
    """Test restarting a server stops when max retries is reached."""
    manager = BedrockProcessManager(app_context)

    with patch.object(app_context.settings, "get", return_value=3):
        with patch.object(manager, "write_error_status") as mock_write_error:
            with patch.object(manager, "remove_server") as mock_remove_server:
                mock_server = MagicMock()
                mock_server.server_name = "test_server"
                # Set higher than max
                mock_server.failure_count = 4

                manager._try_restart_server(mock_server)

                # Verify start was not called
                mock_server.start.assert_not_called()

                # Verify it was marked as error and removed
                mock_write_error.assert_called_once_with("test_server")
                mock_remove_server.assert_called_once_with("test_server")


def test_write_error_status_success(app_context: AppContext):
    """Test successfully writing error status to config."""
    manager = BedrockProcessManager(app_context)

    mock_server = MagicMock()
    with patch.object(app_context, "get_server", return_value=mock_server):
        manager.write_error_status("test_server")

        mock_server.set_status_in_config.assert_called_once_with("ERROR")


def test_write_error_status_failure(app_context: AppContext):
    """Test writing error status propagating FileOperationError on internal error."""
    manager = BedrockProcessManager(app_context)

    mock_server = MagicMock()
    # Simulate a generic BSMError when setting status
    mock_server.set_status_in_config.side_effect = BSMError("Config missing")

    with patch.object(app_context, "get_server", return_value=mock_server):
        with pytest.raises(FileOperationError, match="Failed to write status"):
            manager.write_error_status("test_server")


@patch("bedrock_server_manager.core.bedrock_process_manager.mc.lookup")
def test_monitor_servers_crashed_server_detected(mock_lookup, app_context: AppContext):
    """Test monitoring detects a crashed server and attempts restart."""
    manager = BedrockProcessManager(app_context)

    # Create a server that is NOT intentionally stopped, but IS NOT running (crashed)
    mock_server = MagicMock()
    mock_server.server_name = "crashed_server"
    mock_server.intentionally_stopped = False
    mock_server.is_running.return_value = False
    mock_server.get_server_port.return_value = 19132
    mock_server.failure_count = 0

    manager.add_server(mock_server)

    # We don't want the while loop to run forever, so we fake the _shutdown_event
    # We'll make it return False once, then True so the loop exits immediately.
    # The while condition checks `not manager._shutdown_event.is_set()`
    manager._shutdown_event = MagicMock()
    # Add an extra True to avoid StopIteration if it checks again while breaking out
    manager._shutdown_event.is_set.side_effect = [False, True, True, True]
    manager._shutdown_event.wait.return_value = False  # So it doesn't break early

    with patch.object(manager, "_try_restart_server") as mock_try_restart:
        manager._monitor_servers()

        # The server should have its failure count increased and a restart attempted
        assert mock_server.failure_count == 1
        mock_try_restart.assert_called_once_with(mock_server)

        # Status lookup shouldn't be called if it's dead
        mock_lookup.assert_not_called()

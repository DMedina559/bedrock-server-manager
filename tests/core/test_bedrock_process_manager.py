"""
Integration tests for bedrock_server_manager/core/bedrock_process_manager.py
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bedrock_server_manager.context import AppContext
from bedrock_server_manager.core.bedrock_process_manager import BedrockProcessManager
from bedrock_server_manager.error import BSMError, FileOperationError


async def test_process_manager_add_remove_server(app_context: AppContext):
    """Test adding and removing servers from the manager."""
    manager = BedrockProcessManager(
        settings=app_context.settings,
        storage=app_context.storage,
        server_provider=app_context.get_server,
        api=app_context.api,
    )
    mock_server = MagicMock()
    mock_server.set_status_in_config = AsyncMock()
    mock_server.server_name = "test_server"

    # Add server
    await manager.add_server(mock_server)
    assert "test_server" in manager.servers

    # Remove server
    await manager.remove_server("test_server")
    assert "test_server" not in manager.servers


async def test_process_manager_shutdown(app_context: AppContext):
    """Test shutting down the process manager stops the thread."""
    manager = BedrockProcessManager(
        settings=app_context.settings,
        storage=app_context.storage,
        server_provider=app_context.get_server,
        api=app_context.api,
    )
    manager._shutdown_event = MagicMock()

    manager.monitoring_task = asyncio.create_task(asyncio.sleep(0))

    with patch.object(manager.settings, "get", return_value=0):
        await manager.shutdown()

    manager._shutdown_event.set.assert_called_once()
    # Task is awaited naturally


async def test_try_restart_server_success(app_context: AppContext):
    """Test successfully attempting to restart a server."""
    manager = BedrockProcessManager(
        settings=app_context.settings,
        storage=app_context.storage,
        server_provider=app_context.get_server,
        api=app_context.api,
    )

    with patch.object(app_context.settings, "get", return_value=3):
        mock_server = MagicMock()
        mock_server.start = AsyncMock()
        mock_server.server_name = "test_server"
        mock_server.failure_count = 1

        await manager._try_restart_server(mock_server)

        # Verify the start method was called
        mock_server.start.assert_awaited_once()


async def test_try_restart_server_max_retries_reached(app_context: AppContext):
    """Test restarting a server stops when max retries is reached."""
    manager = BedrockProcessManager(
        settings=app_context.settings,
        storage=app_context.storage,
        server_provider=app_context.get_server,
        api=app_context.api,
    )

    with patch.object(app_context.settings, "get", return_value=3):
        with patch.object(manager, "write_error_status") as mock_write_error:
            with patch.object(manager, "remove_server") as mock_remove_server:
                mock_server = MagicMock()
                mock_server.start = AsyncMock()
                mock_server.server_name = "test_server"
                # Set higher than max
                mock_server.failure_count = 4

                await manager._try_restart_server(mock_server)

                # Verify start was not called
                mock_server.start.assert_not_called()

                # Verify it was marked as error and removed
                mock_write_error.assert_awaited_once_with("test_server")
                mock_remove_server.assert_awaited_once_with("test_server")


async def test_write_error_status_success(app_context: AppContext):
    """Test successfully writing error status to config."""
    mock_server = MagicMock()
    mock_server.get_status_from_config = AsyncMock(return_value="STOPPED")
    mock_server._manage_json_config = AsyncMock()
    mock_server.set_status_in_config = AsyncMock()

    manager = BedrockProcessManager(
        settings=app_context.settings,
        storage=app_context.storage,
        server_provider=MagicMock(return_value=mock_server),
        api=app_context.api,
    )

    await manager.write_error_status("test_server")
    mock_server.set_status_in_config.assert_awaited_once_with("ERROR")


async def test_write_error_status_failure(app_context: AppContext):
    """Test writing error status propagating FileOperationError on internal error."""
    mock_server = MagicMock()
    mock_server.get_status_from_config = AsyncMock(return_value="STOPPED")
    mock_server._manage_json_config = AsyncMock()
    mock_server.set_status_in_config = AsyncMock(side_effect=BSMError("Config missing"))

    manager = BedrockProcessManager(
        settings=app_context.settings,
        storage=app_context.storage,
        server_provider=MagicMock(return_value=mock_server),
        api=app_context.api,
    )

    with pytest.raises(FileOperationError, match="Failed to write status"):
        await manager.write_error_status("test_server")


async def test_monitor_servers_crashed_server_detected(
    app_context: AppContext, real_bedrock_server
):
    """Test monitoring detects a crashed server and attempts restart."""
    manager = BedrockProcessManager(
        settings=app_context.settings,
        storage=app_context.storage,
        server_provider=app_context.get_server,
        api=app_context.api,
    )

    server = real_bedrock_server

    with patch.object(
        server, "is_installed", new_callable=AsyncMock, return_value=True
    ):
        await server.start()
        assert await server.is_running()

        server.intentionally_stopped = False
        server.failure_count = 0

        await manager.add_server(server)

        # Crash the server via the dummy binary's __DUMMY__ CRASH command
        await server.send_command("__DUMMY__ CRASH")

        # wait a bit for process to actually die
        for _ in range(50):
            if not await server.is_running():
                break
            await asyncio.sleep(0.1)

        assert not await server.is_running()

        # We don't want the while loop to run forever, so we fake the _shutdown_event
        # We'll make it return False once, then True so the loop exits immediately.
        # The while condition checks `not manager._shutdown_event.is_set()`
        manager._shutdown_event = MagicMock()
        # Add an extra True to avoid StopIteration if it checks again while breaking out
        manager._shutdown_event.is_set.side_effect = [
            False,
            False,
            False,
            True,
            True,
            True,
        ]
        manager._shutdown_event.wait.return_value = False  # So it doesn't break early

        # Wrap the execution in the patch.object block
        with patch.object(manager.settings, "get", return_value=0):
            with patch.object(manager, "_try_restart_server") as mock_try_restart:
                with patch.object(server, "get_server_property", return_value=19132):
                    await manager._monitor_servers()

            # The server should have its failure count increased and a restart attempted
            assert server.failure_count == 1
            mock_try_restart.assert_awaited_once_with(server)

        await server.stop()


async def test_monitor_player_failure_resets_coherent_runtime(app_context, real_bedrock_server, monkeypatch):
    server = real_bedrock_server
    server.players = [{"name": "Alex", "xuid": "1"}]
    server.is_running = AsyncMock(return_value=True)
    server.update_online_players = AsyncMock(side_effect=RuntimeError("scan failed"))
    manager = app_context.bedrock_process_manager
    manager.servers = {server.server_name: server}
    manager.player_scan_counter = 10
    manager._shutdown_event = MagicMock()
    manager._shutdown_event.is_set.side_effect = [False, False, True]
    monkeypatch.setattr(manager.settings, "get", lambda *args: 0)
    await manager._monitor_servers()
    assert server.players == []
    assert server.player_count == 0


async def test_monitor_probe_failure_does_not_stop_other_servers(app_context, monkeypatch):
    manager = app_context.bedrock_process_manager
    bad = MagicMock(is_running=AsyncMock(side_effect=RuntimeError("probe failed")))
    good = MagicMock(is_running=AsyncMock(return_value=False), intentionally_stopped=True)
    manager.servers = {"bad": bad, "good": good}
    manager._shutdown_event = MagicMock()
    manager._shutdown_event.is_set.side_effect = [False, False, True]
    monkeypatch.setattr(manager.settings, "get", lambda *args: 0)
    await manager._monitor_servers()
    good.is_running.assert_awaited_once()
    assert "good" not in manager.servers

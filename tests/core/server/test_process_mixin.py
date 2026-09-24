from unittest.mock import AsyncMock, patch

import pytest


async def test_start_server(real_bedrock_server):
    """Test starting the server asynchronously."""
    server = real_bedrock_server

    with patch.object(
        server, "is_installed", new_callable=AsyncMock
    ) as mock_is_installed:
        mock_is_installed.return_value = True
        await server.start()

        assert await server.is_running()
        assert server._process is not None
        assert server._process.returncode is None

        await server.stop()


async def test_start_server_already_running(real_bedrock_server):
    """Test starting a server asynchronously that is already running."""
    server = real_bedrock_server
    with patch.object(server, "is_running", new_callable=AsyncMock) as mock_is_running:
        mock_is_running.return_value = True
        from bedrock_server_manager.error import ServerStartError

        with pytest.raises(ServerStartError):
            await server.start()


async def test_stop_server(real_bedrock_server):
    """Test stopping the server asynchronously."""
    server = real_bedrock_server

    with patch.object(
        server, "is_installed", new_callable=AsyncMock
    ) as mock_is_installed:
        mock_is_installed.return_value = True
        await server.start()
        assert await server.is_running()

        await server.stop()

        assert not await server.is_running()
        assert server._process is None


async def test_stop_server_already_stopped(real_bedrock_server):
    """Test stopping a server asynchronously that is already stopped."""
    server = real_bedrock_server
    with patch.object(server, "is_running", new_callable=AsyncMock) as mock_is_running:
        mock_is_running.return_value = False
        # Stop on stopped server doesn't raise error, just returns early (None)
        assert await server.stop() is None


async def test_send_command(real_bedrock_server):
    """Test sending a command to the server asynchronously."""
    server = real_bedrock_server

    with patch.object(
        server, "is_installed", new_callable=AsyncMock
    ) as mock_is_installed:
        mock_is_installed.return_value = True
        await server.start()
        assert await server.is_running()

        # Send dummy command that the dummy binary can handle
        await server.send_command("__DUMMY__ PLAYER_JOIN test_user")

        await server.stop()

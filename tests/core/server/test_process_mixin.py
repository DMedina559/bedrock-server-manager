from unittest.mock import patch

import pytest


def test_start_server(real_bedrock_server):
    """Test starting the server."""
    server = real_bedrock_server

    with patch.object(server, "is_installed", return_value=True):
        server.start()

        assert server.is_running()
        assert server._process is not None
        assert server._process.poll() is None

        server.stop()


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

    with patch.object(server, "is_installed", return_value=True):
        server.start()
        assert server.is_running()

        server.stop()

        assert not server.is_running()
        assert server._process is None


def test_stop_server_already_stopped(real_bedrock_server):
    """Test stopping a server that is already stopped."""
    server = real_bedrock_server
    with patch.object(server, "is_running", return_value=False):
        # Stop on stopped server doesn't raise error, just returns early (None)
        assert server.stop() is None


def test_send_command(real_bedrock_server):
    """Test sending a command to the server."""
    server = real_bedrock_server

    with patch.object(server, "is_installed", return_value=True):
        server.start()
        assert server.is_running()

        # Send dummy command that the dummy binary can handle
        server.send_command("__DUMMY__ PLAYER_JOIN test_user")

        server.stop()


@pytest.mark.asyncio
async def test_async_start_server(real_bedrock_server):
    """Test starting the server asynchronously."""
    server = real_bedrock_server

    with patch.object(server, "async_is_installed", return_value=True):
        await server.async_start()

        assert await server.async_is_running()
        assert server._process is not None
        assert server._process.returncode is None

        await server.async_stop()


@pytest.mark.asyncio
async def test_async_start_server_already_running(real_bedrock_server):
    """Test starting a server asynchronously that is already running."""
    server = real_bedrock_server
    with patch.object(server, "async_is_running", return_value=True):
        from bedrock_server_manager.error import ServerStartError

        with pytest.raises(ServerStartError):
            await server.async_start()


@pytest.mark.asyncio
async def test_async_stop_server(real_bedrock_server):
    """Test stopping the server asynchronously."""
    server = real_bedrock_server

    with patch.object(server, "async_is_installed", return_value=True):
        await server.async_start()
        assert await server.async_is_running()

        await server.async_stop()

        assert not await server.async_is_running()
        assert server._process is None


@pytest.mark.asyncio
async def test_async_stop_server_already_stopped(real_bedrock_server):
    """Test stopping a server asynchronously that is already stopped."""
    server = real_bedrock_server
    with patch.object(server, "async_is_running", return_value=False):
        # Stop on stopped server doesn't raise error, just returns early (None)
        assert await server.async_stop() is None


@pytest.mark.asyncio
async def test_async_send_command(real_bedrock_server):
    """Test sending a command to the server asynchronously."""
    server = real_bedrock_server

    with patch.object(server, "async_is_installed", return_value=True):
        await server.async_start()
        assert await server.async_is_running()

        # Send dummy command that the dummy binary can handle
        await server.async_send_command("__DUMMY__ PLAYER_JOIN test_user")

        await server.async_stop()

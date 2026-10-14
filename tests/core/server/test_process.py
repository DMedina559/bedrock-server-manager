import asyncio

import pytest

from bedrock_server_manager.error import ServerStartError


async def test_server_lifecycle_serializes_starts_and_preserves_command_channel(
    real_bedrock_server,
):
    server = real_bedrock_server
    assert await server.is_installed()
    assert not await server.is_running()
    results = await asyncio.gather(
        server.start(), server.start(), return_exceptions=True
    )
    assert sum(isinstance(result, ServerStartError) for result in results) == 1
    assert sum(result is None for result in results) == 1
    child = server.process._process
    assert child is not None and child.returncode is None
    assert await server.is_running()
    with pytest.raises(ServerStartError):
        await server.start()
    assert server.process._process is child
    await server.send_command("__DUMMY__ PLAYER_JOIN test_user")
    await server.stop()
    assert child.returncode is not None
    assert server.process._process is None
    assert not await server.is_running()


async def test_stopping_stopped_server_is_idempotent(real_bedrock_server):
    assert await real_bedrock_server.stop() is None
    assert await real_bedrock_server.stop() is None

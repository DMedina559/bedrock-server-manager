import asyncio

import pytest

from bedrock_server_manager.error import ServerStartError


async def test_server_start_command_and_stop_use_real_process(real_bedrock_server):
    server = real_bedrock_server
    assert await server.is_installed()
    assert not await server.is_running()
    await server.start()
    child = server._process
    assert child is not None and child.returncode is None
    assert await server.is_running()
    await server.send_command("__DUMMY__ PLAYER_JOIN test_user")
    await server.stop()
    assert child.returncode is not None
    assert server._process is None
    assert not await server.is_running()


async def test_starting_live_server_is_rejected(real_bedrock_server):
    await real_bedrock_server.start()
    original = real_bedrock_server._process.pid
    with pytest.raises(ServerStartError):
        await real_bedrock_server.start()
    assert real_bedrock_server._process.pid == original


async def test_stopping_stopped_server_is_idempotent(real_bedrock_server):
    assert await real_bedrock_server.stop() is None
    assert await real_bedrock_server.stop() is None


async def test_concurrent_start_does_not_create_duplicate_process(real_bedrock_server):
    results = await asyncio.gather(
        real_bedrock_server.start(), real_bedrock_server.start(), return_exceptions=True
    )
    assert sum(isinstance(result, ServerStartError) for result in results) == 1
    assert await real_bedrock_server.is_running()
    assert real_bedrock_server._process.returncode is None

import os

from bedrock_server_manager.core.server.software import is_update_needed


async def test_is_update_needed_no_exe(real_bedrock_server):
    """Test update needed if executable doesn't exist."""
    server = real_bedrock_server
    os.remove(server.paths.bedrock_executable_path)
    assert await is_update_needed(server, "1.20.0") is True


async def test_is_update_needed_specific_version(real_bedrock_server):
    """Test update needed against specific version."""
    server = real_bedrock_server
    await server.set_version("1.19.0")
    assert await is_update_needed(server, "1.20.0") is True
    assert await is_update_needed(server, "1.19.0") is False

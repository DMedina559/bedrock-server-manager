import os
from unittest.mock import AsyncMock, patch


async def test_is_update_needed_no_exe(real_bedrock_server):
    """Test update needed if executable doesn't exist."""
    server = real_bedrock_server
    os.remove(server.bedrock_executable_path)
    assert await server.is_update_needed("1.20.0") is True


async def test_is_update_needed_specific_version(real_bedrock_server):
    """Test update needed against specific version."""
    server = real_bedrock_server
    with patch.object(
        server, "get_version", new_callable=AsyncMock, return_value="1.19.0"
    ):
        assert await server.is_update_needed("1.20.0") is True
        assert await server.is_update_needed("1.19.0") is False

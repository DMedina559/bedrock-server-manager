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


async def test_failed_release_lookup_propagates_before_update(
    real_bedrock_server, monkeypatch
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import pytest

    from bedrock_server_manager.core.server import software
    from bedrock_server_manager.error import NetworkError

    await real_bedrock_server.set_version("1.0")
    downloader = SimpleNamespace(
        get_version_for_target_spec=AsyncMock(side_effect=NetworkError("lookup failed"))
    )
    monkeypatch.setattr(software, "BedrockDownloader", lambda **kwargs: downloader)
    with pytest.raises(NetworkError):
        await is_update_needed(real_bedrock_server, "LATEST")

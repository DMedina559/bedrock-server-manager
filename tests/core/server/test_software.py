import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bedrock_server_manager.core.server import software
from bedrock_server_manager.core.server.software import is_update_needed
from bedrock_server_manager.error import NetworkError


async def test_is_update_needed_scenarios(real_bedrock_server, monkeypatch):
    """Test update checks for specific versions, failed release lookup, and missing executable."""
    server = real_bedrock_server

    await server.set_version("1.19.0")
    assert await is_update_needed(server, "1.20.0") is True
    assert await is_update_needed(server, "1.19.0") is False

    downloader = SimpleNamespace(
        get_version_for_target_spec=AsyncMock(side_effect=NetworkError("lookup failed"))
    )
    with monkeypatch.context() as fault:
        fault.setattr(software, "BedrockDownloader", lambda **kwargs: downloader)
        with pytest.raises(NetworkError):
            await is_update_needed(server, "LATEST")

    os.remove(server.paths.bedrock_executable_path)
    assert await is_update_needed(server, "1.20.0") is True

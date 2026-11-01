import os
import platform
from dataclasses import FrozenInstanceError

import pytest

from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.error import ConfigurationError, MissingArgumentError


def test_initialization_paths_and_immutability(real_bedrock_server):
    """Test initialization, executable name, paths generation, and immutability."""
    server = real_bedrock_server

    assert server.server_name == "test_server"
    assert server.settings is not None
    assert server.logger is not None
    assert "servers" in server.paths.base_dir
    assert "test_server" in server.paths.server_dir
    assert server.paths.os_type == platform.system()

    if platform.system() == "Windows":
        assert server.paths.bedrock_executable_name == "bedrock_server.exe"
    else:
        assert server.paths.bedrock_executable_name == "bedrock_server"

    assert server.paths.bedrock_executable_path == os.path.join(
        server.paths.server_dir, server.paths.bedrock_executable_name
    )
    assert server.paths.server_log_dir == os.path.join(
        server.paths.app_config_dir, "logs", "servers", "test_server"
    )
    assert server.paths.server_log_path == os.path.join(
        server.paths.server_log_dir, "server_output.log"
    )
    assert server.paths.server_properties_path == os.path.join(
        server.paths.server_dir, "server.properties"
    )
    assert server.paths.allowlist_json_path == os.path.join(
        server.paths.server_dir, "allowlist.json"
    )
    assert server.paths.permissions_json_path == os.path.join(
        server.paths.server_dir, "permissions.json"
    )
    assert server.paths.server_config_dir == os.path.join(
        server.paths.app_config_dir, "runtime", "servers", "test_server"
    )
    assert server.get_pid_file_path() == os.path.join(
        server.paths.server_config_dir, "bedrock_test_server.pid"
    )

    with pytest.raises(FrozenInstanceError):
        server.paths.server_name = "different"
    with pytest.raises(AttributeError):
        server.server_name = "different"
    assert server.paths.server_dir == server.paths.server_dir


async def test_initialization_validation_errors(app_context):
    """Test missing server name, settings, or base_dir setting raises error."""
    with pytest.raises(MissingArgumentError):
        BedrockServer(server_name="", events=app_context.events)

    with pytest.raises(ConfigurationError):
        BedrockServer(server_name="test_server", events=None)

    await app_context.settings.set("paths.servers", "")
    with pytest.raises(ConfigurationError, match="BASE_DIR not configured"):
        BedrockServer(
            server_name="test_server",
            settings=app_context.settings,
            events=app_context.events,
        )

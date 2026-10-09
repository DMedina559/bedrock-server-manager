import os
import platform

import pytest

from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.error import ConfigurationError, MissingArgumentError


def test_initialization(real_bedrock_server):
    """Test that the mixin initializes correctly with proper attributes."""
    server = real_bedrock_server

    assert server.server_name == "test_server"
    assert server.settings is not None
    assert server.logger is not None
    assert "servers" in server.paths.base_dir
    assert "test_server" in server.paths.server_dir
    assert server.paths.os_type == platform.system()


def test_missing_server_name(app_context):
    """Test that initializing without a server name raises an error."""
    with pytest.raises(MissingArgumentError):
        BedrockServer(server_name="", app_context=app_context)


def test_missing_app_context():
    """Test that initializing without an app context raises an error."""
    with pytest.raises(ConfigurationError):
        BedrockServer(server_name="test_server", app_context=None)


async def test_missing_base_dir_setting(app_context):
    """Test that missing the base directory setting raises an error."""
    await app_context.settings.set("paths.servers", "")
    with pytest.raises(ConfigurationError, match="BASE_DIR not configured"):
        BedrockServer(
            server_name="test_server",
            settings=app_context.settings,
            app_context=app_context,
        )


def test_bedrock_executable_name(real_bedrock_server):
    """Test that the executable name is set correctly based on OS."""
    server = real_bedrock_server
    if platform.system() == "Windows":
        assert server.paths.bedrock_executable_name == "bedrock_server.exe"
    else:
        assert server.paths.bedrock_executable_name == "bedrock_server"


def test_paths_generation(real_bedrock_server):
    """Test that generated paths are constructed correctly."""
    server = real_bedrock_server

    assert server.paths.bedrock_executable_path == os.path.join(
        server.paths.server_dir, server.paths.bedrock_executable_name
    )
    assert server.paths.server_log_path == os.path.join(
        server.paths.server_dir, "server_output.txt"
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
        server.paths.app_config_dir, "test_server"
    )

    pid_path = server.get_pid_file_path()
    assert pid_path == os.path.join(
        server.paths.server_config_dir, "bedrock_test_server.pid"
    )


def test_paths_and_identity_are_immutable(real_bedrock_server):
    from dataclasses import FrozenInstanceError

    server = real_bedrock_server
    with pytest.raises(FrozenInstanceError):
        server.paths.server_name = "different"
    with pytest.raises(AttributeError):
        server.server_name = "different"
    assert server.paths.server_dir == server.paths.server_dir

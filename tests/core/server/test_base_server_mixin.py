import os
import platform

import pytest

from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.error import ConfigurationError, MissingArgumentError


def test_initialization(real_bedrock_server):
    """Test that the mixin initializes correctly with proper attributes."""
    server = real_bedrock_server

    assert server.server_name == "test_server"
    assert server.settings is not None
    assert server.logger is not None
    assert "servers" in server.base_dir
    assert "test_server" in server.server_dir
    assert server.os_type == platform.system()


def test_missing_server_name(app_context):
    """Test that initializing without a server name raises an error."""
    with pytest.raises(MissingArgumentError):
        BedrockServerBaseMixin(server_name="", app_context=app_context)


def test_missing_app_context():
    """Test that initializing without an app context raises an error."""
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(server_name="test_server", app_context=None)


def test_missing_base_dir_setting(app_context):
    """Test that missing the base directory setting raises an error."""
    app_context.settings.set("paths.servers", None)
    with pytest.raises(ConfigurationError, match="BASE_DIR not configured"):
        BedrockServerBaseMixin(server_name="test_server", app_context=app_context)


def test_bedrock_executable_name(real_bedrock_server):
    """Test that the executable name is set correctly based on OS."""
    server = real_bedrock_server
    if platform.system() == "Windows":
        assert server.bedrock_executable_name == "bedrock_server.exe"
    else:
        assert server.bedrock_executable_name == "bedrock_server"


def test_paths_generation(real_bedrock_server):
    """Test that generated paths are constructed correctly."""
    server = real_bedrock_server

    assert server.bedrock_executable_path == os.path.join(
        server.server_dir, server.bedrock_executable_name
    )
    assert server.server_log_path == os.path.join(
        server.server_dir, "server_output.txt"
    )
    assert server.server_properties_path == os.path.join(
        server.server_dir, "server.properties"
    )
    assert server.allowlist_json_path == os.path.join(
        server.server_dir, "allowlist.json"
    )
    assert server.permissions_json_path == os.path.join(
        server.server_dir, "permissions.json"
    )
    assert server.server_config_dir == os.path.join(
        server.app_config_dir, "test_server"
    )

    pid_path = server.get_pid_file_path()
    assert pid_path == os.path.join(server.server_config_dir, "bedrock_test_server.pid")

import pytest
import os
import platform
import tempfile
import shutil
from unittest.mock import MagicMock, patch

from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import MissingArgumentError, ConfigurationError


def test_initialization(real_bedrock_server):
    server = real_bedrock_server

    assert server.server_name == "test_server"
    assert server.settings is not None
    assert server.logger is not None
    assert "servers" in server.base_dir
    assert "test_server" in server.server_dir
    assert ".config" in server.app_config_dir
    assert server.os_type == platform.system()


def test_missing_server_name(real_bedrock_server):
    with pytest.raises(MissingArgumentError):
        BedrockServerBaseMixin(
            server_name="", settings_instance=real_bedrock_server.settings
        )


def test_missing_base_dir_setting(real_bedrock_server):
    real_bedrock_server.settings.set("paths.servers", None)
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(
            server_name="test_server", settings_instance=real_bedrock_server.settings
        )


def test_missing_config_dir_setting(real_bedrock_server, monkeypatch):
    monkeypatch.setattr(real_bedrock_server.settings, "_config_dir_path", None)
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(
            server_name="test_server", settings_instance=real_bedrock_server.settings
        )


def test_bedrock_executable_name(real_bedrock_server):
    server = real_bedrock_server
    if platform.system() == "Windows":
        assert server.bedrock_executable_name == "bedrock_server.exe"
    else:
        assert server.bedrock_executable_name == "bedrock_server"


def test_bedrock_executable_path(real_bedrock_server):
    server = real_bedrock_server
    expected_path = os.path.join(server.server_dir, server.bedrock_executable_name)
    assert server.bedrock_executable_path == expected_path


def test_server_log_path(real_bedrock_server):
    server = real_bedrock_server
    expected_path = os.path.join(server.server_dir, "server_output.txt")
    assert server.server_log_path == expected_path


def test_server_config_dir_property(real_bedrock_server):
    server = real_bedrock_server
    expected_path = os.path.join(server.app_config_dir, server.server_name)
    assert server.server_config_dir == expected_path


def test_get_pid_file_path(real_bedrock_server):
    server = real_bedrock_server
    expected_filename = f"bedrock_{server.server_name}.pid"
    expected_path = os.path.join(server.server_config_dir, expected_filename)
    assert server.get_pid_file_path() == expected_path


def test_init_no_server_name():
    with pytest.raises(MissingArgumentError):
        BedrockServerBaseMixin(server_name="", settings_instance=Settings())


def test_init_no_settings():
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(server_name="test_server", settings_instance=None)


def test_init_no_base_dir(real_bedrock_server):
    real_bedrock_server.settings.set("paths.servers", None)
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(
            server_name="test_server", settings_instance=real_bedrock_server.settings
        )


def test_init_no_app_config_dir(real_bedrock_server, monkeypatch):
    monkeypatch.setattr(real_bedrock_server.settings, "_config_dir_path", None)
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(
            server_name="test_server", settings_instance=real_bedrock_server.settings
        )


def test_server_properties_path(real_bedrock_server):
    server = real_bedrock_server
    expected_path = os.path.join(server.server_dir, "server.properties")
    assert server.server_properties_path == expected_path


def test_allowlist_json_path(real_bedrock_server):
    server = real_bedrock_server
    expected_path = os.path.join(server.server_dir, "allowlist.json")
    assert server.allowlist_json_path == expected_path


def test_permissions_json_path(real_bedrock_server):
    server = real_bedrock_server
    expected_path = os.path.join(server.server_dir, "permissions.json")
    assert server.permissions_json_path == expected_path


def test_all_cached_properties(real_bedrock_server):
    server = real_bedrock_server

    # bedrock_executable_name
    if platform.system() == "Windows":
        assert server.bedrock_executable_name == "bedrock_server.exe"
    else:
        assert server.bedrock_executable_name == "bedrock_server"

    # bedrock_executable_path
    expected_executable_path = os.path.join(
        server.server_dir, server.bedrock_executable_name
    )
    assert server.bedrock_executable_path == expected_executable_path

    # server_log_path
    expected_log_path = os.path.join(server.server_dir, "server_output.txt")
    assert server.server_log_path == expected_log_path

    # server_properties_path
    expected_properties_path = os.path.join(server.server_dir, "server.properties")
    assert server.server_properties_path == expected_properties_path

    # allowlist_json_path
    expected_allowlist_path = os.path.join(server.server_dir, "allowlist.json")
    assert server.allowlist_json_path == expected_allowlist_path

    # permissions_json_path
    expected_permissions_path = os.path.join(server.server_dir, "permissions.json")
    assert server.permissions_json_path == expected_permissions_path

    # server_config_dir
    expected_config_dir = os.path.join(server.app_config_dir, server.server_name)
    assert server.server_config_dir == expected_config_dir

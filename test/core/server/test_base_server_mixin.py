import pytest
import os
import platform
import tempfile
import shutil
from unittest.mock import MagicMock

from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import MissingArgumentError, ConfigurationError


@pytest.fixture
def base_server_mixin_fixture(mock_get_settings_instance):
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    mock_get_settings_instance.get.return_value = os.path.join(temp_dir, "servers")
    mock_get_settings_instance.config_dir = os.path.join(temp_dir, "config")
    manager_expath = "/path/to/manager"

    yield temp_dir, server_name, mock_get_settings_instance, manager_expath

    shutil.rmtree(temp_dir)


def test_initialization(base_server_mixin_fixture):
    temp_dir, server_name, settings, manager_expath = base_server_mixin_fixture
    server = BedrockServerBaseMixin(
        server_name=server_name,
        settings_instance=settings,
    )

    assert server.server_name == server_name
    assert server.settings == settings
    assert server.logger is not None
    assert server.base_dir == os.path.join(temp_dir, "servers")
    assert server.server_dir == os.path.join(temp_dir, "servers", server_name)
    assert server.app_config_dir == os.path.join(temp_dir, "config")
    assert server.os_type == platform.system()


def test_missing_server_name(base_server_mixin_fixture):
    _, _, settings, _ = base_server_mixin_fixture
    with pytest.raises(MissingArgumentError):
        BedrockServerBaseMixin(server_name="", settings_instance=settings)


def test_missing_base_dir_setting():
    settings = Settings()
    settings.set("paths.servers", None)
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(server_name="test_server", settings_instance=settings)


def test_missing_config_dir_setting(mock_get_settings_instance):
    mock_get_settings_instance.config_dir = None

    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(
            server_name="test_server", settings_instance=mock_get_settings_instance
        )


def test_bedrock_executable_name(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    server = BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)
    if platform.system() == "Windows":
        assert server.bedrock_executable_name == "bedrock_server.exe"
    else:
        assert server.bedrock_executable_name == "bedrock_server"


def test_bedrock_executable_path(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    server = BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)
    expected_path = os.path.join(server.server_dir, server.bedrock_executable_name)
    assert server.bedrock_executable_path == expected_path


def test_server_log_path(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    server = BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)
    expected_path = os.path.join(server.server_dir, "server_output.txt")
    assert server.server_log_path == expected_path


def test_server_config_dir_property(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    server = BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)
    expected_path = os.path.join(server.app_config_dir, server.server_name)
    assert server.server_config_dir == expected_path


def test_get_pid_file_path(base_server_mixin_fixture):
    _, server_name, settings, _ = base_server_mixin_fixture
    server = BedrockServerBaseMixin(server_name=server_name, settings_instance=settings)
    expected_filename = f"bedrock_{server_name}.pid"
    expected_path = os.path.join(server.server_config_dir, expected_filename)
    assert server.get_pid_file_path() == expected_path


def test_init_no_server_name():
    with pytest.raises(MissingArgumentError):
        BedrockServerBaseMixin(server_name="", settings_instance=Settings())


from unittest.mock import patch


def test_init_no_settings(monkeypatch):
    from bedrock_server_manager.core.server.base_server_mixin import (
        BedrockServerBaseMixin,
    )

    monkeypatch.setattr(
        "bedrock_server_manager.core.server.base_server_mixin.get_settings_instance",
        lambda: None,
    )
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(server_name="test_server", settings_instance=None)


def test_init_no_base_dir(mock_get_settings_instance):
    mock_get_settings_instance.get.return_value = None
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(
            server_name="test_server", settings_instance=mock_get_settings_instance
        )


def test_init_no_app_config_dir(mock_get_settings_instance):
    mock_get_settings_instance.config_dir = None
    with pytest.raises(ConfigurationError):
        BedrockServerBaseMixin(
            server_name="test_server", settings_instance=mock_get_settings_instance
        )


def test_server_properties_path(base_server_mixin_fixture):
    _, server_name, settings, manager_expath = base_server_mixin_fixture
    server = BedrockServerBaseMixin(
        server_name=server_name,
        settings_instance=settings,
    )
    expected_path = os.path.join(server.server_dir, "server.properties")
    assert server.server_properties_path == expected_path


def test_allowlist_json_path(base_server_mixin_fixture):
    _, server_name, settings, manager_expath = base_server_mixin_fixture
    server = BedrockServerBaseMixin(
        server_name=server_name,
        settings_instance=settings,
    )
    expected_path = os.path.join(server.server_dir, "allowlist.json")
    assert server.allowlist_json_path == expected_path


def test_permissions_json_path(base_server_mixin_fixture):
    _, server_name, settings, manager_expath = base_server_mixin_fixture
    server = BedrockServerBaseMixin(
        server_name=server_name,
        settings_instance=settings,
    )
    expected_path = os.path.join(server.server_dir, "permissions.json")
    assert server.permissions_json_path == expected_path


def test_all_cached_properties(base_server_mixin_fixture):
    temp_dir, server_name, settings, manager_expath = base_server_mixin_fixture
    server = BedrockServerBaseMixin(
        server_name=server_name,
        settings_instance=settings,
    )

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

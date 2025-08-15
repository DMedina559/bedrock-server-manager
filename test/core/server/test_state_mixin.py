import pytest
import os
import shutil
import tempfile
import json
from bedrock_server_manager.core.server.state_mixin import ServerStateMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.config.settings import Settings


class SetupBedrockServer(
    ServerStateMixin, ServerConfigManagementMixin, BedrockServerBaseMixin
):
    @property
    def server_config_path(self):
        return os.path.join(self.server_config_dir, "server_config.json")

    def get_server_properties_path(self):
        return os.path.join(self.server_dir, "server.properties")

    def is_running(self):
        return False


@pytest.fixture
def state_mixin_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))
    settings._config_dir_path = os.path.join(temp_dir, "config")

    server = SetupBedrockServer(server_name=server_name, settings_instance=settings)
    os.makedirs(server.server_config_dir, exist_ok=True)
    os.makedirs(server.server_dir, exist_ok=True)

    yield server, temp_dir

    shutil.rmtree(temp_dir)


from unittest.mock import patch


def test_get_status_running(state_mixin_fixture):
    server, _ = state_mixin_fixture
    with patch.object(server, "is_running", return_value=True):
        assert server.get_status() == "RUNNING"


def test_get_status_stopped(state_mixin_fixture):
    server, _ = state_mixin_fixture
    with patch.object(server, "is_running", return_value=False):
        assert server.get_status() == "STOPPED"


def test_get_status_unknown(state_mixin_fixture):
    server, _ = state_mixin_fixture
    with patch.object(server, "is_running", side_effect=Exception("error")):
        assert server.get_status() == "UNKNOWN"


def test_load_server_config_empty_file(state_mixin_fixture):
    server, _ = state_mixin_fixture
    with open(server._server_specific_json_config_file_path, "w") as f:
        f.write("")
    config = server._load_server_config()
    assert config["server_info"]["status"] == "UNKNOWN"


def test_load_server_config_corrupted_file(state_mixin_fixture):
    server, _ = state_mixin_fixture
    with open(server._server_specific_json_config_file_path, "w") as f:
        f.write("{corrupted_json}")
    config = server._load_server_config()
    assert config["server_info"]["status"] == "UNKNOWN"


def test_manage_json_config_invalid_key(state_mixin_fixture):
    server, _ = state_mixin_fixture
    assert server._manage_json_config("invalid.key", "read") is None


def test_manage_json_config_invalid_operation(state_mixin_fixture):
    server, _ = state_mixin_fixture
    with pytest.raises(Exception):
        server._manage_json_config("server_info.status", "invalid_op")


def test_set_status_in_config(state_mixin_fixture):
    server, _ = state_mixin_fixture
    server._manage_json_config("server_info.status", "write", "STOPPED")
    with open(server._server_specific_json_config_file_path, "r") as f:
        data = json.load(f)
    assert data["server_info"]["status"] == "STOPPED"


def test_get_and_set_version(state_mixin_fixture):
    server, _ = state_mixin_fixture
    server.set_version("1.2.3")
    assert server.get_version() == "1.2.3"


def test_get_and_set_target_version(state_mixin_fixture):
    server, _ = state_mixin_fixture
    server.set_target_version("LATEST")
    assert server.get_target_version() == "LATEST"


def test_get_world_name_success(state_mixin_fixture):
    server, _ = state_mixin_fixture
    with open(server.server_properties_path, "w") as f:
        f.write("level-name=MyWorld\n")
    assert server.get_world_name() == "MyWorld"


from bedrock_server_manager.error import AppFileNotFoundError, ConfigParseError


def test_get_world_name_no_properties(state_mixin_fixture):
    server, _ = state_mixin_fixture
    with pytest.raises(AppFileNotFoundError):
        server.get_world_name()


def test_get_world_name_no_level_name(state_mixin_fixture):
    server, _ = state_mixin_fixture
    with open(server.server_properties_path, "w") as f:
        f.write("other-setting=value\n")
    with pytest.raises(ConfigParseError):
        server.get_world_name()

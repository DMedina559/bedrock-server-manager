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


from unittest.mock import MagicMock


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
def state_mixin_fixture(monkeypatch):
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))
    settings._config_dir_path = os.path.join(temp_dir, "config")

    # Mock the db session
    mock_db_session = MagicMock()
    mock_session_manager = MagicMock()
    mock_session_manager.return_value.__enter__.return_value = mock_db_session
    monkeypatch.setattr(
        "bedrock_server_manager.core.server.state_mixin.db_session_manager",
        mock_session_manager,
    )

    server = SetupBedrockServer(server_name=server_name, settings_instance=settings)
    os.makedirs(server.server_config_dir, exist_ok=True)
    os.makedirs(server.server_dir, exist_ok=True)

    yield server, temp_dir, mock_db_session

    shutil.rmtree(temp_dir)


from unittest.mock import patch


def test_get_status_running(state_mixin_fixture):
    server, _, _ = state_mixin_fixture
    with patch.object(server, "is_running", return_value=True):
        assert server.get_status() == "RUNNING"


def test_get_status_stopped(state_mixin_fixture):
    server, _, _ = state_mixin_fixture
    with patch.object(server, "is_running", return_value=False):
        assert server.get_status() == "STOPPED"


def test_get_status_unknown(state_mixin_fixture):
    server, _, _ = state_mixin_fixture
    with (
        patch.object(server, "is_running", side_effect=Exception("error")),
        patch.object(server, "get_status_from_config", return_value="UNKNOWN"),
    ):
        assert server.get_status() == "UNKNOWN"


def test_manage_json_config_invalid_key(state_mixin_fixture):
    server, _, mock_db_session = state_mixin_fixture
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    assert server._manage_json_config("invalid.key", "read") is None


def test_manage_json_config_invalid_operation(state_mixin_fixture):
    server, _, _ = state_mixin_fixture
    with pytest.raises(Exception):
        server._manage_json_config("server_info.status", "invalid_op")


def test_get_and_set_version(state_mixin_fixture):
    server, _, mock_db_session = state_mixin_fixture

    # Mock the server config
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    server.set_version("1.2.3")

    # Assert that the config was saved correctly
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


def test_get_and_set_target_version(state_mixin_fixture):
    server, _, mock_db_session = state_mixin_fixture

    # Mock the server config
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    server.set_target_version("LATEST")

    # Assert that the config was saved correctly
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


def test_get_world_name_success(state_mixin_fixture):
    server, _, _ = state_mixin_fixture
    with open(server.server_properties_path, "w") as f:
        f.write("level-name=MyWorld\n")
    assert server.get_world_name() == "MyWorld"


from bedrock_server_manager.error import AppFileNotFoundError, ConfigParseError


def test_get_world_name_no_properties(state_mixin_fixture):
    server, _, _ = state_mixin_fixture
    with pytest.raises(AppFileNotFoundError):
        server.get_world_name()


def test_get_world_name_no_level_name(state_mixin_fixture):
    server, _, _ = state_mixin_fixture
    with open(server.server_properties_path, "w") as f:
        f.write("other-setting=value\n")
    with pytest.raises(ConfigParseError):
        server.get_world_name()

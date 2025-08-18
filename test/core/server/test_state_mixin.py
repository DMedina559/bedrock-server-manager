import pytest
import os
import shutil
import tempfile
import json
from unittest.mock import patch, MagicMock

from bedrock_server_manager.core.server.state_mixin import ServerStateMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import (
    UserInputError,
    AppFileNotFoundError,
    ConfigParseError,
)


def test_get_status_running(real_bedrock_server):
    server = real_bedrock_server
    with patch.object(server, "is_running", return_value=True):
        assert server.get_status() == "RUNNING"


def test_get_status_stopped(real_bedrock_server):
    server = real_bedrock_server
    with patch.object(server, "is_running", return_value=False):
        assert server.get_status() == "STOPPED"


def test_get_status_unknown(real_bedrock_server):
    server = real_bedrock_server
    with (
        patch.object(server, "is_running", side_effect=Exception("error")),
        patch.object(server, "get_status_from_config", return_value="UNKNOWN"),
    ):
        assert server.get_status() == "UNKNOWN"


def test_manage_json_config_invalid_key(real_bedrock_server, db_session):
    server = real_bedrock_server
    assert server._manage_json_config("invalid.key", "read") is None


def test_manage_json_config_invalid_operation(real_bedrock_server):
    server = real_bedrock_server
    with pytest.raises(Exception):
        server._manage_json_config("server_info.status", "invalid_op")


def test_get_and_set_version(real_bedrock_server, db_session):
    server = real_bedrock_server
    from bedrock_server_manager.db.models import Server

    server.set_version("1.2.3")

    # Assert that the config was saved correctly
    db_server = db_session.query(Server).filter_by(server_name=server.server_name).one()
    assert db_server.config["server_info"]["installed_version"] == "1.2.3"


def test_get_and_set_target_version(real_bedrock_server, db_session):
    server = real_bedrock_server
    from bedrock_server_manager.db.models import Server

    server.set_target_version("LATEST")

    # Assert that the config was saved correctly
    db_server = db_session.query(Server).filter_by(server_name=server.server_name).one()
    assert db_server.config["settings"]["target_version"] == "LATEST"


def test_get_world_name_success(real_bedrock_server):
    server = real_bedrock_server
    assert server.get_world_name() == "world"


def test_get_world_name_no_properties(real_bedrock_server):
    server = real_bedrock_server
    os.remove(server.server_properties_path)
    with pytest.raises(AppFileNotFoundError):
        server.get_world_name()


def test_get_world_name_no_level_name(real_bedrock_server):
    server = real_bedrock_server
    with open(server.server_properties_path, "w") as f:
        f.write("other-setting=value\n")
    with pytest.raises(ConfigParseError):
        server.get_world_name()

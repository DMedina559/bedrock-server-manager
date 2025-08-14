import pytest
import os
import shutil
import tempfile
from unittest.mock import patch

from bedrock_server_manager.core.server.installation_mixin import (
    ServerInstallationMixin,
)
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import AppFileNotFoundError


def test_is_installed_true(real_bedrock_server):
    server = real_bedrock_server
    assert server.is_installed() is True


def test_is_installed_false(real_bedrock_server):
    server = real_bedrock_server
    os.remove(server.bedrock_executable_path)
    assert server.is_installed() is False


def test_is_installed_dir_exists_no_exe(real_bedrock_server):
    server = real_bedrock_server
    os.remove(server.bedrock_executable_path)
    assert server.is_installed() is False


def test_validate_installation_no_dir(real_bedrock_server):
    server = real_bedrock_server
    shutil.rmtree(server.server_dir)
    with pytest.raises(AppFileNotFoundError):
        server.validate_installation()


def test_validate_installation_no_exe(real_bedrock_server):
    server = real_bedrock_server
    os.remove(server.bedrock_executable_path)
    with pytest.raises(AppFileNotFoundError):
        server.validate_installation()


def test_set_filesystem_permissions_not_installed(real_bedrock_server):
    server = real_bedrock_server
    os.remove(server.bedrock_executable_path)
    with pytest.raises(AppFileNotFoundError):
        server.set_filesystem_permissions()


def test_delete_all_data_missing_backup_dir(real_bedrock_server):
    server = real_bedrock_server
    # No exception should be raised
    with patch.object(server, "is_running", return_value=False, create=True):
        with patch.object(server, "stop", create=True):
            server.delete_all_data()

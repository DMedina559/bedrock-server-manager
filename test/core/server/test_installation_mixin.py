import pytest
import os
import shutil
import tempfile
from bedrock_server_manager.core.server.installation_mixin import (
    ServerInstallationMixin,
)
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.config.settings import Settings


class SetupBedrockServer(ServerInstallationMixin, BedrockServerBaseMixin):
    pass


@pytest.fixture
def installation_mixin_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))

    server = SetupBedrockServer(server_name=server_name, settings_instance=settings)
    os.makedirs(server.server_dir, exist_ok=True)

    yield server, temp_dir

    shutil.rmtree(temp_dir)


def test_is_installed_true(installation_mixin_fixture):
    server, _ = installation_mixin_fixture
    with open(server.bedrock_executable_path, "w") as f:
        f.write("test")
    assert server.is_installed() is True


def test_is_installed_false(installation_mixin_fixture):
    server, _ = installation_mixin_fixture
    assert server.is_installed() is False


from bedrock_server_manager.error import AppFileNotFoundError


def test_is_installed_dir_exists_no_exe(installation_mixin_fixture):
    server, _ = installation_mixin_fixture
    assert server.is_installed() is False


def test_validate_installation_no_dir(installation_mixin_fixture):
    server, _ = installation_mixin_fixture
    shutil.rmtree(server.server_dir)
    with pytest.raises(AppFileNotFoundError):
        server.validate_installation()


def test_validate_installation_no_exe(installation_mixin_fixture):
    server, _ = installation_mixin_fixture
    with pytest.raises(AppFileNotFoundError):
        server.validate_installation()


def test_set_filesystem_permissions_not_installed(installation_mixin_fixture):
    server, _ = installation_mixin_fixture
    with pytest.raises(AppFileNotFoundError):
        server.set_filesystem_permissions()


from unittest.mock import patch


def test_delete_all_data_missing_backup_dir(installation_mixin_fixture):
    server, _ = installation_mixin_fixture
    # No exception should be raised
    with patch.object(server, "is_running", return_value=False, create=True):
        server.delete_all_data()

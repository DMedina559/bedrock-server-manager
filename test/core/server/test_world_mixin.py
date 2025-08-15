import pytest
import os
import shutil
import zipfile
import tempfile
from bedrock_server_manager.core.server.world_mixin import ServerWorldMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.config.settings import Settings


class SetupBedrockServer(
    ServerWorldMixin, ServerConfigManagementMixin, BedrockServerBaseMixin
):
    def get_server_properties_path(self):
        return os.path.join(self.server_dir, "server.properties")

    def get_world_name(self):
        return "world1"


def zip_dir(path, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(path):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), path),
                )


@pytest.fixture
def world_mixin_fixture():
    temp_dir = tempfile.mkdtemp()
    server_name = "test_server"
    settings = Settings()
    settings.set("paths.servers", os.path.join(temp_dir, "servers"))
    settings._config_dir_path = os.path.join(temp_dir, "config")

    server = SetupBedrockServer(server_name=server_name, settings_instance=settings)
    os.makedirs(server.server_dir, exist_ok=True)
    os.makedirs(os.path.join(server.server_dir, "worlds", "world1"), exist_ok=True)
    os.makedirs(os.path.join(server.server_dir, "worlds", "world2"), exist_ok=True)

    yield server, temp_dir

    shutil.rmtree(temp_dir)


def test_get_worlds(world_mixin_fixture):
    # The get_worlds method is not part of the world mixin, so this test is removed.
    pass


def test_export_world_directory_to_mcworld(world_mixin_fixture):
    server, temp_dir = world_mixin_fixture
    world_name = "world1"
    output_path = os.path.join(temp_dir, "world1.mcworld")
    db_path = os.path.join(server.server_dir, "worlds", world_name, "db")
    os.makedirs(db_path)
    with open(os.path.join(db_path, "test.ldb"), "w") as f:
        f.write("test")

    server.export_world_directory_to_mcworld(world_name, output_path)
    assert os.path.exists(output_path)
    with zipfile.ZipFile(output_path, "r") as zip_ref:
        assert "db/test.ldb" in zip_ref.namelist()


from bedrock_server_manager.error import ExtractError, AppFileNotFoundError


def test_import_active_world_from_mcworld(world_mixin_fixture):
    server, temp_dir = world_mixin_fixture
    world_name = "world1"
    mcworld_path = os.path.join(temp_dir, f"{world_name}.mcworld")
    world_source_path = os.path.join(temp_dir, "world1_source")
    os.makedirs(os.path.join(world_source_path, "db"), exist_ok=True)
    with open(os.path.join(world_source_path, "test.txt"), "w") as f:
        f.write("test")
    zip_dir(world_source_path, mcworld_path)

    imported_world_name = server.import_active_world_from_mcworld(mcworld_path)
    assert imported_world_name == world_name
    assert os.path.exists(
        os.path.join(server.server_dir, "worlds", world_name, "test.txt")
    )


def test_extract_mcworld_to_directory_invalid_zip(world_mixin_fixture):
    server, temp_dir = world_mixin_fixture
    invalid_zip_path = os.path.join(temp_dir, "invalid.mcworld")
    with open(invalid_zip_path, "w") as f:
        f.write("not a zip")
    with pytest.raises(ExtractError):
        server.extract_mcworld_to_directory(invalid_zip_path, "world1")


def test_export_world_directory_to_mcworld_no_source(world_mixin_fixture):
    server, temp_dir = world_mixin_fixture
    with pytest.raises(AppFileNotFoundError):
        server.export_world_directory_to_mcworld(
            "non_existent_world", os.path.join(temp_dir, "export.mcworld")
        )


from unittest.mock import patch


def test_delete_active_world_directory_not_exist(world_mixin_fixture):
    server, _ = world_mixin_fixture
    with patch.object(server, "get_world_name", return_value="non_existent_world"):
        assert server.delete_active_world_directory() is True


def test_has_world_icon_missing(world_mixin_fixture):
    server, _ = world_mixin_fixture
    assert server.has_world_icon() is False

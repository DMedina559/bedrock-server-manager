import pytest
import os
import shutil
import zipfile
import tempfile
from unittest.mock import patch

from bedrock_server_manager.core.server.world_mixin import ServerWorldMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import ExtractError, AppFileNotFoundError


def zip_dir(path, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(path):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), path),
                )


def test_export_world_directory_to_mcworld(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    world_name = "world"
    output_path = tmp_path / "world.mcworld"
    db_path = os.path.join(server.server_dir, "worlds", world_name, "db")
    os.makedirs(db_path, exist_ok=True)
    with open(os.path.join(db_path, "test.ldb"), "w") as f:
        f.write("test")

    server.export_world_directory_to_mcworld(world_name, str(output_path))
    assert os.path.exists(output_path)
    with zipfile.ZipFile(output_path, "r") as zip_ref:
        assert "db/test.ldb" in zip_ref.namelist()


def test_import_active_world_from_mcworld(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    world_name = "world"
    mcworld_path = tmp_path / f"{world_name}.mcworld"
    world_source_path = tmp_path / "world_source"
    os.makedirs(os.path.join(world_source_path, "db"), exist_ok=True)
    with open(os.path.join(world_source_path, "test.txt"), "w") as f:
        f.write("test")
    zip_dir(world_source_path, mcworld_path)

    imported_world_name = server.import_active_world_from_mcworld(str(mcworld_path))
    assert imported_world_name == world_name
    assert os.path.exists(
        os.path.join(server.server_dir, "worlds", world_name, "test.txt")
    )


def test_extract_mcworld_to_directory_invalid_zip(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    invalid_zip_path = tmp_path / "invalid.mcworld"
    invalid_zip_path.write_text("not a zip")
    with pytest.raises(ExtractError):
        server.extract_mcworld_to_directory(str(invalid_zip_path), "world")


def test_export_world_directory_to_mcworld_no_source(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    with pytest.raises(AppFileNotFoundError):
        server.export_world_directory_to_mcworld(
            "non_existent_world", str(tmp_path / "export.mcworld")
        )


def test_delete_active_world_directory_not_exist(real_bedrock_server):
    server = real_bedrock_server
    with patch.object(server, "get_world_name", return_value="non_existent_world"):
        assert server.delete_active_world_directory() is True


def test_has_world_icon_missing(real_bedrock_server):
    server = real_bedrock_server
    assert server.has_world_icon() is False

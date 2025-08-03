import pytest
import os
import shutil
import zipfile
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from bedrock_server_manager.core.server.backup_restore_mixin import ServerBackupMixin
from bedrock_server_manager.core.server.base_server_mixin import BedrockServerBaseMixin
from bedrock_server_manager.core.server.config_management_mixin import (
    ServerConfigManagementMixin,
)
from bedrock_server_manager.config.settings import Settings
from bedrock_server_manager.error import UserInputError, AppFileNotFoundError


def test_backup_all_data(real_bedrock_server):
    server = real_bedrock_server
    world_dir = os.path.join(server.server_dir, "worlds", "world")
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "test.txt"), "w") as f:
        f.write("test content")

    with patch(
        "bedrock_server_manager.core.server.world_mixin.ServerWorldMixin.export_world_directory_to_mcworld"
    ) as mock_export:
        results = server.backup_all_data()
        assert results["world"] is not None
        mock_export.assert_called_once()

    # Create a dummy backup file to be found by list_backups
    backup_dir = server.server_backup_directory
    os.makedirs(backup_dir, exist_ok=True)
    (Path(backup_dir) / "world_backup_test.mcworld").touch()

    backups = server.list_backups("all")
    assert "world_backups" in backups
    assert len(backups["world_backups"]) == 1
    assert os.path.basename(backups["world_backups"][0]).startswith("world_backup_")


def test_list_backups(real_bedrock_server):
    server = real_bedrock_server
    backup_dir = server.server_backup_directory
    os.makedirs(backup_dir, exist_ok=True)
    (Path(backup_dir) / "world_backup_test1.mcworld").touch()
    time.sleep(0.1)
    (Path(backup_dir) / "world_backup_test2.mcworld").touch()

    backups = server.list_backups("world")
    assert len(backups) == 2
    assert "world_backup_test2.mcworld" in os.path.basename(backups[0])


def test_restore_all_data_from_latest(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    backup_dir = server.server_backup_directory
    os.makedirs(backup_dir, exist_ok=True)
    backup_file = tmp_path / "world_backup_test.mcworld"
    with zipfile.ZipFile(backup_file, "w") as zf:
        zf.writestr("test.txt", "test content")

    shutil.copy(backup_file, backup_dir)

    with patch(
        "bedrock_server_manager.core.server.world_mixin.ServerWorldMixin.import_active_world_from_mcworld"
    ) as mock_import:
        server.restore_all_data_from_latest()
        mock_import.assert_called_once()


def test_list_backups_invalid_type(real_bedrock_server):
    server = real_bedrock_server
    with pytest.raises(UserInputError):
        server.list_backups("invalid_type")


def test_backup_world_data_internal_no_world_dir(real_bedrock_server):
    server = real_bedrock_server
    with pytest.raises(AppFileNotFoundError):
        server._backup_world_data_internal()


def test_restore_config_file_internal_malformed_name(real_bedrock_server, tmp_path):
    server = real_bedrock_server
    backup_dir = server.server_backup_directory
    os.makedirs(backup_dir, exist_ok=True)
    malformed_backup_path = Path(backup_dir) / "malformed.properties"
    malformed_backup_path.touch()
    with pytest.raises(UserInputError):
        server._restore_config_file_internal(str(malformed_backup_path))


def test_restore_all_data_from_latest_no_backups(real_bedrock_server):
    server = real_bedrock_server
    results = server.restore_all_data_from_latest()
    assert results == {}

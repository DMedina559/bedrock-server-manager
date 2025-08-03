import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.backup_restore import (
    list_backup_files,
    backup_world,
    backup_config_file,
    backup_all,
    restore_all,
    restore_world,
    restore_config_file,
    prune_old_backups,
)
from bedrock_server_manager.error import AppFileNotFoundError, MissingArgumentError


@pytest.fixture
def mock_get_server_instance(mocker, mock_bedrock_server):
    """Fixture to patch get_server_instance for the api.backup_restore module."""
    return mocker.patch(
        "bedrock_server_manager.api.backup_restore.get_server_instance",
        return_value=mock_bedrock_server,
    )


import os
from pathlib import Path


class TestBackupRestore:
    def test_list_backup_files(self, real_bedrock_server):
        backup_dir = real_bedrock_server.settings.get("paths.backups")
        server_backup_dir = os.path.join(
            backup_dir, real_bedrock_server.server_name
        )
        os.makedirs(server_backup_dir, exist_ok=True)

        (Path(server_backup_dir) / "backup1.mcworld").touch()
        (Path(server_backup_dir) / "backup2.mcworld").touch()

        with patch(
            "bedrock_server_manager.api.backup_restore.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = list_backup_files("test-server", "world")
            assert result["status"] == "success"
            assert len(result["backups"]) == 2

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_backup_world(self, mock_lifecycle, real_bedrock_server):
        with patch.object(
            real_bedrock_server,
            "_backup_world_data_internal",
            return_value="world_backup.mcworld",
        ) as mock_backup:
            with patch(
                "bedrock_server_manager.api.backup_restore.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = backup_world("test-server")
                assert result["status"] == "success"
                mock_lifecycle.assert_called_once()
                mock_backup.assert_called_once()

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_backup_config_file(self, mock_lifecycle, real_bedrock_server):
        with patch.object(
            real_bedrock_server,
            "_backup_config_file_internal",
            return_value="server.properties.bak",
        ) as mock_backup:
            with patch(
                "bedrock_server_manager.api.backup_restore.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = backup_config_file("test-server", "server.properties")
                assert result["status"] == "success"
                mock_lifecycle.assert_called_once()
                mock_backup.assert_called_once_with("server.properties")

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_backup_all(self, mock_lifecycle, real_bedrock_server):
        with patch.object(
            real_bedrock_server,
            "backup_all_data",
            return_value={"world": "world.mcworld"},
        ) as mock_backup:
            with patch(
                "bedrock_server_manager.api.backup_restore.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = backup_all("test-server")
                assert result["status"] == "success"
                mock_lifecycle.assert_called_once()
                mock_backup.assert_called_once()

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_restore_all(self, mock_lifecycle, real_bedrock_server):
        with patch.object(
            real_bedrock_server,
            "restore_all_data_from_latest",
            return_value={"world": "world.mcworld"},
        ) as mock_restore:
            with patch(
                "bedrock_server_manager.api.backup_restore.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = restore_all("test-server")
                assert result["status"] == "success"
                mock_lifecycle.assert_called_once()
                mock_restore.assert_called_once()

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_restore_world(self, mock_lifecycle, real_bedrock_server, tmp_path):
        backup_file = tmp_path / "world.mcworld"
        backup_file.touch()

        with patch.object(
            real_bedrock_server, "import_active_world_from_mcworld"
        ) as mock_import:
            with patch(
                "bedrock_server_manager.api.backup_restore.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = restore_world("test-server", str(backup_file))
                assert result["status"] == "success"
                mock_lifecycle.assert_called_once()
                mock_import.assert_called_once_with(str(backup_file))

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_restore_config_file(self, mock_lifecycle, real_bedrock_server, tmp_path):
        backup_file = tmp_path / "server.properties.bak"
        backup_file.touch()

        with patch.object(
            real_bedrock_server,
            "_restore_config_file_internal",
            return_value="server.properties",
        ) as mock_restore:
            with patch(
                "bedrock_server_manager.api.backup_restore.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = restore_config_file("test-server", str(backup_file))
                assert result["status"] == "success"
                mock_lifecycle.assert_called_once()
                mock_restore.assert_called_once_with(str(backup_file))

    def test_prune_old_backups(self, real_bedrock_server):
        backup_dir = real_bedrock_server.settings.get("paths.backups")
        server_backup_dir = os.path.join(
            backup_dir, real_bedrock_server.server_name
        )
        os.makedirs(server_backup_dir, exist_ok=True)

        with patch.object(real_bedrock_server, "prune_server_backups") as mock_prune:
            with patch(
                "bedrock_server_manager.api.backup_restore.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = prune_old_backups("test-server")
                assert result["status"] == "success"
                assert mock_prune.call_count == 4

    def test_prune_old_backups_no_dir(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.api.backup_restore.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = prune_old_backups("test-server")
            assert result["status"] == "success"
            assert "No backup directory found" in result["message"]

    def test_lock_skipped(self):
        with patch(
            "bedrock_server_manager.api.backup_restore._backup_restore_lock"
        ) as mock_lock:
            mock_lock.acquire.return_value = False
            result = backup_world("test-server")
            assert result["status"] == "skipped"

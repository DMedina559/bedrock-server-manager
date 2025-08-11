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


import os
from pathlib import Path


class TestBackupRestore:
    def test_list_backup_files(self, app_context):
        server = app_context.get_server("test_server")
        backup_dir = server.server_backup_directory
        os.makedirs(backup_dir, exist_ok=True)

        (Path(backup_dir) / "backup1.mcworld").touch()
        (Path(backup_dir) / "backup2.mcworld").touch()

        result = list_backup_files("test_server", "world", app_context=app_context)
        assert result["status"] == "success"
        assert len(result["backups"]) == 2

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_backup_world(self, mock_lifecycle, app_context):
        server = app_context.get_server("test_server")
        with patch.object(
            server, "_backup_world_data_internal", return_value="world_backup.mcworld"
        ) as mock_backup:
            result = backup_world("test_server", app_context=app_context)
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()
            mock_backup.assert_called_once()

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_backup_config_file(self, mock_lifecycle, app_context):
        server = app_context.get_server("test_server")
        with patch.object(
            server, "_backup_config_file_internal", return_value="server.properties.bak"
        ) as mock_backup:
            result = backup_config_file(
                "test_server", "server.properties", app_context=app_context
            )
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()
            mock_backup.assert_called_once_with("server.properties")

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_backup_all(self, mock_lifecycle, app_context):
        server = app_context.get_server("test_server")
        with patch.object(
            server, "backup_all_data", return_value={"world": "world.mcworld"}
        ) as mock_backup:
            result = backup_all("test_server", app_context=app_context)
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()
            mock_backup.assert_called_once()

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_restore_all(self, mock_lifecycle, app_context):
        server = app_context.get_server("test_server")
        with patch.object(
            server,
            "restore_all_data_from_latest",
            return_value={"world": "world.mcworld"},
        ) as mock_restore:
            result = restore_all("test_server", app_context=app_context)
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()
            mock_restore.assert_called_once()

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_restore_world(self, mock_lifecycle, app_context, tmp_path):
        server = app_context.get_server("test_server")
        backup_file = tmp_path / "world.mcworld"
        backup_file.touch()

        with patch.object(server, "import_active_world_from_mcworld") as mock_import:
            result = restore_world(
                "test_server", str(backup_file), app_context=app_context
            )
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()
            mock_import.assert_called_once_with(str(backup_file))

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_restore_config_file(self, mock_lifecycle, app_context, tmp_path):
        server = app_context.get_server("test_server")
        backup_file = tmp_path / "server.properties.bak"
        backup_file.touch()

        with patch.object(
            server, "_restore_config_file_internal", return_value="server.properties"
        ) as mock_restore:
            result = restore_config_file(
                "test_server", str(backup_file), app_context=app_context
            )
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()
            mock_restore.assert_called_once_with(str(backup_file))

    def test_prune_old_backups(self, app_context):
        server = app_context.get_server("test_server")
        backup_dir = server.server_backup_directory
        os.makedirs(backup_dir, exist_ok=True)

        with patch.object(server, "prune_server_backups") as mock_prune:
            result = prune_old_backups("test_server", app_context=app_context)
            assert result["status"] == "success"
            assert mock_prune.call_count == 4

    def test_prune_old_backups_no_dir(self, app_context):
        result = prune_old_backups("test_server", app_context=app_context)
        assert result["status"] == "success"
        assert "No backup directory found" in result["message"]

    def test_lock_skipped(self, app_context):
        with patch(
            "bedrock_server_manager.api.backup_restore._backup_restore_lock"
        ) as mock_lock:
            mock_lock.acquire.return_value = False
            result = backup_world("test_server", app_context=app_context)
            assert result["status"] == "skipped"

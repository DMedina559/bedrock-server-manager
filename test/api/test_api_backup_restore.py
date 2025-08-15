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

    def test_backup_world(self, app_context):
        server = app_context.get_server("test_server")
        world_dir = os.path.join(server.server_dir, "worlds", "world")
        os.makedirs(world_dir)
        (Path(world_dir) / "level.dat").touch()

        result = backup_world(
            "test_server", stop_start_server=False, app_context=app_context
        )
        assert result["status"] == "success"

    def test_backup_config_file(self, app_context):
        server = app_context.get_server("test_server")
        (Path(server.server_dir) / "server.properties").touch()

        result = backup_config_file(
            "test_server",
            "server.properties",
            stop_start_server=False,
            app_context=app_context,
        )
        assert result["status"] == "success"

    def test_backup_all(self, app_context):
        server = app_context.get_server("test_server")
        world_dir = os.path.join(server.server_dir, "worlds", "world")
        os.makedirs(world_dir)
        (Path(world_dir) / "level.dat").touch()
        (Path(server.server_dir) / "server.properties").touch()

        result = backup_all(
            "test_server", stop_start_server=False, app_context=app_context
        )
        assert result["status"] == "success"

    def test_restore_all(self, app_context):
        server = app_context.get_server("test_server")
        backup_dir = server.server_backup_directory
        os.makedirs(backup_dir, exist_ok=True)

        world_backup_file = Path(backup_dir) / "world_backup_20230101_000000.mcworld"
        with open(world_backup_file, "wb") as f:
            import zipfile

            with zipfile.ZipFile(f, "w") as zf:
                zf.writestr("test.txt", "test")

        (
            Path(backup_dir) / "server.properties_backup_20230101_000000.properties"
        ).touch()

        result = restore_all(
            "test_server", stop_start_server=False, app_context=app_context
        )
        assert result["status"] == "success"

    def test_restore_world(self, app_context, tmp_path):
        server = app_context.get_server("test_server")
        backup_file = tmp_path / "world.mcworld"
        with open(backup_file, "wb") as f:
            import zipfile

            with zipfile.ZipFile(f, "w") as zf:
                zf.writestr("test.txt", "test")

        result = restore_world(
            "test_server",
            str(backup_file),
            stop_start_server=False,
            app_context=app_context,
        )
        assert result["status"] == "success"

    def test_restore_config_file(self, app_context, tmp_path):
        server = app_context.get_server("test_server")
        backup_file = tmp_path / "server.properties_backup_20230101_000000.properties"
        backup_file.touch()

        result = restore_config_file(
            "test_server",
            str(backup_file),
            stop_start_server=False,
            app_context=app_context,
        )
        assert result["status"] == "success"

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

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
def mock_bedrock_server():
    """Fixture for a mocked BedrockServer."""
    server = MagicMock()
    server.server_name = "test-server"
    return server


@pytest.fixture
def mock_get_server_instance(mock_bedrock_server):
    """Fixture to patch get_server_instance."""
    with patch(
        "bedrock_server_manager.api.backup_restore.get_server_instance",
        return_value=mock_bedrock_server,
    ) as mock:
        yield mock


@pytest.fixture
def temp_backup_file(tmp_path):
    """Creates a temporary backup file for tests."""
    backup_file = tmp_path / "backup.zip"
    backup_file.touch()
    return str(backup_file)


class TestBackupRestore:
    def test_list_backup_files(self, mock_get_server_instance, mock_bedrock_server):
        mock_bedrock_server.list_backups.return_value = ["backup1.zip", "backup2.zip"]
        result = list_backup_files("test-server", "world")
        assert result["status"] == "success"
        assert result["backups"] == ["backup1.zip", "backup2.zip"]

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_backup_world(
        self, mock_lifecycle, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server._backup_world_data_internal.return_value = (
            "world_backup.mcworld"
        )
        result = backup_world("test-server")
        assert result["status"] == "success"
        mock_lifecycle.assert_called_once()
        mock_bedrock_server._backup_world_data_internal.assert_called_once()

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_backup_config_file(
        self, mock_lifecycle, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server._backup_config_file_internal.return_value = (
            "server.properties.bak"
        )
        result = backup_config_file("test-server", "server.properties")
        assert result["status"] == "success"
        mock_lifecycle.assert_called_once()
        mock_bedrock_server._backup_config_file_internal.assert_called_once_with(
            "server.properties"
        )

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_backup_all(
        self, mock_lifecycle, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.backup_all_data.return_value = {"world": "world.mcworld"}
        result = backup_all("test-server")
        assert result["status"] == "success"
        mock_lifecycle.assert_called_once()
        mock_bedrock_server.backup_all_data.assert_called_once()

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_restore_all(
        self, mock_lifecycle, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.restore_all_data_from_latest.return_value = {
            "world": "world.mcworld"
        }
        result = restore_all("test-server")
        assert result["status"] == "success"
        mock_lifecycle.assert_called_once()
        mock_bedrock_server.restore_all_data_from_latest.assert_called_once()

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_restore_world(
        self,
        mock_lifecycle,
        mock_get_server_instance,
        mock_bedrock_server,
        temp_backup_file,
    ):
        result = restore_world("test-server", temp_backup_file)
        assert result["status"] == "success"
        mock_lifecycle.assert_called_once()
        mock_bedrock_server.import_active_world_from_mcworld.assert_called_once_with(
            temp_backup_file
        )

    @patch("bedrock_server_manager.api.backup_restore.server_lifecycle_manager")
    def test_restore_config_file(
        self,
        mock_lifecycle,
        mock_get_server_instance,
        mock_bedrock_server,
        temp_backup_file,
    ):
        mock_bedrock_server._restore_config_file_internal.return_value = (
            "server.properties"
        )
        result = restore_config_file("test-server", temp_backup_file)
        assert result["status"] == "success"
        mock_lifecycle.assert_called_once()
        mock_bedrock_server._restore_config_file_internal.assert_called_once_with(
            temp_backup_file
        )

    def test_prune_old_backups(self, mock_get_server_instance, mock_bedrock_server):
        mock_bedrock_server.server_backup_directory = "/backup/dir"
        mock_bedrock_server.get_world_name.return_value = "world"
        with patch("os.path.isdir", return_value=True):
            result = prune_old_backups("test-server")
            assert result["status"] == "success"
            assert mock_bedrock_server.prune_server_backups.call_count == 4

    def test_prune_old_backups_no_dir(
        self, mock_get_server_instance, mock_bedrock_server
    ):
        mock_bedrock_server.server_backup_directory = "/backup/dir"
        with patch("os.path.isdir", return_value=False):
            result = prune_old_backups("test-server")
            assert result["status"] == "success"
            assert "No backup directory found" in result["message"]

    def test_lock_skipped(self, temp_backup_file):
        with patch(
            "bedrock_server_manager.api.backup_restore._backup_restore_lock"
        ) as mock_lock:
            mock_lock.acquire.return_value = False
            result = backup_world("test-server")
            assert result["status"] == "skipped"

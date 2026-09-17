"""
Integration tests for the API functions in bedrock_server_manager/api/backup_restore.py.
"""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from bedrock_server_manager.api.backup_restore import (
    backup_all,
    backup_config_file,
    backup_world,
    list_backup_files,
    prune_old_backups,
    restore_all,
    restore_config_file,
    restore_world,
)
from bedrock_server_manager.context import AppContext
from bedrock_server_manager.error import InvalidServerNameError, MissingArgumentError


async def test_list_backup_files_success(real_bedrock_server, app_context: AppContext):
    """Test successfully listing backup files."""
    real_bedrock_server.list_backups = AsyncMock(return_value=["world_backup.mcworld"])

    result = await list_backup_files("test_server", "world", app_context)

    assert result["status"] == "success"
    assert result["backups"] == ["world_backup.mcworld"]


async def test_list_backup_files_empty_server(app_context: AppContext):
    """Test listing backup files with empty server name raises error."""
    with pytest.raises(InvalidServerNameError):
        await list_backup_files("", "world", app_context)


async def test_backup_world_success(real_bedrock_server, app_context: AppContext):
    """Test successfully backing up a world."""
    real_bedrock_server._backup_world_data_internal = AsyncMock(
        return_value="/path/to/backup.mcworld"
    )

    with patch(
        "bedrock_server_manager.api.backup_restore.server_lifecycle_manager"
    ) as mock_lifecycle:
        # We simulate the context manager doing nothing (yielding None)
        mock_lifecycle.return_value.__enter__.return_value = None
        result = await backup_world("test_server", app_context, stop_start_server=True)

        assert result["status"] == "success"
        assert "created successfully" in result["message"]
        real_bedrock_server._backup_world_data_internal.assert_called_once()
        mock_lifecycle.assert_called_once_with(
            "test_server", True, app_context=app_context
        )


async def test_backup_world_missing_server(app_context: AppContext):
    """Test missing server argument returns a skipped or error via MissingArgumentError internal catching."""
    # Since backup_world acquires a lock and then checks server_name, we just call it with empty string
    with pytest.raises(MissingArgumentError):
        await backup_world("", app_context)


async def test_backup_config_file_success(real_bedrock_server, app_context: AppContext):
    """Test backing up a config file successfully."""
    real_bedrock_server._backup_config_file_internal = AsyncMock(
        return_value="/path/to/backup.properties"
    )

    with patch(
        "bedrock_server_manager.api.backup_restore.server_lifecycle_manager"
    ) as mock_lifecycle:
        mock_lifecycle.return_value.__enter__.return_value = None
        result = await backup_config_file(
            "test_server", "server.properties", app_context, stop_start_server=False
        )

        assert result["status"] == "success"
        assert "server.properties" in result["message"]
        real_bedrock_server._backup_config_file_internal.assert_called_once_with(
            "server.properties"
        )


async def test_backup_all_success(real_bedrock_server, app_context: AppContext):
    """Test backing up all components successfully."""
    real_bedrock_server.backup_all_data = AsyncMock(
        return_value={"world": "backup.mcworld"}
    )

    with patch(
        "bedrock_server_manager.api.backup_restore.server_lifecycle_manager"
    ) as mock_lifecycle:
        mock_lifecycle.return_value.__enter__.return_value = None
        result = await backup_all("test_server", app_context)

        assert result["status"] == "success"
        assert result["details"] == {"world": "backup.mcworld"}
        real_bedrock_server.backup_all_data.assert_called_once()


async def test_restore_all_success(real_bedrock_server, app_context: AppContext):
    """Test restoring all components successfully."""
    real_bedrock_server.restore_all_data_from_latest = AsyncMock(
        return_value={"world": "restored"}
    )

    with patch(
        "bedrock_server_manager.api.backup_restore.server_lifecycle_manager"
    ) as mock_lifecycle:
        mock_lifecycle.return_value.__enter__.return_value = None
        result = await restore_all("test_server", app_context)

        assert result["status"] == "success"
        assert result["details"] == {"world": "restored"}
        real_bedrock_server.restore_all_data_from_latest.assert_called_once()


async def test_restore_world_success(real_bedrock_server, app_context: AppContext):
    """Test restoring world successfully."""
    real_bedrock_server.import_world = AsyncMock()

    with patch("os.path.isfile", return_value=True):
        with patch(
            "bedrock_server_manager.api.backup_restore.server_lifecycle_manager"
        ) as mock_lifecycle:
            mock_lifecycle.return_value.__enter__.return_value = None
            result = await restore_world(
                "test_server", "/fake/backup.mcworld", app_context
            )

            assert result["status"] == "success"
            real_bedrock_server.import_world.assert_called_once_with(
                "/fake/backup.mcworld"
            )


async def test_restore_config_file_success(
    real_bedrock_server, app_context: AppContext
):
    """Test restoring a config file successfully."""
    real_bedrock_server._restore_config_file_internal = AsyncMock(
        return_value="/path/to/server.properties"
    )

    with patch("os.path.isfile", return_value=True):
        with patch(
            "bedrock_server_manager.api.backup_restore.server_lifecycle_manager"
        ) as mock_lifecycle:
            mock_lifecycle.return_value.__enter__.return_value = None
            result = await restore_config_file(
                "test_server", "/fake/backup.properties", app_context
            )

            assert result["status"] == "success"
            real_bedrock_server._restore_config_file_internal.assert_called_once_with(
                "/fake/backup.properties"
            )


async def test_prune_old_backups_success(real_bedrock_server, app_context: AppContext):
    """Test pruning old backups successfully."""
    real_bedrock_server.get_world_name = AsyncMock(return_value="Bedrock level")
    real_bedrock_server.prune_server_backups = AsyncMock()

    with patch("os.path.isdir", return_value=True):
        # The proper way to mock a property on a mock/object when we don't care about inheritance
        # is sometimes to just patch it directly where it is called, or override it on the class.
        with patch(
            "bedrock_server_manager.core.server.backup_restore_mixin.ServerBackupMixin.server_backup_directory",
            new_callable=PropertyMock,
        ) as mock_backup_dir:
            mock_backup_dir.return_value = "/fake/backup/dir"
            result = await prune_old_backups("test_server", app_context)

            assert result["status"] == "success"
            # It should be called multiple times for world and configs
            assert real_bedrock_server.prune_server_backups.call_count == 4

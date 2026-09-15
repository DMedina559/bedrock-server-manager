from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.api.world import export_world, import_world, reset_world
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
)
from bedrock_server_manager.plugins.plugin_manager import PluginManager


async def test_export_world_success(app_context, monkeypatch):
    """Test export_world functions appropriately mapping internal core export operations."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    mock_server = MagicMock()
    mock_server.export_world = AsyncMock()
    mock_server.import_world = AsyncMock()
    mock_server.reset_world = AsyncMock()
    mock_server.delete_world = AsyncMock()
    mock_server.import_addon = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
    mock_server.enable_addon = AsyncMock()
    mock_server.disable_addon = AsyncMock()
    mock_server.update_subpack = AsyncMock()
    mock_server.remove_addon = AsyncMock()
    mock_server.reorder_addons = AsyncMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.get_world_name.return_value = "MyWorld"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Needs to bypass stop/start errors gracefully for test scope
    monkeypatch.setattr(
        "bedrock_server_manager.api.world.server_lifecycle_manager", MagicMock()
    )
    monkeypatch.setattr("os.makedirs", MagicMock())

    result = await export_world(
        "test_server",
        app_context,
        export_dir="/some/export/dir",
        stop_start_server=False,
    )

    assert result["status"] == "success"
    mock_server.export_world.assert_called_once()
    assert result["export_file"].startswith("/some/export/dir")


async def test_export_world_empty_server(app_context, monkeypatch):
    """Test export_world correctly validates bad server inputs."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    with pytest.raises(InvalidServerNameError):
        await export_world("", app_context, export_dir="/some/export/dir")


async def test_export_world_empty_dir(app_context, monkeypatch):
    """Test export_world correctly validates bad directory inputs."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    # It does not raise MissingArgumentError, it generates a path if export_dir is empty or None
    monkeypatch.setattr("os.makedirs", MagicMock())
    mock_server = MagicMock()
    mock_server.export_world = AsyncMock()
    mock_server.import_world = AsyncMock()
    mock_server.reset_world = AsyncMock()
    mock_server.delete_world = AsyncMock()
    mock_server.import_addon = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
    mock_server.enable_addon = AsyncMock()
    mock_server.disable_addon = AsyncMock()
    mock_server.update_subpack = AsyncMock()
    mock_server.remove_addon = AsyncMock()
    mock_server.reorder_addons = AsyncMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.get_world_name.return_value = "MyWorld"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)
    monkeypatch.setattr(
        "bedrock_server_manager.api.world.server_lifecycle_manager", MagicMock()
    )

    result = await export_world("test_server", app_context, export_dir="")
    assert result["status"] == "success"


async def test_export_world_bsmerror(app_context, monkeypatch):
    """Test export_world catches and maps specific core operation errors safely."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    mock_server = MagicMock()
    mock_server.export_world = AsyncMock()
    mock_server.import_world = AsyncMock()
    mock_server.reset_world = AsyncMock()
    mock_server.delete_world = AsyncMock()
    mock_server.import_addon = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
    mock_server.enable_addon = AsyncMock()
    mock_server.disable_addon = AsyncMock()
    mock_server.update_subpack = AsyncMock()
    mock_server.remove_addon = AsyncMock()
    mock_server.reorder_addons = AsyncMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.get_world_name.side_effect = BSMError("Cannot find world files")
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)
    monkeypatch.setattr("os.makedirs", MagicMock())

    result = await export_world(
        "test_server", app_context, export_dir="/some/export/dir"
    )
    assert result["status"] == "error"
    assert "Cannot find world files" in result["message"]


async def test_import_world_success(app_context, monkeypatch):
    """Test import_world coordinates the BedrockServer core replacing existing active world."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    mock_server = MagicMock()
    mock_server.export_world = AsyncMock()
    mock_server.import_world = AsyncMock()
    mock_server.reset_world = AsyncMock()
    mock_server.delete_world = AsyncMock()
    mock_server.import_addon = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
    mock_server.enable_addon = AsyncMock()
    mock_server.disable_addon = AsyncMock()
    mock_server.update_subpack = AsyncMock()
    mock_server.remove_addon = AsyncMock()
    mock_server.reorder_addons = AsyncMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.import_world = AsyncMock()
    mock_server.import_world.return_value = "ImportedWorld"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Mocking os.path.isfile
    monkeypatch.setattr("os.path.isfile", lambda x: True)
    # Needs to bypass stop/start errors gracefully for test scope
    monkeypatch.setattr(
        "bedrock_server_manager.api.world.server_lifecycle_manager", MagicMock()
    )

    result = await import_world(
        "test_server", "/path/backup.mcworld", app_context, stop_start_server=False
    )

    assert result["status"] == "success"
    assert "ImportedWorld" in result["message"]
    mock_server.import_world.assert_called_once_with("/path/backup.mcworld")


async def test_import_world_empty_server(app_context, monkeypatch):
    """Test import_world correctly validates bad server inputs."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    with pytest.raises(InvalidServerNameError):
        await import_world("", "/some/import/dir", app_context)


async def test_import_world_empty_dir(app_context, monkeypatch):
    """Test import_world correctly validates bad directory inputs."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    with pytest.raises(MissingArgumentError):
        await import_world("test_server", "", app_context)


async def test_reset_world_success(app_context, monkeypatch):
    """Test reset_world effectively deletes world dictating a clean generation on next start."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    mock_server = MagicMock()
    mock_server.export_world = AsyncMock()
    mock_server.import_world = AsyncMock()
    mock_server.reset_world = AsyncMock()
    mock_server.delete_world = AsyncMock()
    mock_server.import_addon = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
    mock_server.enable_addon = AsyncMock()
    mock_server.disable_addon = AsyncMock()
    mock_server.update_subpack = AsyncMock()
    mock_server.remove_addon = AsyncMock()
    mock_server.reorder_addons = AsyncMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.get_world_name.return_value = "TargetWorld"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Needs to bypass stop/start errors gracefully for test scope
    monkeypatch.setattr(
        "bedrock_server_manager.api.world.server_lifecycle_manager", MagicMock()
    )

    result = await reset_world("test_server", app_context)

    assert result["status"] == "success"
    mock_server.delete_world.assert_called_once()
    assert "reset successfully" in result["message"]


async def test_reset_world_empty_server(app_context, monkeypatch):
    """Test reset_world correctly validates bad server inputs."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    with pytest.raises(InvalidServerNameError):
        await reset_world("", app_context)

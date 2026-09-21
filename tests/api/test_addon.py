import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from bedrock_server_manager.api.addon import (
    disable_addon,
    enable_addon,
    import_addon,
    list_available_addons,
    list_installed_addons,
    reorder_addons,
    uninstall_addon,
    update_subpack,
)
from bedrock_server_manager.error import MissingArgumentError


async def test_import_addon_success(app_context, tmp_path, monkeypatch):
    """Test importing an addon returns success status."""
    mock_process = AsyncMock()
    mock_server = AsyncMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
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
    mock_server.process_addon_file.side_effect = mock_process.side_effect
    mock_server.process_addon_file.return_value = mock_process.return_value
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    addon_file = tmp_path / "addon.mcpack"
    addon_file.touch()

    result = await import_addon(
        "test_server", str(addon_file), stop_start_server=False, app_context=app_context
    )

    assert result["status"] == "success"
    mock_server.process_addon_file.assert_called_once_with(str(addon_file))


async def test_import_addon_error(app_context, tmp_path, monkeypatch):
    """Test importing an addon returns error status on exception."""
    mock_process = AsyncMock(side_effect=Exception("Failed extracting"))
    mock_server = AsyncMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
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
    mock_server.process_addon_file.side_effect = mock_process.side_effect
    mock_server.process_addon_file.return_value = mock_process.return_value
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    addon_file = tmp_path / "addon.mcpack"
    addon_file.touch()

    result = await import_addon(
        "test_server", str(addon_file), stop_start_server=False, app_context=app_context
    )

    assert result["status"] == "error"
    assert "Failed extracting" in result["message"]


async def test_import_addon_missing_args(app_context):
    """Test import_addon validates missing server names and paths."""
    with pytest.raises(MissingArgumentError):
        await import_addon("", "path", app_context=app_context)
    with pytest.raises(MissingArgumentError):
        await import_addon("server", "", app_context=app_context)


async def test_import_addon_lock_skipped(app_context, tmp_path, monkeypatch):
    """Test import_addon correctly skips if the lock is held."""
    addon_file = tmp_path / "addon.mcpack"
    addon_file.touch()

    mock_lock = MagicMock()
    mock_lock.acquire = AsyncMock(side_effect=asyncio.TimeoutError)
    mock_lock.acquire.return_value = False
    monkeypatch.setattr("bedrock_server_manager.api.addon._addon_lock", mock_lock)

    result = await import_addon("test_server", str(addon_file), app_context=app_context)
    assert result["status"] == "skipped"


async def test_list_available_addons_success(app_context, monkeypatch):
    """Test listing available addons from content directory successfully."""
    monkeypatch.setattr(
        "bedrock_server_manager.api.addon.list_content_files",
        AsyncMock(return_value=["addon1.mcpack", "addon2.mcaddon"]),
    )

    result = await list_available_addons(app_context)
    assert result["status"] == "success"
    assert len(result["files"]) == 2


async def test_list_installed_addons_success(app_context, monkeypatch):
    """Test listing installed addons delegates correctly."""
    mock_list = MagicMock(return_value={"behavior_packs": []})
    mock_server = MagicMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
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
    mock_server.list_installed_addons.side_effect = mock_list.side_effect
    mock_server.list_installed_addons.return_value = mock_list.return_value
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    result = await list_installed_addons("test_server", app_context)
    assert result["status"] == "success"
    assert "addons" in result


async def test_enable_addon_success(app_context, monkeypatch):
    """Test enabling an addon handles locks and triggers successfully."""
    mock_server = MagicMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
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
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # We must mock server_lifecycle_manager to not raise errors if context isnt fully ready
    monkeypatch.setattr(
        "bedrock_server_manager.api.addon.server_lifecycle_manager", MagicMock()
    )

    result = await enable_addon("test_server", "uuid1", "behavior_packs", app_context)
    assert result["status"] == "success"
    mock_server.enable_addon.assert_called_once()


async def test_disable_addon_success(app_context, monkeypatch):
    """Test disabling an addon handles locks and triggers successfully."""
    mock_server = MagicMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
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
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    monkeypatch.setattr(
        "bedrock_server_manager.api.addon.server_lifecycle_manager", MagicMock()
    )

    result = await disable_addon("test_server", "uuid1", "behavior_packs", app_context)
    assert result["status"] == "success"
    mock_server.disable_addon.assert_called_once()


async def test_update_subpack_success(app_context, monkeypatch):
    """Test updating subpack works properly via server class."""
    mock_server = MagicMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
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
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    monkeypatch.setattr(
        "bedrock_server_manager.api.addon.server_lifecycle_manager", MagicMock()
    )

    result = await update_subpack(
        "test_server", "uuid1", "behavior_packs", "new_folder", app_context
    )
    assert result["status"] == "success"
    mock_server.update_subpack.assert_called_once()


async def test_uninstall_addon_success(app_context, monkeypatch):
    """Test uninstalling an addon functions successfully."""
    mock_server = MagicMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
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
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    monkeypatch.setattr(
        "bedrock_server_manager.api.addon.server_lifecycle_manager", MagicMock()
    )

    result = await uninstall_addon(
        "test_server", "uuid1", "behavior_packs", app_context
    )
    assert result["status"] == "success"
    mock_server.remove_addon.assert_called_once()


async def test_reorder_addons_success(app_context, monkeypatch):
    """Test reordering addons delegates to the server core efficiently."""
    mock_server = MagicMock()
    mock_server.process_addon_file = AsyncMock()
    mock_server.list_installed_addons = AsyncMock()
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
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    monkeypatch.setattr(
        "bedrock_server_manager.api.addon.server_lifecycle_manager", MagicMock()
    )

    result = await reorder_addons(
        "test_server", ["uuid2", "uuid1"], "behavior_packs", app_context
    )
    assert result["status"] == "success"
    mock_server.reorder_addons.assert_called_once()

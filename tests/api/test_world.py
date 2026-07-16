from unittest.mock import MagicMock

import pytest

from bedrock_server_manager.api.world import export_world, import_world, reset_world
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
)
from bedrock_server_manager.plugins.plugin_manager import PluginManager


def test_export_world_success(app_context, monkeypatch):
    """Test export_world functions appropriately mapping internal core export operations."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    mock_server = MagicMock()
    mock_server.get_world_name.return_value = "MyWorld"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Needs to bypass stop/start errors gracefully for test scope
    monkeypatch.setattr(
        "bedrock_server_manager.api.world.server_lifecycle_manager", MagicMock()
    )
    monkeypatch.setattr("os.makedirs", MagicMock())

    result = export_world(
        "test_server",
        app_context,
        export_dir="/some/export/dir",
        stop_start_server=False,
    )

    assert result["status"] == "success"
    mock_server.export_world.assert_called_once()
    assert result["export_file"].startswith("/some/export/dir")


def test_export_world_empty_server(app_context, monkeypatch):
    """Test export_world correctly validates bad server inputs."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    with pytest.raises(InvalidServerNameError):
        export_world("", app_context, export_dir="/some/export/dir")


def test_export_world_empty_dir(app_context, monkeypatch):
    """Test export_world correctly validates bad directory inputs."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    # It does not raise MissingArgumentError, it generates a path if export_dir is empty or None
    monkeypatch.setattr("os.makedirs", MagicMock())
    mock_server = MagicMock()
    mock_server.get_world_name.return_value = "MyWorld"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)
    monkeypatch.setattr(
        "bedrock_server_manager.api.world.server_lifecycle_manager", MagicMock()
    )

    result = export_world("test_server", app_context, export_dir="")
    assert result["status"] == "success"


def test_export_world_bsmerror(app_context, monkeypatch):
    """Test export_world catches and maps specific core operation errors safely."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    mock_server = MagicMock()
    mock_server.get_world_name.side_effect = BSMError("Cannot find world files")
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)
    monkeypatch.setattr("os.makedirs", MagicMock())

    result = export_world("test_server", app_context, export_dir="/some/export/dir")
    assert result["status"] == "error"
    assert "Cannot find world files" in result["message"]


def test_import_world_success(app_context, monkeypatch):
    """Test import_world coordinates the BedrockServer core replacing existing active world."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    mock_server = MagicMock()
    mock_server.import_world.return_value = "ImportedWorld"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Mocking os.path.isfile
    monkeypatch.setattr("os.path.isfile", lambda x: True)
    # Needs to bypass stop/start errors gracefully for test scope
    monkeypatch.setattr(
        "bedrock_server_manager.api.world.server_lifecycle_manager", MagicMock()
    )

    result = import_world(
        "test_server", "/path/backup.mcworld", app_context, stop_start_server=False
    )

    assert result["status"] == "success"
    assert "ImportedWorld" in result["message"]
    mock_server.import_world.assert_called_once_with("/path/backup.mcworld")


def test_import_world_empty_server(app_context, monkeypatch):
    """Test import_world correctly validates bad server inputs."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    with pytest.raises(InvalidServerNameError):
        import_world("", "/some/import/dir", app_context)


def test_import_world_empty_dir(app_context, monkeypatch):
    """Test import_world correctly validates bad directory inputs."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    with pytest.raises(MissingArgumentError):
        import_world("test_server", "", app_context)


def test_reset_world_success(app_context, monkeypatch):
    """Test reset_world effectively deletes world dictating a clean generation on next start."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    mock_server = MagicMock()
    mock_server.get_world_name.return_value = "TargetWorld"
    monkeypatch.setattr(app_context, "get_server", lambda x: mock_server)

    # Needs to bypass stop/start errors gracefully for test scope
    monkeypatch.setattr(
        "bedrock_server_manager.api.world.server_lifecycle_manager", MagicMock()
    )

    result = reset_world("test_server", app_context)

    assert result["status"] == "success"
    mock_server.delete_world.assert_called_once()
    assert "reset successfully" in result["message"]


def test_reset_world_empty_server(app_context, monkeypatch):
    """Test reset_world correctly validates bad server inputs."""
    monkeypatch.setattr(app_context, "_plugin_manager", MagicMock(spec=PluginManager))
    with pytest.raises(InvalidServerNameError):
        reset_world("", app_context)

import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.world import (
    get_world_name,
    export_world,
    import_world,
    reset_world,
)
from bedrock_server_manager.error import (
    InvalidServerNameError,
    MissingArgumentError,
    FileOperationError,
)


class TestWorldAPI:
    def test_get_world_name(self, app_context):
        result = get_world_name("test_server", app_context=app_context)
        assert result["status"] == "success"
        assert result["world_name"] == "world"

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_export_world(self, mock_lifecycle, app_context, tmp_path):
        server = app_context.get_server("test_server")
        with patch.object(server, "export_world_directory_to_mcworld") as mock_export:
            result = export_world(
                "test_server", export_dir=str(tmp_path), app_context=app_context
            )
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()
            mock_export.assert_called_once()

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_export_world_no_dir(self, mock_lifecycle, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "export_world_directory_to_mcworld") as mock_export:
            with patch("os.makedirs"):
                result = export_world("test_server", app_context=app_context)
                assert result["status"] == "success"
                mock_lifecycle.assert_called_once()
                mock_export.assert_called_once()

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_import_world(self, mock_lifecycle, app_context, tmp_path):
        server = app_context.get_server("test_server")
        world_file = tmp_path / "world.mcworld"
        world_file.touch()

        with patch.object(server, "import_active_world_from_mcworld") as mock_import:
            with patch("os.path.isfile", return_value=True):
                result = import_world(
                    "test_server", str(world_file), app_context=app_context
                )
                assert result["status"] == "success"
                mock_lifecycle.assert_called_once()
                mock_import.assert_called_once_with(str(world_file))

    def test_import_world_no_file(self, app_context):
        result = import_world(
            "test_server", "/non/existent/file.mcworld", app_context=app_context
        )
        assert result["status"] == "error"
        assert "file not found" in result["message"].lower()

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_reset_world(self, mock_lifecycle, app_context):
        server = app_context.get_server("test_server")
        with patch.object(server, "delete_active_world_directory") as mock_delete:
            result = reset_world("test_server", app_context=app_context)
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()
            mock_delete.assert_called_once()

    def test_invalid_server_name(self, app_context):
        with pytest.raises(InvalidServerNameError):
            get_world_name("", app_context=app_context)

    def test_lock_skipped(self, app_context):
        with patch("bedrock_server_manager.api.world._world_lock") as mock_lock:
            mock_lock.acquire.return_value = False
            result = export_world("test_server", app_context=app_context)
            assert result["status"] == "skipped"

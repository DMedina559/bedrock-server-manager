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


@pytest.fixture
def mock_get_server_instance(mocker, mock_bedrock_server):
    """Fixture to patch get_server_instance for the api.world module."""
    mock_bedrock_server.get_world_name.return_value = "world"
    return mocker.patch(
        "bedrock_server_manager.api.world.get_server_instance",
        return_value=mock_bedrock_server,
    )


class TestWorldAPI:
    def test_get_world_name(self, real_bedrock_server):
        with patch(
            "bedrock_server_manager.api.world.get_server_instance",
            return_value=real_bedrock_server,
        ):
            result = get_world_name("test-server")
            assert result["status"] == "success"
            assert result["world_name"] == "world"

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_export_world(self, mock_lifecycle, real_bedrock_server, tmp_path):
        with patch.object(
            real_bedrock_server, "export_world_directory_to_mcworld"
        ) as mock_export:
            with patch(
                "bedrock_server_manager.api.world.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = export_world("test-server", export_dir=str(tmp_path))
                assert result["status"] == "success"
                mock_lifecycle.assert_called_once()
                mock_export.assert_called_once()

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_export_world_no_dir(self, mock_lifecycle, real_bedrock_server):
        with patch.object(
            real_bedrock_server, "export_world_directory_to_mcworld"
        ) as mock_export:
            with patch(
                "bedrock_server_manager.api.world.get_server_instance",
                return_value=real_bedrock_server,
            ):
                with patch("os.makedirs"):
                    result = export_world("test-server")
                    assert result["status"] == "success"
                    mock_lifecycle.assert_called_once()
                    mock_export.assert_called_once()

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_import_world(self, mock_lifecycle, real_bedrock_server, tmp_path):
        world_file = tmp_path / "world.mcworld"
        world_file.touch()

        with patch.object(
            real_bedrock_server, "import_active_world_from_mcworld"
        ) as mock_import:
            with patch(
                "bedrock_server_manager.api.world.get_server_instance",
                return_value=real_bedrock_server,
            ):
                with patch("os.path.isfile", return_value=True):
                    result = import_world("test-server", str(world_file))
                    assert result["status"] == "success"
                    mock_lifecycle.assert_called_once()
                    mock_import.assert_called_once_with(str(world_file))

    def test_import_world_no_file(self, mock_get_server_instance):
        result = import_world("test-server", "/non/existent/file.mcworld")
        assert result["status"] == "error"
        assert "file not found" in result["message"].lower()

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_reset_world(self, mock_lifecycle, real_bedrock_server):
        with patch.object(
            real_bedrock_server, "delete_active_world_directory"
        ) as mock_delete:
            with patch(
                "bedrock_server_manager.api.world.get_server_instance",
                return_value=real_bedrock_server,
            ):
                result = reset_world("test-server")
                assert result["status"] == "success"
                mock_lifecycle.assert_called_once()
                mock_delete.assert_called_once()

    def test_invalid_server_name(self):
        with pytest.raises(InvalidServerNameError):
            get_world_name("")

    def test_lock_skipped(self):
        with patch("bedrock_server_manager.api.world._world_lock") as mock_lock:
            mock_lock.acquire.return_value = False
            result = export_world("test-server")
            assert result["status"] == "skipped"

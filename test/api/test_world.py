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
def mock_bedrock_server():
    """Fixture for a mocked BedrockServer."""
    server = MagicMock()
    server.get_world_name.return_value = "world"
    return server


@pytest.fixture
def mock_get_server_instance(mock_bedrock_server):
    """Fixture to patch get_server_instance."""
    with patch(
        "bedrock_server_manager.api.world.get_server_instance",
        return_value=mock_bedrock_server,
    ) as mock:
        yield mock


@pytest.fixture
def temp_world_file(tmp_path):
    """Creates a temporary world file for tests."""
    world_file = tmp_path / "world.mcworld"
    world_file.touch()
    return str(world_file)


class TestWorldAPI:
    def test_get_world_name(self, mock_get_server_instance):
        result = get_world_name("test-server")
        assert result["status"] == "success"
        assert result["world_name"] == "world"

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_export_world(
        self, mock_lifecycle, mock_get_server_instance, temp_world_file
    ):
        result = export_world("test-server", export_dir="/tmp")
        assert result["status"] == "success"
        mock_lifecycle.assert_called_once()

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_export_world_no_dir(
        self, mock_lifecycle, mock_get_server_instance, mock_get_settings_instance
    ):
        mock_get_settings_instance.get.return_value = "/content"
        with patch("os.makedirs"):
            result = export_world("test-server")
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_import_world(
        self, mock_lifecycle, mock_get_server_instance, temp_world_file
    ):
        with patch("os.path.isfile", return_value=True):
            result = import_world("test-server", temp_world_file)
            assert result["status"] == "success"
            mock_lifecycle.assert_called_once()

    def test_import_world_no_file(self, mock_get_server_instance):
        result = import_world("test-server", "/non/existent/file.mcworld")
        assert result["status"] == "error"
        assert "file not found" in result["message"].lower()

    @patch("bedrock_server_manager.api.world.server_lifecycle_manager")
    def test_reset_world(self, mock_lifecycle, mock_get_server_instance):
        result = reset_world("test-server")
        assert result["status"] == "success"
        mock_lifecycle.assert_called_once()

    def test_invalid_server_name(self):
        with pytest.raises(InvalidServerNameError):
            get_world_name("")

    def test_lock_skipped(self):
        with patch("bedrock_server_manager.api.world._world_lock") as mock_lock:
            mock_lock.acquire.return_value = False
            result = export_world("test-server")
            assert result["status"] == "skipped"

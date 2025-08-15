import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.misc import prune_download_cache
from bedrock_server_manager.error import MissingArgumentError, UserInputError


@pytest.fixture
def temp_download_dir(tmp_path):
    """Creates a temporary download directory for tests."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    return str(download_dir)


class TestPruneDownloadCache:
    @patch("bedrock_server_manager.api.misc.prune_old_downloads")
    def test_prune_download_cache_success(self, mock_prune, temp_download_dir):
        result = prune_download_cache(temp_download_dir, keep_count=2)
        assert result["status"] == "success"
        mock_prune.assert_called_once_with(
            download_dir=temp_download_dir, download_keep=2
        )

    @patch("bedrock_server_manager.api.misc.prune_old_downloads")
    @patch("bedrock_server_manager.api.misc.get_settings_instance")
    def test_prune_download_cache_default_keep(
        self, mock_get_settings, mock_prune, temp_download_dir
    ):
        mock_get_settings.return_value.get.return_value = 3
        result = prune_download_cache(temp_download_dir)
        assert result["status"] == "success"
        mock_prune.assert_called_once_with(
            download_dir=temp_download_dir, download_keep=3
        )

    def test_prune_download_cache_no_dir(self):
        result = prune_download_cache("")
        assert result["status"] == "error"
        assert "cannot be empty" in result["message"]

    def test_prune_download_cache_invalid_keep(self, temp_download_dir):
        result = prune_download_cache(temp_download_dir, keep_count=-1)
        assert result["status"] == "error"
        assert "Invalid keep_count" in result["message"]

    def test_lock_skipped(self, temp_download_dir):
        with patch("bedrock_server_manager.api.misc._misc_lock") as mock_lock:
            mock_lock.acquire.return_value = False
            result = prune_download_cache(temp_download_dir)
            assert result["status"] == "skipped"

    @patch("bedrock_server_manager.api.misc.prune_old_downloads")
    def test_prune_download_cache_exception(self, mock_prune, temp_download_dir):
        mock_prune.side_effect = Exception("Test exception")
        result = prune_download_cache(temp_download_dir)
        assert result["status"] == "error"
        assert "Test exception" in result["message"]

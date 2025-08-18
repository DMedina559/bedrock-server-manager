import pytest
from unittest.mock import patch, MagicMock

from bedrock_server_manager.api.misc import prune_download_cache
from bedrock_server_manager.error import MissingArgumentError, UserInputError


class TestPruneDownloadCache:
    @patch("bedrock_server_manager.api.misc.prune_old_downloads")
    def test_prune_download_cache_success(self, mock_prune, temp_dir, app_context):
        result = prune_download_cache(temp_dir, keep_count=2, app_context=app_context)
        assert result["status"] == "success"
        mock_prune.assert_called_once_with(download_dir=temp_dir, download_keep=2)

    @patch("bedrock_server_manager.api.misc.prune_old_downloads")
    def test_prune_download_cache_default_keep(self, mock_prune, temp_dir, app_context):
        app_context.settings.set("retention.downloads", 3)
        result = prune_download_cache(temp_dir, app_context=app_context)
        assert result["status"] == "success"
        mock_prune.assert_called_once_with(download_dir=temp_dir, download_keep=3)

    def test_prune_download_cache_no_dir(self, app_context):
        result = prune_download_cache("", app_context=app_context)
        assert result["status"] == "error"
        assert "cannot be empty" in result["message"]

    def test_prune_download_cache_invalid_keep(self, temp_dir, app_context):
        result = prune_download_cache(temp_dir, keep_count=-1, app_context=app_context)
        assert result["status"] == "error"
        assert "Invalid keep_count" in result["message"]

    def test_lock_skipped(self, temp_dir, app_context):
        with patch("bedrock_server_manager.api.misc._misc_lock") as mock_lock:
            mock_lock.acquire.return_value = False
            result = prune_download_cache(temp_dir, app_context=app_context)
            assert result["status"] == "skipped"

    @patch("bedrock_server_manager.api.misc.prune_old_downloads")
    def test_prune_download_cache_exception(self, mock_prune, temp_dir, app_context):
        mock_prune.side_effect = Exception("Test exception")
        result = prune_download_cache(temp_dir, app_context=app_context)
        assert result["status"] == "error"
        assert "Test exception" in result["message"]

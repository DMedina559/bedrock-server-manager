from unittest.mock import MagicMock

from bedrock_server_manager.api.misc import prune_download_cache
from bedrock_server_manager.error import BSMError


def test_prune_download_cache_success(app_context, monkeypatch):
    """Test prune_download_cache retrieves values correctly and dispatches."""
    mock_prune = MagicMock()
    monkeypatch.setattr(
        "bedrock_server_manager.api.misc.prune_old_downloads", mock_prune
    )

    result = prune_download_cache("/downloads", keep_count=5, app_context=app_context)

    assert result["status"] == "success"
    mock_prune.assert_called_once_with(download_dir="/downloads", download_keep=5)


def test_prune_download_cache_default_settings(app_context, monkeypatch):
    """Test prune_download_cache falls back to application settings cleanly."""
    mock_prune = MagicMock()
    monkeypatch.setattr(
        "bedrock_server_manager.api.misc.prune_old_downloads", mock_prune
    )
    app_context.settings.set("retention.downloads", 2)

    result = prune_download_cache("/downloads", app_context=app_context)

    assert result["status"] == "success"
    mock_prune.assert_called_once_with(download_dir="/downloads", download_keep=2)


def test_prune_download_cache_empty_dir():
    """Test prune_download_cache rejects missing directories."""
    # It catches MissingArgumentError internally and returns it wrapped in unexpected exception generic handler, because it is not specifically matching it
    result = prune_download_cache("")
    assert result["status"] == "error"
    assert "Download directory cannot be empty" in result["message"]


def test_prune_download_cache_negative_count(app_context):
    """Test prune_download_cache rejects negative limits."""
    result = prune_download_cache("/downloads", keep_count=-1, app_context=app_context)

    assert result["status"] == "error"
    assert "Invalid keep_count" in result["message"]


def test_prune_download_cache_locked(app_context, monkeypatch):
    """Test prune_download_cache silently skips if lock is taken."""
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = False
    monkeypatch.setattr("bedrock_server_manager.api.misc._misc_lock", mock_lock)

    result = prune_download_cache("/downloads", app_context=app_context)
    assert result["status"] == "skipped"
    assert "already in progress" in result["message"]


def test_prune_download_cache_bsm_error(app_context, monkeypatch):
    """Test prune_download_cache catches internally thrown errors formatting accurately."""
    mock_prune = MagicMock(side_effect=BSMError("File perms"))
    monkeypatch.setattr(
        "bedrock_server_manager.api.misc.prune_old_downloads", mock_prune
    )

    result = prune_download_cache("/downloads", keep_count=5, app_context=app_context)

    assert result["status"] == "error"
    assert "File perms" in result["message"]

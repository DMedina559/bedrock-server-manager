from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from bedrock_server_manager.api.misc import prune_download_cache
from bedrock_server_manager.api.models import (
    PruneDownloadCacheRequest,
)
from bedrock_server_manager.error import BSMError


async def test_prune_download_cache_success(app_context, monkeypatch):
    """Test prune_download_cache retrieves values correctly and dispatches."""
    from unittest.mock import AsyncMock

    mock_prune = AsyncMock()
    monkeypatch.setattr(
        "bedrock_server_manager.api.misc.prune_old_downloads", mock_prune
    )

    result = (
        await prune_download_cache(
            request=PruneDownloadCacheRequest(download_dir="/downloads", keep_count=5),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    mock_prune.assert_called_once_with(download_dir="/downloads", download_keep=5)


async def test_prune_download_cache_default_settings(app_context, monkeypatch):
    """Test prune_download_cache falls back to application settings cleanly."""
    from unittest.mock import AsyncMock

    mock_prune = AsyncMock()
    monkeypatch.setattr(
        "bedrock_server_manager.api.misc.prune_old_downloads", mock_prune
    )
    await app_context.settings.set("retention.downloads", 2)

    result = (
        await prune_download_cache(
            request=PruneDownloadCacheRequest(download_dir="/downloads"),
            app_context=app_context,
        )
    ).model_dump(mode="python")

    assert result["status"] == "success"
    mock_prune.assert_called_once_with(download_dir="/downloads", download_keep=2)


async def test_prune_download_cache_empty_dir():
    """Test prune_download_cache rejects missing directories."""
    # It catches MissingArgumentError internally and returns it wrapped in unexpected exception generic handler, because it is not specifically matching it
    with pytest.raises(ValidationError):
        (
            await prune_download_cache(
                request=PruneDownloadCacheRequest(download_dir="")
            )
        ).model_dump(mode="python")


async def test_prune_download_cache_negative_count(app_context):
    """Test prune_download_cache rejects negative limits."""
    with pytest.raises(ValidationError):
        (
            await prune_download_cache(
                request=PruneDownloadCacheRequest(
                    download_dir="/downloads", keep_count=-1
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")


async def test_prune_download_cache_locked(app_context, monkeypatch):
    """Test prune_download_cache silently skips if lock is taken."""
    mock_lock = MagicMock()
    import asyncio

    mock_lock.acquire = AsyncMock(side_effect=asyncio.TimeoutError())
    monkeypatch.setattr("bedrock_server_manager.api.misc._misc_lock", mock_lock)

    result = (
        await prune_download_cache(
            request=PruneDownloadCacheRequest(download_dir="/downloads"),
            app_context=app_context,
        )
    ).model_dump(mode="python")
    assert result["status"] == "skipped"
    assert "already in progress" in result["message"]


async def test_prune_download_cache_bsm_error(app_context, monkeypatch):
    """Test prune_download_cache catches internally thrown errors formatting accurately."""
    mock_prune = MagicMock(side_effect=BSMError("File perms"))
    monkeypatch.setattr(
        "bedrock_server_manager.api.misc.prune_old_downloads", mock_prune
    )

    with pytest.raises(BSMError):
        (
            await prune_download_cache(
                request=PruneDownloadCacheRequest(
                    download_dir="/downloads", keep_count=5
                ),
                app_context=app_context,
            )
        ).model_dump(mode="python")

# bedrock_server_manager/api/misc.py
"""Provides API functions for miscellaneous or global operations.

This module contains functions that are not tied to a specific server
instance, such as managing the global download cache for server executables.
Operations are designed to be thread-safe.
"""

import asyncio
import logging
from typing import Optional

from ..context import AppContext
from ..core import prune_old_downloads
from ..error import BSMError, MissingArgumentError, UserInputError
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from ..plugins.event_trigger import trigger_event
from ..utils.general import ReentrantAsyncLock
from .models.misc import (
    PruneDownloadCacheRequest,
    PruneDownloadCacheResponse,
)

logger = logging.getLogger(__name__)

# A lock to prevent race conditions during miscellaneous file operations.
_misc_lock = ReentrantAsyncLock()


@api_method("prune_download_cache")
@trigger_event(
    before="before_prune_download_cache",
    after="after_prune_download_cache",
    identity_keys=("download_dir", "keep_count"),
)
async def prune_download_cache(
    request: PruneDownloadCacheRequest, *, app_context: Optional[AppContext] = None
) -> PruneDownloadCacheResponse:
    """Prunes old downloaded server archives (.zip) in a directory.

    Accepts PruneDownloadCacheRequest and returns PruneDownloadCacheResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    download_dir = request.download_dir
    keep_count = request.keep_count
    try:
        await _misc_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "A miscellaneous file operation is already in progress. Skipping concurrent prune."
        )
        return PruneDownloadCacheResponse.model_validate(
            {"status": "skipped", "message": "A file operation is already in progress."}
        )
    try:
        if not download_dir:
            raise MissingArgumentError("Download directory cannot be empty.")
        effective_keep: int
        try:
            if keep_count is None:
                if app_context and app_context.settings:
                    settings = app_context.settings
                    keep_setting = settings.get("retention.downloads", 3)
                    effective_keep = int(keep_setting)
                else:
                    effective_keep = 3
            else:
                effective_keep = int(keep_count)
            if effective_keep < 0:
                raise ValueError("Keep count cannot be negative")
        except (TypeError, ValueError) as e:
            raise UserInputError(
                f"Invalid keep_count or DOWNLOAD_KEEP setting: {e}"
            ) from e
        logger.debug(
            "Pruning download cache directory '%s'. Keep: %s",
            download_dir,
            effective_keep,
        )
        try:
            await prune_old_downloads(
                download_dir=download_dir, download_keep=effective_keep
            )
            logger.info("Pruning successful for directory '%s'.", download_dir)
            return PruneDownloadCacheResponse.model_validate(
                {
                    "status": "success",
                    "message": f"Download cache pruned successfully for '{download_dir}'.",
                }
            )
        except BSMError as e:
            log_operation_error(
                logger,
                "Failed to prune download cache '%s': %s",
                download_dir,
                e,
                error=e,
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error pruning download cache '%s': %s",
                download_dir,
                e,
                error=e,
            )
            raise
    except UserInputError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error in prune_download_cache: %s", e, error=e
        )
        raise
    finally:
        _misc_lock.release()

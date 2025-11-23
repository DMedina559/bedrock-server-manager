# bedrock_server_manager/api/misc.py
"""Provides API functions for miscellaneous or global operations.

This module contains functions that are not tied to a specific server
instance, such as managing the global download cache for server executables.
Operations are designed to be thread-safe.
"""

import logging
import threading
from typing import Dict, Optional

# Plugin system imports to bridge API functionality.
from ..plugins import plugin_method

# Local application imports.
from ..core import prune_old_downloads
from ..error import (
    BSMError,
    UserInputError,
    MissingArgumentError,
)
from ..plugins.event_trigger import trigger_plugin_event
from ..context import AppContext

logger = logging.getLogger(__name__)

# A lock to prevent race conditions during miscellaneous file operations.
_misc_lock = threading.Lock()


@plugin_method("prune_download_cache")
@trigger_plugin_event(
    before="before_prune_download_cache", after="after_prune_download_cache"
)
def prune_download_cache(
    download_dir: str,
    keep_count: Optional[int] = None,
    app_context: Optional[AppContext] = None,
) -> Dict[str, str]:
    """Prunes old downloaded server archives (.zip) in a directory.

    This function removes older ``bedrock-server-*.zip`` archive files from the
    specified `download_dir`, keeping a specified number of the most recent
    files. It delegates the actual pruning logic to
    :func:`~bedrock_server_manager.core.downloader.prune_old_downloads`.

    The operation uses a non-blocking lock (``_misc_lock``) to ensure thread
    safety; if another pruning operation is in progress, this call will be
    skipped, returning a "skipped" status.
    Triggers ``before_prune_download_cache`` and ``after_prune_download_cache`` plugin events.

    Args:
        download_dir (str): The path to the directory containing the downloaded
            server archives.
        keep_count (Optional[int], optional): The number of recent archives to keep.
            If ``None``, the value from the global application setting
            ``retention.downloads`` (defaulting to 3 if not set) is used.
            Defaults to ``None``.

    Returns:
        Dict[str, str]: A dictionary with the operation result.
        Possible statuses: "success", "error", or "skipped" (if lock not acquired).
        Example: ``{"status": "success", "message": "Download cache pruned..."}``

    Raises:
        MissingArgumentError: If `download_dir` is not provided.
        UserInputError: If `keep_count` (or the ``retention.downloads`` setting)
            is not a valid non-negative integer.
        BSMError: Can be raised by the underlying prune operation for issues like
            :class:`~.error.AppFileNotFoundError` (if `download_dir` is invalid after initial checks)
            or :class:`~.error.FileOperationError`.
    """
    # Attempt to acquire the lock without blocking. If another operation
    # is in progress, skip this one to avoid conflicts.
    if not _misc_lock.acquire(blocking=False):
        logger.warning(
            "A miscellaneous file operation is already in progress. Skipping concurrent prune."
        )
        return {
            "status": "skipped",
            "message": "A file operation is already in progress.",
        }

    try:
        if not download_dir:
            raise MissingArgumentError("Download directory cannot be empty.")

        effective_keep: int
        try:
            # Determine the number of files to keep, prioritizing the function
            # argument over the global setting.
            if keep_count is None:
                settings = app_context.settings
                keep_setting = settings.get("retention.downloads", 3)
                effective_keep = int(keep_setting)
            else:
                effective_keep = int(keep_count)

            if effective_keep < 0:
                raise ValueError("Keep count cannot be negative")

        except (TypeError, ValueError) as e:
            # Catch errors from invalid settings or user input.
            raise UserInputError(
                f"Invalid keep_count or DOWNLOAD_KEEP setting: {e}"
            ) from e

        logger.info(
            f"API: Pruning download cache directory '{download_dir}'. Keep: {effective_keep}"
        )

        try:
            # Delegate the actual file deletion to the core downloader module.
            prune_old_downloads(download_dir=download_dir, download_keep=effective_keep)

            logger.info(f"API: Pruning successful for directory '{download_dir}'.")
            return {
                "status": "success",
                "message": f"Download cache pruned successfully for '{download_dir}'.",
            }

        except BSMError as e:
            # Handle application-specific errors during pruning.
            logger.error(
                f"API: Failed to prune download cache '{download_dir}': {e}",
                exc_info=True,
            )
            return {"status": "error", "message": f"Failed to prune downloads: {e}"}
        except Exception as e:
            # Handle any other unexpected errors.
            logger.error(
                f"API: Unexpected error pruning download cache '{download_dir}': {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "message": f"Unexpected error pruning downloads: {e}",
            }

    except UserInputError as e:
        # Handle the validation error for keep_count from the outer try block.
        return {"status": "error", "message": str(e)}

    finally:
        # Ensure the lock is always released, even if errors occur.
        _misc_lock.release()

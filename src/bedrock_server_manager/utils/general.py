# bedrock_server_manager/utils/general.py
"""
Provides general utility functions for the application.

Includes startup checks, timestamp generation, and interactive prompts.
"""

import logging
import os
import sys
from datetime import datetime
from typing import List, Optional

from ..context import AppContext
from ..core.system import find_files
from ..error import AppFileNotFoundError, FileOperationError

logger = logging.getLogger(__name__)


def startup_checks(
    app_context: AppContext,
    app_name: Optional[str] = None,
    version: Optional[str] = "0.0.0",
) -> None:
    """
    Performs initial checks and setup when the application starts.

    - Verifies Python version compatibility (>= 3.11).
    - Creates essential application directories based on settings.
    - Note: colorama initialization is no longer needed as `click.secho` handles it.

    Args:
        app_name: The name of the application to display in logs.
        version: The version of the application to display in logs.
    """
    # Python Version Check
    if sys.version_info < (3, 11):
        message = "Python version 3.11 or later is required. You are running {}.{}.{}.".format(
            sys.version_info.major, sys.version_info.minor, sys.version_info.micro
        )
        logger.critical(message)
        # Raising an exception is the correct way to halt execution on a critical failure.
        raise RuntimeError(message)

    settings = app_context.settings

    # Ensure essential directories exist
    dirs_to_create = {
        "BASE_DIR": settings.get("paths.servers"),
        "CONTENT_DIR": settings.get("paths.content"),
        "WORLDS_SUBDIR": (
            os.path.join(str(settings.get("paths.content")), "worlds")
            if settings.get("paths.content")
            else None
        ),
        "ADDONS_SUBDIR": (
            os.path.join(str(settings.get("paths.content")), "addons")
            if settings.get("paths.content")
            else None
        ),
        "DOWNLOAD_DIR": settings.get("paths.downloads"),
        "PLUGIN_DIR": settings.get("paths.plugins"),
        "BACKUP_DIR": settings.get("paths.backups"),
        "LOG_DIR": settings.get("paths.logs"),
    }

    logger.debug("Insuring essential directories exist...")

    for name, dir_path in dirs_to_create.items():
        if dir_path and isinstance(dir_path, str):
            try:
                os.makedirs(dir_path, exist_ok=True)
                # logger.debug(f"Ensured directory exists: {dir_path} (Setting: {name})")
            except OSError as e:
                logger.error(
                    f"Failed to create directory {dir_path}: {e}", exc_info=True
                )
        elif not dir_path:
            logger.warning(
                f"Directory path for '{name}' is missing in settings. Skipping creation."
            )

    logger.debug("Startup checks completed.")


def get_timestamp() -> str:
    """
    Generates a timestamp string suitable for filenames or logging.

    Returns:
        str: The current timestamp in YYYYMMDD_HHMMSS format.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # logger.debug(f"Generated timestamp: {timestamp}")
    return timestamp


def list_content_files(
    content_dir: str | None, sub_folder: str, extensions: List[str]
) -> List[str]:
    """
    Internal helper to list files with specified extensions from a sub-folder
    within the global content directory.
    """
    if not content_dir or not os.path.isdir(content_dir):
        raise AppFileNotFoundError(str(content_dir), "Content directory")

    target_dir = os.path.join(content_dir, sub_folder)
    if not os.path.isdir(target_dir):
        logger.debug(
            f"BSM: Content sub-directory '{target_dir}' not found. Returning empty list."
        )
        return []

    found_files: List[str] = []
    try:
        for ext in extensions:
            pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            files = find_files(target_dir, pattern=pattern)
            found_files.extend(os.path.abspath(str(f)) for f in files)
    except OSError as e:
        raise FileOperationError(
            f"Error scanning content directory {target_dir}: {e}"
        ) from e
    return sorted(list(set(found_files)))

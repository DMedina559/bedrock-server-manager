# bedrock_server_manager/utils/general.py
"""
Provides general utility functions for the application.

Includes startup checks, timestamp generation, and interactive prompts.
"""

import sys
import os
import logging
from datetime import datetime
from typing import Optional


from ..context import AppContext


logger = logging.getLogger(__name__)


def startup_checks(
    app_context: AppContext,
    app_name: Optional[str] = "BedrockServerManager",
    version: Optional[str] = "0.0.0",
) -> None:
    """
    Performs initial checks and setup when the application starts.

    - Verifies Python version compatibility (>= 3.10).
    - Creates essential application directories based on settings.
    - Note: colorama initialization is no longer needed as `click.secho` handles it.

    Args:
        app_name: The name of the application to display in logs.
        version: The version of the application to display in logs.
    """
    # Python Version Check
    if sys.version_info < (3, 10):
        message = "Python version 3.10 or later is required. You are running {}.{}.{}.".format(
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

    for name, dir_path in dirs_to_create.items():
        if dir_path and isinstance(dir_path, str):
            try:
                os.makedirs(dir_path, exist_ok=True)
                logger.debug(f"Ensured directory exists: {dir_path} (Setting: {name})")
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
    logger.debug(f"Generated timestamp: {timestamp}")
    return timestamp

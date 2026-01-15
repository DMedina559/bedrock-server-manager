# bedrock_server_manager/core/system/task_scheduler.py
"""Provides a platform-agnostic interface for OS-level task scheduling.

This module abstracts the complexities of creating, modifying, and deleting
scheduled tasks (e.g., cron jobs on Linux, Scheduled Tasks on Windows) that
are used to automate Bedrock server operations like backups or restarts.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def get_task_scheduler() -> Optional[Any]:
    """A factory function to get the appropriate task scheduler for the current OS.

    This function is a placeholder and returns None.
    The task scheduling functionality has been moved to plugins.
    """
    logger.debug("get_task_scheduler is called, but functionality is now in plugins.")
    return None

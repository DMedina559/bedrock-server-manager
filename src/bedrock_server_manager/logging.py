# bedrock_server_manager/logging.py
"""
Configures and manages logging for the bedrock-server-manager application.

Provides functions to set up file logging (with timestamped filenames and
retention limits) and console logging, and to add separator lines to log
files for clarity during restarts.
"""

import glob
import logging
import os
import platform
import sys
from datetime import datetime
from typing import Optional

from .config.bcm_config import get_config_dir, load_config

# --- Constants ---
DEFAULT_LOG_KEEP: int = 5  # Hardcoded default for log file retention
_logging_configured = False


def _prune_old_logs(
    log_dir: str, base_name: str = "bedrock_server_manager", keep: int = 5
):
    """
    Helper function to prune old log files in the specified directory.
    Assumes log files follow the pattern '<base_name>_*.log'.
    """
    try:
        pattern = os.path.join(log_dir, f"{base_name}_*.log")
        files = glob.glob(pattern)
        # Sort files by modification time, oldest first
        files.sort(key=os.path.getmtime)

        # If we have more files than we want to keep, delete the oldest
        if len(files) >= keep:
            files_to_delete = files[: len(files) - keep + 1]
            for f in files_to_delete:
                try:
                    os.remove(f)
                except OSError as e:
                    print(
                        f"Warning: Could not delete old log file '{f}': {e}",
                        file=sys.stderr,
                    )
    except Exception as e:
        print(f"Warning: Error while pruning old logs: {e}", file=sys.stderr)


def setup_logging(  # noqa: C901
    force_reconfigure: bool = False,
    config_dir: Optional[str] = None,
    log_level: Optional[str] = None,
) -> logging.Logger:
    """
    Sets up or re-configures the root logger with file and console handlers.

    On first call, it configures logging based on settings from bcm_config.
    It creates a new timestamped log file in the configured logs directory
    and ensures only the 5 most recent logs are kept.

    Args:
        force_reconfigure: If True, remove existing handlers and re-apply
                           configuration. Defaults to False.
    Returns:
        The configured logger instance.
    """
    global _logging_configured

    # Read configuration directly from early loading system
    if log_level is None:
        config = load_config()
        log_level_str = config.get("logging_level", "INFO")
    else:
        log_level_str = log_level

    # Resolve log directory
    if config_dir is None:
        config_dir = get_config_dir()
    log_dir = os.path.join(config_dir, "logs")

    # Configure root logger first
    root_logger = logging.getLogger()
    log_level = logging.getLevelName(log_level_str)
    root_logger.setLevel(log_level)

    # If already configured and not forcing a reconfigure, do nothing.
    if _logging_configured and not force_reconfigure:
        root_logger.debug("Logging already configured. Skipping setup.")
        return root_logger

    # --- Remove existing handlers if re-configuring ---
    if force_reconfigure:
        root_logger.debug("Force reconfigure requested. Removing existing handlers.")
        # Create a list of handlers to remove to avoid modifying the list while iterating
        handlers_to_remove = [
            h
            for h in root_logger.handlers
            if isinstance(h, (logging.StreamHandler, logging.FileHandler))
        ]
        for handler in handlers_to_remove:
            root_logger.debug(f"Removing handler: {handler}")
            # Ensure handler stream is closed before removing
            try:
                handler.close()
            except Exception as e:
                root_logger.debug(f"Error closing handler {handler}: {e}")
            root_logger.removeHandler(handler)

    # Ensure log directory exists
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        # Use basic print since logging might not be set up yet
        print(
            f"CRITICAL: Could not create log directory '{log_dir}': {e}",
            file=sys.stderr,
        )
        # Attempt a minimal console-only setup
        if not root_logger.hasHandlers():
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(
                logging.Formatter("%(levelname)s: %(message)s")
            )
            root_logger.addHandler(console_handler)
            root_logger.setLevel(log_level)
            root_logger.warning(
                f"File logging disabled due to directory error for '{log_dir}'."
            )
        return root_logger

    # Prune old logs before creating a new one
    _prune_old_logs(log_dir, base_name="bedrock_server_manager", keep=DEFAULT_LOG_KEEP)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"bedrock_server_manager_{timestamp}.log"
    log_path = os.path.join(log_dir, log_filename)

    try:
        # --- Define Log Formats ---
        file_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")

        # --- File Handler ---
        file_handler = logging.FileHandler(
            log_path,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # --- Console Handler ---
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        _logging_configured = True
        root_logger.info(
            f"Logging has been {'re' if force_reconfigure else ''}configured. "
            f"Level: '{logging.getLevelName(log_level)}'"
        )

    except Exception as e:
        print(f"CRITICAL: Failed to configure log handlers: {e}", file=sys.stderr)
        if not root_logger.hasHandlers():
            # Fallback to a very basic console logger if everything failed
            logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
            root_logger.warning(
                "Using basic fallback logging due to configuration error."
            )

    return root_logger


def log_separator(  # noqa: C901
    logger: logging.Logger,
    app_name: Optional[str] = None,
    app_version: str = "0.0.0",
) -> None:
    """
    Writes a separator line with system and app info directly to file handlers.

    This helps visually distinguish application restarts or different runs
    within the log files. Information includes OS, Python version, app name/version,
    and timestamp. It writes directly to the stream of FileHandler instances.

    Args:
        logger: The logger object whose file handlers will be written to.
        app_name: The name of the application (optional).
        app_version: The version of the application (optional).
    """
    try:
        os_name = platform.system()
        os_version = platform.release()
        os_info = f"{os_name} {os_version}"
        if os_name == "Windows":
            os_info = f"{os_name} {platform.version()}"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        python_version = platform.python_version()

        separator_line = "=" * 100
        info_lines = [
            f"{app_name or 'Application'} v{app_version}",
            f"Operating System: {os_info}",
            f"Python Version: {python_version}",
            f"Timestamp: {current_time}",
        ]

        logger.debug(
            f"Attempting to write log separator. App: {app_name}, Version: {app_version}"
        )

        handlers_written = 0
        for handler in logger.handlers:
            # Only write to file-based handlers that seem active
            if isinstance(handler, (logging.FileHandler,)):
                # Check if the stream exists and is not closed (basic check)
                if (
                    hasattr(handler, "stream")
                    and handler.stream
                    and not handler.stream.closed
                ):
                    try:
                        handler.stream.write("\n" + separator_line + "\n")
                        for line in info_lines:
                            handler.stream.write(line + "\n")
                        handler.stream.write(separator_line + "\n\n")
                        handler.stream.flush()  # Ensure it's written immediately
                        logger.debug(
                            f"Separator written to handler's stream: {getattr(handler, 'baseFilename', 'Unknown File')}"
                        )
                        handlers_written += 1
                    except ValueError as e:
                        # This specific check helps diagnose closed file issues
                        if "I/O operation on closed file" in str(e):
                            logger.warning(
                                f"Could not write separator to log file (stream closed): {getattr(handler, 'baseFilename', 'Unknown File')} - {e}"
                            )
                        else:
                            # Re-raise other ValueErrors, logging them first
                            logger.exception(
                                f"ValueError writing separator to log file {getattr(handler, 'baseFilename', 'Unknown File')}: {e}"
                            )
                            # Depending on policy, you might re-raise here: raise
                    except Exception as e:
                        # Catch other unexpected errors during write/flush
                        logger.exception(
                            f"Unexpected error writing separator to log file {getattr(handler, 'baseFilename', 'Unknown File')}: {e}"
                        )
                        # Depending on policy, you might re-raise here: raise
                else:
                    logger.debug(
                        f"Skipping handler for separator write (no stream/stream closed): {handler}"
                    )

        if handlers_written == 0:
            logger.debug(
                "Log separator not written to any file handlers (none found or streams closed)."
            )

    except Exception as e:
        # Catch errors happening *before* the loop (e.g., platform calls)
        logger.error(f"Failed to prepare or write log separator: {e}", exc_info=True)

# bedrock_server_manager/logging.py
"""
Configures and manages logging for the bedrock-server-manager application.

Provides functions to set up file rotation and console logging,
and to add separator lines to log files for clarity during restarts.
"""

import logging
import logging.handlers
import os
import platform
import sys
from datetime import datetime
from typing import Optional

# --- Constants ---
DEFAULT_LOG_DIR: str = "logs"  # Default directory if not specified by settings
DEFAULT_LOG_KEEP: int = 3  # Default number of backup logs to keep
_logging_configured = False


def setup_logging(
    log_dir: str = DEFAULT_LOG_DIR,
    log_filename: str = "bedrock_server_manager.log",
    log_keep: int = DEFAULT_LOG_KEEP,
    file_log_level: int = logging.INFO,
    cli_log_level: int = logging.WARN,
    when: str = "midnight",
    interval: int = 1,
    force_reconfigure: bool = False,
) -> logging.Logger:
    """
    Sets up or re-configures the root logger with file and console handlers.

    On first call, it configures logging. On subsequent calls (if
    `force_reconfigure` is True), it removes existing handlers and adds new
    ones with the updated settings, allowing for dynamic log level changes.

    Args:
        log_dir: Directory to store log files.
        log_filename: The base name of the log file.
        log_keep: Number of backup log files to keep.
        file_log_level: The minimum log level for the file handler.
        cli_log_level: The minimum log level for the console handler.
        when: Time interval for rotation (e.g., 'midnight', 'h', 'd').
        interval: The interval number based on 'when'.
        force_reconfigure: If True, remove existing handlers and re-apply
                           configuration. Defaults to False.

    Returns:
        The configured logger instance.
    """
    global _logging_configured
    logger = logging.getLogger()
    logger.setLevel(min(file_log_level, cli_log_level))

    # If already configured and not forcing a reconfigure, do nothing.
    if _logging_configured and not force_reconfigure:
        logger.debug("Logging already configured. Skipping setup.")
        return logger

    # --- Remove existing handlers if re-configuring ---
    if force_reconfigure:
        logger.debug("Force reconfigure requested. Removing existing handlers.")
        # Create a list of handlers to remove to avoid modifying the list while iterating
        handlers_to_remove = [
            h
            for h in logger.handlers
            if isinstance(
                h, (logging.StreamHandler, logging.handlers.TimedRotatingFileHandler)
            )
        ]
        for handler in handlers_to_remove:
            logger.debug(f"Removing handler: {handler}")
            # Ensure handler stream is closed before removing
            try:
                handler.close()
            except Exception as e:
                logger.debug(f"Error closing handler {handler}: {e}")
            logger.removeHandler(handler)

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
        if not logger.hasHandlers():
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(cli_log_level)
            console_handler.setFormatter(
                logging.Formatter("%(levelname)s: %(message)s")
            )
            logger.addHandler(console_handler)
            logger.warning(
                f"File logging disabled due to directory error for '{log_dir}'."
            )
        return logger

    log_path = os.path.join(log_dir, log_filename)

    try:
        # --- Define Log Formats ---
        file_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")

        # --- File Handler ---
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_path,
            when=when,
            interval=interval,
            backupCount=log_keep,
            encoding="utf-8",
        )
        file_handler.setLevel(file_log_level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # --- Console Handler ---
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(cli_log_level)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        _logging_configured = True
        logger.info(
            f"Logging has been {'re' if force_reconfigure else ''}configured. "
            f"CLI Level: '{logging.getLevelName(cli_log_level)}', "
            f"File Level: '{logging.getLevelName(file_log_level)}'"
        )

    except Exception as e:
        print(f"CRITICAL: Failed to configure log handlers: {e}", file=sys.stderr)
        if not logger.hasHandlers():
            # Fallback to a very basic console logger if everything failed
            logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
            logger.warning("Using basic fallback logging due to configuration error.")

    return logger


def log_separator(
    logger: logging.Logger,
    app_name: Optional[str] = "BedrockServerManager",
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
            if isinstance(
                handler,
                (logging.FileHandler, logging.handlers.TimedRotatingFileHandler),
            ):
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

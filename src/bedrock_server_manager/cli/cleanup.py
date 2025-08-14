# bedrock_server_manager/cli/cleanup.py
"""
Defines the `bsm cleanup` command for removing generated application files.

This module provides a utility command for project and application maintenance.
It allows for the targeted removal of:
-   Python bytecode cache directories (``__pycache__``).
-   Application log files (``.log`` files from the configured log directory).

The log cleanup functionality is designed to retain the most recent log file
while deleting older ones, helping to manage disk space without losing the
very latest logging information. The project root for pycache cleanup is
determined dynamically. The log directory can be specified via an option or
taken from application settings.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

import click

from ..context import AppContext

logger = logging.getLogger(__name__)


# --- Core Cleanup Functions ---


def _cleanup_pycache() -> int:
    """Finds and removes all `__pycache__` directories within the project.

    It traverses up from the current file's location to find the project
    root and then recursively removes all `__pycache__` directories.

    Returns:
        The number of directories deleted.
    """
    try:
        # Assumes this file is at bedrock_server_manager/cli/cleanup.py.
        # .parents[0] is 'cli', .parents[1] is 'bedrock_server_manager',
        # .parents[2] is the project root directory.
        project_root = Path(__file__).resolve().parents[2]
        deleted_count = 0

        for cache_dir in project_root.rglob("__pycache__"):
            if cache_dir.is_dir():
                logger.debug(f"Removing pycache directory: {cache_dir}")
                shutil.rmtree(cache_dir)
                deleted_count += 1
        return deleted_count

    except Exception as e:
        logger.error(f"Error during pycache cleanup: {e}", exc_info=True)
        click.secho(f"An error occurred during cache cleanup: {e}", fg="red")
        return 0


def _cleanup_log_files(log_dir_path: Path) -> int:
    """
    Deletes all `.log` files in the specified directory, skipping the newest one.

    Args:
        log_dir_path (Path): The `pathlib.Path` object for the log directory.

    Returns:
        int: The number of log files deleted.
    """
    if not log_dir_path.is_dir():
        message = f"Log directory '{log_dir_path}' does not exist."
        click.secho(f"Warning: {message}", fg="yellow")
        logger.warning(f"Log cleanup skipped: {message}")
        return 0

    deleted_count = 0
    try:
        log_files = sorted(log_dir_path.glob("*.log.*"), key=os.path.getmtime)

        if not log_files:
            logger.info(f"No log files found in '{log_dir_path}'.")
            return 0

        if len(log_files) == 1:
            logger.info(
                f"Only one log file found ('{log_files[0].name}'); it will be kept."
            )
            return 0

        newest_log = log_files[-1]
        logger.info(f"Keeping newest log file: {newest_log.name}")

        # Iterate over all but the newest log file
        for log_file in log_files[:-1]:
            try:
                logger.debug(f"Removing old log file: {log_file.name}")
                log_file.unlink()
                deleted_count += 1
            except Exception as e_unlink:
                logger.error(
                    f"Failed to remove log file '{log_file.name}': {e_unlink}",
                    exc_info=True,
                )
                click.secho(
                    f"Error removing log file '{log_file.name}': {e_unlink}", fg="red"
                )

        return deleted_count
    except Exception as e:
        logger.error(
            f"Error during log cleanup in '{log_dir_path}': {e}", exc_info=True
        )
        click.secho(f"An error occurred during log cleanup: {e}", fg="red")
        return 0


# --- The Click Command ---


@click.command("cleanup")
@click.option(
    "-c",
    "--cache",
    is_flag=True,
    help="Clean up Python bytecode cache files (__pycache__).",
)
@click.option(
    "-l", "--logs", is_flag=True, help="Clean up application log files (``.log``)."
)
@click.option(
    "--log-dir",
    "log_dir_override",
    type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
    help="Override the default log directory from settings.",
)
@click.pass_context
def cleanup(
    ctx: click.Context, cache: bool, logs: bool, log_dir_override: Optional[Path]
):
    """
    Cleans up generated application files, such as logs and Python bytecode cache.

    This maintenance command helps keep the project directory and application
    data areas tidy by removing temporary or accumulated files. At least one
    of the cleanup flags (`--cache` or `--logs`) must be provided for the
    command to perform an action.

    Log Cleanup Behavior:
        When `--logs` is specified, this command will delete ``.log`` files from
        the configured log directory. **Crucially, it preserves the single
        most recent log file**, ensuring that the latest operational logs are
        not accidentally deleted.

    Raises:
        click.Abort: If log cleaning (`--logs`) is requested but no valid log
                     directory can be determined (neither specified via
                     `--log-dir` nor found in settings).
    """
    logger.info("CLI: Running cleanup command...")
    app_context: AppContext = ctx.obj["app_context"]

    if not cache and not logs:
        click.secho(
            "No cleanup options specified. Use --cache, --logs, or both.", fg="yellow"
        )
        logger.warning("Cleanup command run without any action flags.")
        return

    was_anything_cleaned = False

    if cache:
        click.secho("\nCleaning Python cache files (__pycache__)...", bold=True)
        deleted_count = _cleanup_pycache()
        if deleted_count > 0:
            click.secho(
                f"Success: Cleaned up {deleted_count} __pycache__ director(ies).",
                fg="green",
            )
            logger.info(f"Cleaned {deleted_count} __pycache__ directories.")
            was_anything_cleaned = True
        else:
            click.secho("Info: No __pycache__ directories found to clean.", fg="cyan")
            logger.info("No __pycache__ directories found.")

    if logs:
        click.secho("\nCleaning log files...", bold=True)

        # Determine the correct log directory, prioritizing the command-line override.
        final_log_dir = log_dir_override
        if not final_log_dir:
            settings_log_dir = app_context.settings.get("paths.logs")
            if settings_log_dir:
                final_log_dir = Path(settings_log_dir)

        if not final_log_dir:
            msg = (
                "Log directory not specified via --log-dir or in application settings."
            )
            click.secho(f"Error: {msg}", fg="red")
            logger.error(f"Cannot clean logs: {msg}")
            raise click.Abort()

        click.echo(f"Targeting log directory: {final_log_dir}")
        deleted_count = _cleanup_log_files(final_log_dir)

        if deleted_count > 0:
            click.secho(
                f"Success: Cleaned up {deleted_count} log file(s) from '{final_log_dir}'.",
                fg="green",
            )
            logger.info(f"Cleaned {deleted_count} log files from '{final_log_dir}'.")
            was_anything_cleaned = True
        else:
            click.secho(
                f"Info: No log files found to clean in '{final_log_dir}'.", fg="cyan"
            )
            logger.info(f"No log files found in '{final_log_dir}'.")

    if was_anything_cleaned:
        logger.info("CLI: Cleanup operations finished successfully.")
    else:
        logger.info("CLI: Cleanup operations finished, nothing was cleaned.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cleanup()

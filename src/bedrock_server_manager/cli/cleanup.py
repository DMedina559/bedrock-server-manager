# bedrock_server_manager/cli/cleanup.py
"""Define the ``bsm cleanup`` command for removing generated application files."""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

import click

from ..context import AppContext
from ..contracts import CleanupResult
from ..error import FileOperationError
from ..failures import classify_failure

logger = logging.getLogger(__name__)


# --- Core Cleanup Functions ---


def _cleanup_pycache() -> CleanupResult:
    """Clean this package's bytecode caches, reporting individual failures."""
    package_root = Path(__file__).resolve().parents[1]
    deleted = []
    failures = {}
    try:
        paths = list(package_root.rglob("__pycache__"))
    except OSError as error:
        raise FileOperationError("Cannot scan package caches.") from error
    for directory in paths:
        try:
            if directory.is_dir():
                shutil.rmtree(directory)
                deleted.append(str(directory))
        except OSError as error:
            failures[str(directory)] = classify_failure(error).error
    return CleanupResult(deleted=deleted, failures=failures)


def _cleanup_log_files(log_dir_path: Path) -> CleanupResult:
    if not log_dir_path.is_dir():
        raise FileOperationError("Log directory does not exist.")
    try:
        paths = sorted(log_dir_path.glob("*.log.*"), key=os.path.getmtime)
    except OSError as error:
        raise FileOperationError("Cannot scan rotated logs.") from error
    deleted = []
    failures = {}
    for path in paths[:-1]:
        try:
            path.unlink()
            deleted.append(str(path))
        except OSError as error:
            failures[str(path)] = classify_failure(error).error
    return CleanupResult(
        deleted=deleted, retained=[str(path) for path in paths[-1:]], failures=failures
    )


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
    """Cleans up generated application files, such as logs and Python bytecode cache."""
    logger.info("Running cleanup command...")
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
        try:
            result = _cleanup_pycache()
        except FileOperationError as error:
            raise click.ClickException(str(error)) from error
        if result.failures:
            raise click.ClickException(
                f"Cache cleanup incomplete: {len(result.deleted)} deleted, {len(result.failures)} failed."
            )
        deleted_count = len(result.deleted)
        if deleted_count > 0:
            click.secho(
                f"Success: Cleaned up {deleted_count} __pycache__ director(ies).",
                fg="green",
            )
            logger.info("Cleaned %s __pycache__ directories.", deleted_count)
            was_anything_cleaned = True
        else:
            click.secho("Info: No __pycache__ directories found to clean.", fg="cyan")
            logger.info("No __pycache__ directories found.")

    if logs:
        click.secho("\nCleaning log files...", bold=True)

        # Determine the correct log directory, prioritizing the command-line override.
        final_log_dir = log_dir_override
        if not final_log_dir:
            settings_log_dir = app_context.log_dir
            if settings_log_dir:
                final_log_dir = Path(settings_log_dir)

        if not final_log_dir:
            msg = (
                "Log directory not specified via --log-dir or in application settings."
            )
            click.secho(f"Error: {msg}", fg="red")
            logger.error("Cannot clean logs: %s", msg)
            raise click.Abort()

        click.echo(f"Targeting log directory: {final_log_dir}")
        try:
            result = _cleanup_log_files(final_log_dir)
        except FileOperationError as error:
            raise click.ClickException(str(error)) from error
        if result.failures:
            raise click.ClickException(
                f"Log cleanup incomplete: {len(result.deleted)} deleted, {len(result.failures)} failed."
            )
        deleted_count = len(result.deleted)

        if deleted_count > 0:
            click.secho(
                f"Success: Cleaned up {deleted_count} log file(s) from '{final_log_dir}'.",
                fg="green",
            )
            logger.info("Cleaned %s log files from '%s'.", deleted_count, final_log_dir)
            was_anything_cleaned = True
        else:
            click.secho(
                f"Info: No log files found to clean in '{final_log_dir}'.", fg="cyan"
            )
            logger.info("No log files found in '%s'.", final_log_dir)

    if was_anything_cleaned:
        logger.info("Cleanup operations finished successfully.")
    else:
        logger.info("Cleanup operations finished, nothing was cleaned.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cleanup()

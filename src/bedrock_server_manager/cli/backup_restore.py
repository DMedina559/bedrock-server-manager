# bedrock_server_manager/cli/backup_restore.py
"""
Defines the `bsm backup` command group for server backup and restore operations.

This module provides CLI tools to create, restore, list, and prune backups
for Bedrock server instances. It supports backing up and restoring the server
world (as ``.mcworld`` files) and key configuration files (``server.properties``,
``allowlist.json``, ``permissions.json``).

Key functionalities:

    -   Creating backups:
        -   Full backup (world + all standard configs).
        -   World-only backup.
        -   Specific configuration file backup.

    -   Restoring from backups:
        -   Restore world from a chosen ``.mcworld`` backup.
        -   Restore a specific configuration file from its backup.
        (Note: A full "restore all" from latest is handled by API, but CLI might expose it differently or via world/config restore).

    -   Listing available backup files for different components.
    -   Pruning old backups based on retention policies defined in application settings.

The module includes interactive workflows for guided backup and restore processes,
as well as direct command-line options for scripting and automation. Commands
primarily interact with the API functions in
:mod:`~bedrock_server_manager.api.backup_restore`.
"""

import logging
import os
from typing import Optional, Tuple

import click
import questionary

from bedrock_server_manager.api import backup_restore as backup_restore_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# ---- Interactive Menu Helpers ----


def _interactive_backup_menu(
    server_name: str,
) -> Tuple[str, Optional[str], bool]:
    """
    Guides the user through an interactive menu to select backup options.

    Presents choices for backing up:

        - World only
        - Everything (world + standard configs)
        - A specific configuration file (server.properties, allowlist.json, permissions.json)

    Args:
        server_name (str): The name of the server for which to create a backup.
                           Used in prompts and logging.

    Returns:
        Tuple[str, Optional[str], bool]: A tuple containing:

            - ``backup_type`` (str): The type of backup selected (e.g., "world",
              "all", "config").
            - ``file_to_backup`` (Optional[str]): The name of the specific
              configuration file if `backup_type` is "config", otherwise ``None``.
            - ``change_status`` (bool): Indicates if the server's running status
              should be managed (stopped/started) for this backup type.
              ``True`` for world/all, ``False`` for config by default here.

    Raises:
        click.Abort: If the user cancels the operation at any `questionary` prompt.
    """
    click.secho(f"Entering interactive backup for server: {server_name}", fg="yellow")

    # Maps user-friendly choices to API parameters
    backup_type_map = {
        "Backup World Only": ("world", None, True),
        "Backup Everything (World + Configs)": ("all", None, True),
        "Backup a Specific Configuration File": ("config", None, False),
    }

    choice = questionary.select(
        "Select a backup option:",
        choices=list(backup_type_map.keys()) + ["Cancel"],
    ).ask()

    if not choice or choice == "Cancel":
        raise click.Abort()

    b_type, b_file, b_change_status = backup_type_map[choice]

    if b_type == "config":
        # Let user choose which config file to back up
        config_file_map = {
            "allowlist.json": "allowlist.json",
            "permissions.json": "permissions.json",
            "server.properties": "server.properties",
        }
        file_choice = questionary.select(
            "Which configuration file do you want to back up?",
            choices=list(config_file_map.keys()) + ["Cancel"],
        ).ask()

        if not file_choice or file_choice == "Cancel":
            raise click.Abort()
        b_file = config_file_map[file_choice]

    return b_type, b_file, b_change_status


def _interactive_restore_menu(
    server_name: str,
) -> Tuple[str, str, bool]:
    """
    Guides the user through an interactive menu to select a backup to restore.

    Prompts the user to choose what type of component to restore (world or a
    specific config file). Then, it lists available backup files for that type
    and allows the user to select one.

    Args:
        server_name (str): The name of the server to which a backup will be restored.

    Returns:
        Tuple[str, str, bool]: A tuple containing:

            - ``restore_type`` (str): The type of item being restored (e.g., "world",
              "allowlist", "properties", "permissions").
            - ``backup_file_path`` (str): The absolute path to the selected backup file.
            - ``change_status`` (bool): Always ``True`` for restore operations,
              indicating the server status should be managed.

    Raises:
        click.Abort: If the user cancels the operation, or if no backups are
                     found for the selected type, or if listing backups fails.
    """
    click.secho(f"Entering interactive restore for server: {server_name}", fg="yellow")

    restore_type_map = {
        "Restore World": "world",
        "Restore Allowlist": "allowlist",
        "Restore Permissions": "permissions",
        "Restore Properties": "properties",
    }

    choice = questionary.select(
        "What do you want to restore?",
        choices=list(restore_type_map.keys()) + ["Cancel"],
    ).ask()

    if not choice or choice == "Cancel":
        raise click.Abort()
    restore_type = restore_type_map[choice]

    # Fetch and display available backup files for the selected type
    try:
        response = backup_restore_api.list_backup_files(server_name, restore_type)
        backup_files = response.get("backups", [])
        if not backup_files:
            click.secho(
                f"No '{restore_type}' backups found for server '{server_name}'.",
                fg="yellow",
            )
            raise click.Abort()
    except BSMError as e:
        click.secho(f"Error listing backups: {e}", fg="red")
        raise click.Abort()

    # Create a user-friendly list of basenames and map them back to full paths
    file_map = {os.path.basename(f): f for f in backup_files}
    file_choices = sorted(list(file_map.keys()), reverse=True)  # Show newest first

    file_to_restore_basename = questionary.select(
        f"Select a '{restore_type}' backup to restore:",
        choices=file_choices + ["Cancel"],
    ).ask()

    if not file_to_restore_basename or file_to_restore_basename == "Cancel":
        raise click.Abort()
    selected_file_path = file_map[file_to_restore_basename]

    return restore_type, selected_file_path, True


# ---- Click Command Group ----


@click.group()
def backup():
    """
    Manages server backups, including creation, restoration, and pruning.

    This command group provides a suite of tools for handling backups of
    Bedrock server data. You can create new backups of the world or
    configuration files, restore a server to a previous state from these
    backups, and manage storage by pruning old backup files according to
    configured retention policies.
    """
    pass


@backup.command("create")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the target server."
)
@click.option(
    "-t",
    "--type",
    "backup_type",
    type=click.Choice(["world", "config", "all"], case_sensitive=False),
    help="Type of backup to create; skips interactive menu.",
)
@click.option(
    "-f",
    "--file",
    "file_to_backup",
    help="Specific file to back up (required if --type=config).",
)
@click.option(
    "--no-stop",
    is_flag=True,
    help="Perform backup without stopping the server (risks data corruption).",
)
def create_backup(
    server_name: str,
    backup_type: Optional[str],
    file_to_backup: Optional[str],
    no_stop: bool,
):
    """
    Creates a backup of specified server data (world, config, or all).

    This command can back up the server's world (as a ``.mcworld`` file),
    a specific configuration file (e.g., ``server.properties``), or everything
    (world and all standard configuration files).

    If run without the ``--type`` option, it launches an interactive menu
    (:func:`~._interactive_backup_menu`) to guide the user through selecting
    what to back up. If ``--type`` is provided, it attempts the specified
    backup directly. For "config" type, ``--file`` is also required.

    The server is typically stopped before world or "all" backups and restarted
    afterwards to ensure data integrity, unless ``--no-stop`` is specified
    (not recommended for world/all). After a successful backup, old backups
    are automatically pruned based on retention settings.

    When ``--type`` is "config", the ``--file`` option is also required to specify
    which configuration file to back up (e.g., "server.properties").
    The ``--no-stop`` flag can be used to perform the backup without stopping the
    server, but this is risky for 'world' or 'all' backups and may lead to data
    corruption.

    This command calls the following API functions:

        - :func:`~bedrock_server_manager.api.backup_restore.backup_world`
        - :func:`~bedrock_server_manager.api.backup_restore.backup_config_file`
        - :func:`~bedrock_server_manager.api.backup_restore.backup_all`
        - :func:`~bedrock_server_manager.api.backup_restore.prune_old_backups`
    """

    def _run_backup(b_type: str, f_to_backup: Optional[str], s_name: str, stop: bool):
        """Internal helper to execute the correct API call."""
        if b_type == "world":
            return backup_restore_api.backup_world(s_name, stop_start_server=stop)
        if b_type == "config":
            return backup_restore_api.backup_config_file(
                s_name, f_to_backup, stop_start_server=stop
            )
        if b_type == "all":
            return backup_restore_api.backup_all(s_name, stop_start_server=stop)
        return None

    change_status = not no_stop

    try:
        if not backup_type:
            backup_type, file_to_backup, change_status = _interactive_backup_menu(
                server_name
            )

        if backup_type == "config" and not file_to_backup:
            raise click.UsageError(
                "Option '--file' is required when using '--type config'."
            )

        click.echo(f"Starting '{backup_type}' backup for server '{server_name}'...")
        response = _run_backup(backup_type, file_to_backup, server_name, change_status)
        _handle_api_response(response, "Backup completed successfully.")

        click.echo("Pruning old backups...")
        prune_response = backup_restore_api.prune_old_backups(server_name=server_name)
        _handle_api_response(prune_response, "Pruning complete.")

    except BSMError as e:
        click.secho(f"A backup error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nBackup operation cancelled.", fg="yellow")


@backup.command("restore")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the target server."
)
@click.option(
    "-f",
    "--file",
    "backup_file_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to the backup file to restore; skips interactive menu.",
)
@click.option(
    "--no-stop",
    is_flag=True,
    help="Perform restore without stopping the server (risks data corruption).",
)
def restore_backup(server_name: str, backup_file_path: Optional[str], no_stop: bool):
    """
    Restores server data from a specified backup file.

    .. warning::
        This is a **DESTRUCTIVE** operation. It will overwrite the current
        server data (world or specific configuration file) with the content
        from the selected backup file.

    If the ``--file`` option is provided with a path to a backup file, the
    command attempts to infer the type of restore (world or config) from the
    filename and proceeds with that file.
    If ``--file`` is not provided, an interactive menu
    (:func:`~._interactive_restore_menu`) is launched, allowing the user to
    select the type of data to restore and then choose from a list of
    available backup files for that type.

    The server is typically stopped before the restore operation and restarted
    afterwards to ensure data integrity, unless ``--no-stop`` is specified
    (highly discouraged for world restores).

    If the ``--file`` option is provided, it should be a path to an existing
    backup file (not a directory). The command will attempt to infer the restore
    type (world or config) from the filename.
    The ``--no-stop`` flag can be used to perform the restore without stopping
    the server, but this is highly risky and may lead to data corruption.

    This command interacts with the following API functions:

        - :func:`~bedrock_server_manager.api.backup_restore.list_backup_files` (for interactive mode)
        - :func:`~bedrock_server_manager.api.backup_restore.restore_world`
        - :func:`~bedrock_server_manager.api.backup_restore.restore_config_file`
    """
    change_status = not no_stop

    try:
        if backup_file_path:
            filename = os.path.basename(backup_file_path).lower()
            if "world" in filename:
                restore_type = "world"
            elif (
                "allowlist" in filename
                or "permissions" in filename
                or "properties" in filename
            ):
                restore_type = "config"
            else:
                raise click.UsageError(
                    f"Could not determine restore type from filename '{filename}'."
                )
        else:
            restore_type, backup_file_path, change_status = _interactive_restore_menu(
                server_name
            )

        click.echo(
            f"Starting '{restore_type}' restore for server '{server_name}' from '{os.path.basename(backup_file_path)}'..."
        )

        if restore_type == "world":
            response = backup_restore_api.restore_world(
                server_name, backup_file_path, stop_start_server=change_status
            )
        else:
            response = backup_restore_api.restore_config_file(
                server_name, backup_file_path, stop_start_server=change_status
            )

        _handle_api_response(response, "Restore completed successfully.")

    except BSMError as e:
        click.secho(f"A restore error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nRestore operation cancelled.", fg="yellow")


@backup.command("prune")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server whose backups to prune.",
)
def prune_backups(server_name: str):
    """
    Deletes old backups for a server, keeping only the newest ones.

    This command checks the backup retention policy defined in the application's
    main configuration (setting: ``retention.backups``). It then deletes
    any backup files (for world and standard configs) for the specified server
    that are older than the configured limit, ensuring only the most recent
    backups are retained.

    Calls API: :func:`~bedrock_server_manager.api.backup_restore.prune_old_backups`.
    """
    try:
        click.echo(f"Pruning old backups for server '{server_name}'...")
        response = backup_restore_api.prune_old_backups(server_name=server_name)
        _handle_api_response(response, "Pruning complete.")
    except BSMError as e:
        click.secho(f"An error occurred during pruning: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backup()

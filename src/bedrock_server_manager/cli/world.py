# bedrock_server_manager/cli/world.py
"""
Defines the `bsm world` command group for managing Bedrock server worlds.

This module provides CLI tools for various world-related operations, including:

    -   Installing a new world onto a server from a ``.mcworld`` file, which
        replaces the server's current active world.
    -   Exporting a server's current active world into a ``.mcworld`` file,
        suitable for backup or transfer.
    -   Resetting a server's world, which involves deleting the current world
        data to allow the server to generate a new one upon its next start.

Commands typically interact with the API functions in
:mod:`~bedrock_server_manager.api.world` and may involve user confirmation
for destructive operations. Some commands also list available world templates
from the application's content directory.
"""

import logging
import os
from typing import Optional

import click
import questionary

from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.api import world as world_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


@click.group()
def world():
    """
    Manages server worlds, including installation, export, and reset operations.

    This command group provides utilities to manipulate the world data for a
    specific Bedrock server instance. You can install a world from a ``.mcworld``
    file (replacing the current world), export the server's current active world
    to a ``.mcworld`` file for backup or transfer, or reset the world to allow
    the server to generate a new one on its next start.
    """
    pass


@world.command("install")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the target server."
)
@click.option(
    "-f",
    "--file",
    "world_file_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to the .mcworld file to install. Skips interactive menu.",
)
@click.option(
    "--no-stop",
    is_flag=True,
    help="Attempt to install without stopping the server (risks data corruption).",
)
def install_world(server_name: str, world_file_path: Optional[str], no_stop: bool):
    """
    Installs a world from a .mcworld file, replacing the server's current world.

    .. warning::
        This is a destructive operation that will overwrite the existing
        active world data for the specified server.

    If the ``--file`` option is provided with a path to a ``.mcworld`` file,
    that file will be used for installation.
    If ``--file`` is not provided, the command enters an interactive mode,
    listing all available ``.mcworld`` files from the application's global
    content directory (typically ``content/worlds``) for the user to select.

    The server is typically stopped before installation and restarted afterwards
    to ensure data integrity, unless ``--no-stop`` is specified (not recommended).
    A confirmation prompt is shown before proceeding with the installation.

    Calls APIs:

        - :func:`~bedrock_server_manager.api.application.list_available_worlds_api` (for interactive mode)
        - :func:`~bedrock_server_manager.api.world.import_world`

    """
    try:
        selected_file = world_file_path

        if not selected_file:
            click.secho(
                f"Entering interactive world installation for server: {server_name}",
                fg="yellow",
            )
            list_response = api_application.list_available_worlds_api()
            available_files = list_response.get("files", [])

            if not available_files:
                click.secho(
                    "No .mcworld files found in the content/worlds directory. Nothing to install.",
                    fg="yellow",
                )
                return

            file_map = {os.path.basename(f): f for f in available_files}
            choices = sorted(list(file_map.keys())) + ["Cancel"]
            selection = questionary.select(
                "Select a world to install:", choices=choices
            ).ask()

            if not selection or selection == "Cancel":
                raise click.Abort()  # User explicitly cancelled
            selected_file = file_map[selection]

        filename = os.path.basename(selected_file)
        click.secho(
            f"\nWARNING: Installing '{filename}' will REPLACE the current world data for server '{server_name}'.",
            fg="red",
            bold=True,
        )
        if not questionary.confirm(
            "This action cannot be undone. Are you sure?", default=False
        ).ask():
            raise click.Abort()  # User declined confirmation

        click.echo(f"Installing world '{filename}'...")
        response = world_api.import_world(
            server_name, selected_file, stop_start_server=(not no_stop)
        )
        _handle_api_response(response, f"World '{filename}' installed successfully.")

    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        # This block catches cancellations from prompts or Ctrl+C.
        click.secho("\nWorld installation cancelled.", fg="yellow")


@world.command("export")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server whose world to export.",
)
def export_world(server_name: str):
    """
    Exports the server's current active world to a .mcworld file.

    This command packages the server's active world directory into a ``.mcworld``
    archive. The resulting file is typically saved in the application's global
    content directory (e.g., ``content/worlds``) and is named using the
    world's name and a timestamp (e.g., ``MyWorldName_export_YYYYMMDD_HHMMSS.mcworld``).

    This exported file can be used for backups, transferring the world to
    another server, or sharing. The server is usually stopped during this
    process to ensure data integrity.

    Calls API: :func:`~bedrock_server_manager.api.world.export_world`.
    """
    click.echo(f"Attempting to export world for server '{server_name}'...")
    try:
        response = world_api.export_world(server_name)
        _handle_api_response(response, "World exported successfully.")
    except BSMError as e:
        click.secho(f"An error occurred during export: {e}", fg="red")
        raise click.Abort()


@world.command("reset")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server whose world to reset.",
)
@click.option("-y", "--yes", is_flag=True, help="Bypass the confirmation prompt.")
def reset_world(server_name: str, yes: bool):
    """
    Deletes the current active world data for a server.

    .. danger::
        This is a **HIGHLY DESTRUCTIVE** operation that permanently removes
        the server's active world directory.

    This is useful when you want the server to generate a completely new world
    the next time it starts (based on its `level-name` and `level-seed` in
    `server.properties`).

    A confirmation prompt is required before proceeding, unless the ``--yes``
    flag is provided. The server is typically stopped before deletion and
    restarted afterwards.

    Calls API: :func:`~bedrock_server_manager.api.world.reset_world`.
    """
    if not yes:
        click.secho(
            f"WARNING: This will permanently delete the current world for server '{server_name}'.",
            fg="red",
            bold=True,
        )
        # click.confirm is a great utility that handles the prompt and abort logic.
        click.confirm(
            "This action cannot be undone. Are you sure you want to reset the world?",
            abort=True,
        )

    click.echo(f"Resetting world for server '{server_name}'...")
    try:
        response = world_api.reset_world(server_name)
        _handle_api_response(response, "World has been reset successfully.")
    except BSMError as e:
        click.secho(f"An error occurred during reset: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    world()

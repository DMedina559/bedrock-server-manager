# bedrock_server_manager/cli/addon.py
"""Defines CLI commands for managing Bedrock server addons.

This module provides tools to install addons (behavior packs, resource packs)
onto a specified server. Addons are typically ``.mcpack`` or ``.mcaddon`` files.
Functionality may be expanded in the future to include listing, removing, or
exporting addons.

Commands currently include:

    -   ``bsm install-addon``: Installs an addon from a local file or by selecting
        from available addons in the content directory.

These commands interact with the API functions in
:mod:`~bedrock_server_manager.api.addon` and
:mod:`~bedrock_server_manager.api.application` (for listing available addons).
"""

import logging
import os
from typing import Optional

import click
import questionary

from bedrock_server_manager.api import addon as addon_api
from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


@click.command("install-addon")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the target server."
)
@click.option(
    "-f",
    "--file",
    "addon_file_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to the addon file (.mcpack, .mcaddon); skips interactive menu.",
)
def install_addon(server_name: str, addon_file_path: Optional[str]):
    """
    Installs a behavior or resource pack addon to a specified server.

    This command installs an addon from a local file (typically ``.mcpack``
    or ``.mcaddon``). The addon's contents are extracted and applied to the
    server's relevant world development packs folders (behavior_packs,
    resource_packs) and potentially registered in world configuration files.

    If the ``--file`` option is provided with a path to an addon file,
    that file will be used for installation.
    If ``--file`` is not provided, the command enters an interactive mode,
    listing all available addon files from the application's global content
    directory (typically ``content/addons``) for the user to select.

    Calls APIs:
        - :func:`~bedrock_server_manager.api.application.list_available_addons_api` (for interactive mode)
        - :func:`~bedrock_server_manager.api.addon.import_addon`
    """
    try:
        selected_addon_path = addon_file_path

        # If no file is provided, enter interactive mode
        if not selected_addon_path:
            click.secho(
                f"Entering interactive addon installation for server: {server_name}",
                fg="yellow",
            )
            list_response = api_application.list_available_addons_api()
            available_files = list_response.get("files", [])

            if not available_files:
                click.secho(
                    "No addon files found in the content/addons directory. Nothing to install.",
                    fg="yellow",
                )
                return

            file_map = {os.path.basename(f): f for f in available_files}
            choices = sorted(list(file_map.keys())) + ["Cancel"]
            selection = questionary.select(
                "Select an addon to install:", choices=choices
            ).ask()

            if not selection or selection == "Cancel":
                raise click.Abort()  # User explicitly cancelled
            selected_addon_path = file_map[selection]

        # By this point, `selected_addon_path` is set to a valid file path.
        addon_filename = os.path.basename(selected_addon_path)
        click.echo(f"Installing addon '{addon_filename}' to server '{server_name}'...")
        logger.debug(
            f"CLI: Calling addon_api.import_addon for file: {selected_addon_path}"
        )

        response = addon_api.import_addon(server_name, selected_addon_path)
        _handle_api_response(
            response, f"Addon '{addon_filename}' installed successfully."
        )

    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        # This block catches cancellations from prompts (Ctrl+D/Abort) or Ctrl+C.
        click.secho("\nAddon installation cancelled.", fg="yellow")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    install_addon()

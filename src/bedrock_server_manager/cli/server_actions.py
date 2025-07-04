# bedrock_server_manager/cli/server_actions.py
"""
Defines the `bsm server` command group for server lifecycle management and interaction.

This module provides the main entry point for most server-specific operations
via the command line. It includes commands for:

    -   **Installation & Updates:**
        -   ``bsm server install``: Interactively installs a new Bedrock server instance.
        -   ``bsm server update``: Updates an existing server to its target version.
    -   **Lifecycle Control:**
        -   ``bsm server start``: Starts a server (detached or direct mode).
        -   ``bsm server stop``: Stops a running server.
        -   ``bsm server restart``: Restarts a server.
    -   **Data Management:**
        -   ``bsm server delete``: **DESTRUCTIVE** - Deletes all server data including backups.
    -   **Interaction & Configuration:**
        -   ``bsm server send-command <server_name> <command_parts>...``: Sends a command
            to a running server.
        -   ``bsm server config <server_name> --key <key> --value <value>``: Sets a specific
            configuration key in the server's JSON configuration file.

Commands in this module typically interact with the API functions defined in
:mod:`~bedrock_server_manager.api.server` and
:mod:`~bedrock_server_manager.api.server_install_config`.
Error handling is generally done by catching :class:`~bedrock_server_manager.error.BSMError`
exceptions and aborting with a user-friendly message.
"""

import logging
import platform
import sys
from typing import Tuple

import click
import questionary

from bedrock_server_manager.api import server as server_api
from bedrock_server_manager.api import server_install_config as config_api
from bedrock_server_manager.cli.system import interactive_service_workflow
from bedrock_server_manager.cli.server_allowlist import interactive_allowlist_workflow
from bedrock_server_manager.cli.server_permissions import (
    interactive_permissions_workflow,
)
from bedrock_server_manager.cli.server_properties import interactive_properties_workflow
from bedrock_server_manager.cli.utils import (
    handle_api_response as _handle_api_response,
    ServerNameValidator,
)
from bedrock_server_manager.error import BSMError


logger = logging.getLogger(__name__)


@click.group()
def server():
    """
    Manages the lifecycle and configuration of individual Minecraft Bedrock servers.

    This group contains commands to install, start, stop, restart, update,
    delete, configure, and interact with specific server instances.
    """
    pass


@server.command("start")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the server to start."
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["direct", "detached"], case_sensitive=False),
    default="detached",
    show_default=True,
    help="Start mode: 'detached' runs in background, 'direct' blocks terminal.",
)
def start_server(server_name: str, mode: str):
    """
    Starts a specific Bedrock server instance.

    This command initiates the startup sequence for the named server.
    It can start the server in 'detached' mode (running in the background,
    often managed by a system service if configured) or 'direct' mode
    (running in the foreground, blocking the current terminal).

    Calls API: :func:`~bedrock_server_manager.api.server.start_server`.
    """
    click.echo(f"Attempting to start server '{server_name}' in {mode} mode...")

    try:
        response = server_api.start_server(server_name, mode)
        # Custom response handling because 'direct' mode blocks and won't show this.
        if mode == "detached":
            _handle_api_response(
                response, f"Server '{server_name}' started successfully."
            )
    except BSMError as e:
        click.secho(f"Failed to start server: {e}", fg="red")
        raise click.Abort()


@server.command("stop")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the server to stop."
)
def stop_server(server_name: str):
    """
    Sends a graceful stop command to a running Bedrock server.

    This command attempts to stop the specified server. It prioritizes using
    system services if available, otherwise sends a 'stop' command directly
    to the server console and waits for termination.

    Calls API: :func:`~bedrock_server_manager.api.server.stop_server`.
    """
    click.echo(f"Attempting to stop server '{server_name}'...")
    try:
        response = server_api.stop_server(server_name)
        _handle_api_response(response, f"Stop signal sent to server '{server_name}'.")
    except BSMError as e:
        click.secho(f"Failed to stop server: {e}", fg="red")
        raise click.Abort()


@server.command("restart")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server to restart.",
)
def restart_server(server_name: str):
    """
    Gracefully restarts a specific Bedrock server.

    This command first attempts to stop the server if it's running, then
    starts it again in 'detached' mode. If the server is already stopped,
    it will simply be started.

    Calls API: :func:`~bedrock_server_manager.api.server.restart_server`.
    """
    click.echo(f"Attempting to restart server '{server_name}'...")
    try:
        response = server_api.restart_server(server_name)
        _handle_api_response(
            response, f"Restart signal sent to server '{server_name}'."
        )
    except BSMError as e:
        click.secho(f"Failed to restart server: {e}", fg="red")
        raise click.Abort()


@server.command("install")
@click.pass_context
def install(ctx: click.Context):
    """
    Guides you through installing and configuring a new Bedrock server instance.

    This interactive command walks you through the entire process of creating
    a new server, including:

        -   Naming the server (validated for format).
        -   Specifying the Minecraft version to install (e.g., "LATEST", "PREVIEW",
            or a specific version number like "1.20.81.01").
        -   Downloading and installing the server files.
        -   Optionally configuring server properties, allowlist, player permissions,
            and system service (systemd/Windows Service) via interactive workflows.
        -   Optionally starting the server automatically upon completion of installation
            and configuration.

    It handles cases where a server directory might already exist, prompting
    for deletion and reinstallation if desired.

    Calls APIs:

        - :func:`~bedrock_server_manager.api.server_install_config.install_new_server`
        - :func:`~bedrock_server_manager.api.server.delete_server_data` (if reinstallation is chosen)
        - Invokes other CLI commands/workflows for configuration (e.g., properties, allowlist).
        - :func:`~.start_server` (if auto-start is chosen).
    """
    try:
        click.secho("--- New Bedrock Server Installation ---", bold=True)
        server_name = questionary.text(
            "Enter a name for the new server:", validate=ServerNameValidator()
        ).ask()
        if not server_name:
            raise click.Abort()

        target_version = questionary.text(
            "Enter server version (e.g., LATEST, PREVIEW, 1.20.81.01):",
            default="LATEST",
        ).ask()
        if not target_version:
            raise click.Abort()

        click.echo(f"\nInstalling server '{server_name}' version '{target_version}'...")
        install_result = config_api.install_new_server(server_name, target_version)

        # Handle case where the server directory already exists
        if install_result.get(
            "status"
        ) == "error" and "already exists" in install_result.get("message", ""):
            click.secho(f"Warning: {install_result['message']}", fg="yellow")
            if questionary.confirm(
                "Delete the existing server and reinstall?", default=False
            ).ask():
                click.echo(f"Deleting existing server '{server_name}'...")
                server_api.delete_server_data(
                    server_name
                )  # Assuming this API call exists and works
                click.echo("Retrying installation...")
                install_result = config_api.install_new_server(
                    server_name, target_version
                )
            else:
                raise click.Abort()

        response = _handle_api_response(
            install_result, "Server files installed successfully."
        )
        click.secho(f"Installed Version: {response.get('version')}", bold=True)

        # Configuration workflows
        interactive_properties_workflow(server_name)
        if questionary.confirm("\nConfigure the allowlist now?", default=False).ask():
            interactive_allowlist_workflow(server_name)
        if questionary.confirm(
            "\nConfigure player permissions now?", default=False
        ).ask():
            interactive_permissions_workflow(server_name)
        if questionary.confirm("\nConfigure the service now?", default=False).ask():
            print(server_name)
            interactive_service_workflow(bsm=ctx.obj["bsm"], server_name=server_name)

        click.secho(
            "\nInstallation and initial configuration complete!", fg="green", bold=True
        )

        # Automatically start the newly installed server
        if questionary.confirm(
            f"Start server '{server_name}' now?", default=True
        ).ask():
            ctx.invoke(start_server, server_name=server_name, mode="detached")

    except BSMError as e:
        click.secho(f"An application error occurred: {e}", fg="red")
        raise click.Abort()
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nInstallation cancelled.", fg="yellow")


@server.command("update")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the server to update."
)
def update(server_name: str):
    """
    Checks for and applies updates to an existing Bedrock server.

    This command triggers the server update process, which typically involves:
    1.  Checking the server's configured target version.
    2.  Comparing it with the currently installed version.
    3.  If an update is needed:

        -   Stopping the server (if running).
        -   Backing up server data.
        -   Downloading and installing the new version.
        -   Restarting the server.

    If the server is already up-to-date, it will report that no update is necessary.

    Calls API: :func:`~bedrock_server_manager.api.server_install_config.update_server`.
    """
    click.echo(f"Checking for updates for server '{server_name}'...")
    try:
        response = config_api.update_server(server_name)
        _handle_api_response(response, "Update check complete.")
    except BSMError as e:
        click.secho(f"A server update error occurred: {e}", fg="red")
        raise click.Abort()


@server.command("delete")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the server to delete."
)
@click.option("-y", "--yes", is_flag=True, help="Bypass the confirmation prompt.")
def delete_server(server_name: str, yes: bool):
    """
    Deletes all data for a server, including world, configs, and backups.

    .. danger::
        This is a **HIGHLY DESTRUCTIVE** and irreversible operation.

    It removes the server's installation directory, its JSON configuration,
    its entire backup directory, and associated system services (if any).
    By default, it prompts for confirmation before proceeding.

    Calls API: :func:`~bedrock_server_manager.api.server.delete_server_data`.
    """
    if not yes:
        click.secho(
            f"WARNING: This will permanently delete all data for server '{server_name}',\n"
            "including the installation, worlds, and all associated backups.",
            fg="red",
            bold=True,
        )
        click.confirm(
            f"\nAre you absolutely sure you want to delete '{server_name}'?", abort=True
        )

    click.echo(f"Proceeding with deletion of server '{server_name}'...")
    try:
        response = server_api.delete_server_data(server_name)
        _handle_api_response(
            response, f"Server '{server_name}' and all its data have been deleted."
        )
    except BSMError as e:
        click.secho(f"Failed to delete server: {e}", fg="red")
        raise click.Abort()


@server.command("send-command")
@click.option(
    "-s", "--server", "server_name", required=True, help="Name of the target server."
)
@click.argument("command_parts", nargs=-1, required=True)
def send_command(server_name: str, command_parts: Tuple[str]):
    """
    Sends a command to a running Bedrock server's console.

    The `COMMAND_PARTS` are joined together to form the full command string.
    For example, `bsm server send-command MyServer say Hello world` will send
    "say Hello world" to "MyServer".

    The command is checked against a blacklist by the API before being sent.

    Calls API: :func:`~bedrock_server_manager.api.server.send_command`.
    """
    command_string = " ".join(command_parts)
    click.echo(f"Sending command to '{server_name}': {command_string}")
    try:
        response = server_api.send_command(server_name, command_string)
        _handle_api_response(response, "Command sent successfully.")
    except BSMError as e:
        click.secho(f"Failed to send command: {e}", fg="red")
        raise click.Abort()


@server.command("config")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server to configure.",
)
@click.option(
    "-k",
    "--key",
    required=True,
    help="The configuration key to set (e.g., 'seetings.target_version').",
)
@click.option("-v", "--value", required=True, help="The value to assign to the key.")
def config_server(server_name: str, key: str, value: str):
    """
    Sets a single key-value pair in a server's JSON configuration file.

    This command allows direct modification of settings stored in the
    server-specific JSON configuration file (e.g., `MyServer_config.json`).
    The key can be a dot-separated path to access nested values
    (e.g., "settings.autoupdate", "custom.my_value").

    Calls API: :func:`~bedrock_server_manager.api.server.set_server_setting`.
    """
    click.echo(f"Setting '{key}' for server '{server_name}'...")
    try:
        response = server_api.set_server_setting(server_name, key, value)
        _handle_api_response(response, f"Config updated: '{key}' set to '{value}'.")
    except BSMError as e:
        click.secho(f"Failed to set config for server: {e}", fg="red")
        raise click.Abort()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server()

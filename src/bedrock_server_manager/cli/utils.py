# bedrock_server_manager/cli/utils.py
"""
Command-Line Interface (CLI) Utilities.

This module provides shared helper functions and standalone utility commands
for the Bedrock Server Manager CLI. It includes:

    - Decorators:
        - :func:`~.linux_only`: Restricts a Click command to run only on Linux.

    - Shared Helper Functions:
        - :func:`~.handle_api_response`: Standardized way to process and display
          success/error messages from API calls.
        - :func:`~.get_server_name_interactively`: Prompts user to select an existing server.

    - Custom `questionary.Validator` Classes:
        - :class:`~.ServerNameValidator`: Validates server name format.
        - :class:`~.ServerExistsValidator`: Checks if a server name corresponds to an
          existing server.
        - :class:`~.PropertyValidator`: Validates values for specific server properties.

    - Standalone Click Commands:
        - ``bsm list-servers`` (from :func:`~.list_servers`): Lists all configured
          servers and their current status, with an optional live refresh loop.
        - ``bsm attach-console`` (from :func:`~.attach_console`): Attaches the
          terminal to a running server's console (Linux-only, uses screen).

These utilities aim to promote code reuse and provide a consistent user
experience across different parts of the CLI.
"""

import functools
import logging
import platform
import time
from typing import Any, Callable, Dict, List, Optional

import click
import questionary
from questionary import ValidationError, Validator

from bedrock_server_manager.api import (
    application as api_application,
    server_install_config as config_api,
    utils as api_utils,
)
from bedrock_server_manager.error import BSMError

logger = logging.getLogger(__name__)


# --- Custom Decorators ---


def linux_only(func: Callable) -> Callable:
    """A decorator that restricts a Click command to run only on Linux.

    If the command is executed on a non-Linux system, it prints an error
    message to the console and aborts the command execution using `click.Abort`.

    Args:
        func (Callable): The Click command function to decorate.

    Returns:
        Callable: The wrapped function that includes the OS check.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if platform.system() != "Linux":
            cmd_name = func.__name__.replace("_", "-")
            click.secho(
                f"Error: The '{cmd_name}' command is only available on Linux.", fg="red"
            )
            raise click.Abort()
        return func(*args, **kwargs)

    return wrapper


# --- Shared Helpers ---


def handle_api_response(response: Dict[str, Any], success_msg: str) -> Dict[str, Any]:
    """Handles responses from API calls, displaying success or error messages.

    If the response indicates an error, it prints an error message and aborts
    the CLI command. Otherwise, it prints a success message. It prioritizes
    the message from the API response over the default `success_msg`.

    Args:
        response (Dict[str, Any]): The dictionary response received from an API
            function call. Expected to have a "status" key and optionally
            "message" and "data" keys.
        success_msg (str): The default success message to display if the API
            response does not provide its own "message" field on success.

    Returns:
        Dict[str, Any]: The `data` part of the API response dictionary if the
        call was successful. Returns an empty dictionary if no "data" key
        was present in the successful response.

    Raises:
        click.Abort: If the API response's "status" key is "error". The error
            message printed to the console will be taken from the response's
            "message" key, or a generic error if that's also missing.
    """
    if response.get("status") == "error":
        message = response.get("message", "An unknown error occurred.")
        click.secho(f"Error: {message}", fg="red")
        raise click.Abort()

    message = response.get("message", success_msg)
    click.secho(f"Success: {message}", fg="green")
    return response.get("data", {})


class ServerNameValidator(Validator):
    """A `questionary.Validator` to check for valid server name characters.

    This validator is used with `questionary` prompts to ensure that the
    server name entered by the user conforms to the allowed character set
    and format rules defined in the backend API
    (via :func:`~bedrock_server_manager.api.utils.validate_server_name_format`).
    """

    def validate(self, document) -> None:
        """Validates the server name format using the `api_utils.validate_server_name_format`.

        Args:
            document: The `questionary`
                document object containing the user's input text.

        Raises:
            questionary.ValidationError: If the server name format is invalid,
                displaying the error message from the API.
        """
        name = document.text.strip()
        response = api_utils.validate_server_name_format(name)
        if response.get("status") == "error":
            raise ValidationError(
                message=response.get("message", "Invalid server name format."),
                cursor_position=len(document.text),
            )


class ServerExistsValidator(Validator):
    """A `questionary.Validator` to check if a server already exists.

    This validator is used with `questionary` prompts to ensure that the
    server name entered by the user corresponds to an existing and valid
    server installation, as determined by the backend API
    (via :func:`~bedrock_server_manager.api.utils.validate_server_exist`).
    """

    def validate(self, document) -> None:
        """Validates that the server name exists using `api_utils.validate_server_exist`.

        Args:
            document: The `questionary`
                document object containing the user's input text.

        Raises:
            questionary.ValidationError: If the server does not exist or if the
                name is otherwise considered invalid by the API.
        """
        server_name = document.text.strip()
        if (
            not server_name
        ):  # Allow empty input initially, might be handled by prompt itself
            return
        response = api_utils.validate_server_exist(server_name)
        if response.get("status") != "success":
            raise ValidationError(
                message=response.get("message", "Server not found or is invalid."),
                cursor_position=len(document.text),
            )


def get_server_name_interactively() -> Optional[str]:
    """Interactively prompts the user to select an existing server.

    It first attempts to fetch and display a list of existing servers for
    selection using `questionary.select`. If no servers are found or if fetching
    fails, it falls back to a `questionary.text` input prompt, validating
    the input using :class:`~.ServerExistsValidator`.

    Returns:
        Optional[str]: The validated server name as a string if a server is
        selected or entered. Returns ``None`` if the user cancels the operation
        (e.g., by pressing Ctrl+C or selecting a "Cancel" option).
    """
    try:
        response = api_application.get_all_servers_data()
        servers = response.get("data", {}).get("servers")
        if servers is None:
            servers = response.get("servers", [])
        server_names = sorted([s["name"] for s in servers if "name" in s])

        if server_names:
            choice = questionary.select(
                "Select a server:", choices=server_names + ["Cancel"]
            ).ask()
            return choice if choice and choice != "Cancel" else None
        else:
            click.secho("No existing servers found.", fg="yellow")
            return questionary.text(
                "Enter the server name:", validate=ServerExistsValidator()
            ).ask()

    except (KeyboardInterrupt, EOFError, click.Abort):
        click.secho("\nOperation cancelled.", fg="yellow")
        return None


class PropertyValidator(Validator):
    """A `questionary.Validator` for a specific server property value.

    Attributes:
        property_name (str): The name of the server property this validator is for.
    """

    def __init__(self, property_name: str):
        """Initializes the validator with the specific server property name.

        Args:
            property_name (str): The name of the server property to validate
                (e.g., 'level-name', 'server-port'). This name is passed to the
                API for validation.
        """
        self.property_name = property_name

    def validate(self, document) -> None:
        """Validates the property value using `config_api.validate_server_property_value`.

        Args:
            document: The `questionary`
                document object containing the user's input text for the property value.

        Raises:
            questionary.ValidationError: If the property value is considered
                invalid by the API for the specified `property_name`.
        """
        value = document.text.strip()
        response = config_api.validate_server_property_value(self.property_name, value)
        if response.get("status") == "error":
            raise ValidationError(
                message=response.get("message", "Invalid value."),
                cursor_position=len(document.text),
            )


# --- Standalone Utility Commands ---


def _print_server_table(servers: List[Dict[str, Any]]):
    """Prints a formatted table of server information to the console.

    This is an internal helper function used by `list-servers` to display
    server data in a structured, colored table format.

    Args:
        servers (List[Dict[str, Any]]): A list of server data dictionaries.
            Each dictionary is expected to have "name", "status", and "version"
            keys.
    """
    header = f"{'SERVER NAME':<25} {'STATUS':<15} {'VERSION'}"
    click.secho(header, bold=True)
    click.echo("-" * 65)

    if not servers:
        click.echo("  No servers found.")
    else:
        for server_data in servers:
            name = server_data.get("name", "N/A")
            status = server_data.get("status", "UNKNOWN").upper()
            version = server_data.get("version", "UNKNOWN")

            color_map = {
                "RUNNING": "green",
                "STOPPED": "red",
                "STARTING": "yellow",
                "STOPPING": "yellow",
                "INSTALLING": "bright_cyan",
                "UPDATING": "bright_cyan",
                "INSTALLED": "bright_magenta",
                "UPDATED": "bright_magenta",
                "UNKNOWN": "bright_black",
            }
            status_color = color_map.get(status, "red")

            status_styled = click.style(f"{status:<10}", fg=status_color)
            name_styled = click.style(name, fg="cyan")
            version_styled = click.style(version, fg="bright_white")

            click.echo(f"  {name_styled:<38} {status_styled:<20} {version_styled}")
    click.echo("-" * 65)


@click.command("list-servers")
@click.option(
    "--loop", is_flag=True, help="Continuously refresh server statuses every 5 seconds."
)
@click.option("--server-name", help="Display status for only a specific server.")
def list_servers(loop: bool, server_name: Optional[str]):
    """
    Lists all configured Bedrock servers and their current operational status.

    This command retrieves data for all known servers via the API and displays
    it in a formatted table. It can optionally filter by a specific server name
    or run in a continuous loop, refreshing the status display every 5 seconds.

    The status of each server (e.g., "RUNNING", "STOPPED") is color-coded for
    better readability.
    """

    def _display_status():
        response = api_application.get_all_servers_data()
        all_servers = response.get("data", {}).get("servers")
        if all_servers is None:
            all_servers = response.get("servers", [])

        if server_name:
            servers_to_show = [s for s in all_servers if s.get("name") == server_name]
        else:
            servers_to_show = all_servers

        _print_server_table(servers_to_show)

    try:
        if loop:
            while True:
                click.clear()
                click.secho(
                    "--- Bedrock Servers Status (Press CTRL+C to exit) ---",
                    fg="magenta",
                    bold=True,
                )
                _display_status()
                time.sleep(5)
        else:
            if not server_name:
                click.secho("--- Bedrock Servers Status ---", fg="magenta", bold=True)
            _display_status()

    except (KeyboardInterrupt, click.Abort):
        click.secho("\nExiting status monitor.", fg="green")
    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")

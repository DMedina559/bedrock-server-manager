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

These utilities aim to promote code reuse and provide a consistent user
experience across different parts of the CLI.
"""

import logging

import click

from ..api.models.common import ActionResponse, SuccessResponse

logger = logging.getLogger(__name__)


# --- Shared Helpers ---


def handle_api_response(
    response: ActionResponse | SuccessResponse, success_msg: str
) -> None:
    """Display a validated API result; operation failures raise at the API boundary."""
    message = response.message or success_msg
    if response.status == "skipped":
        click.secho(f"Skipped: {message}", fg="yellow")
    else:
        click.secho(f"Success: {message}", fg="green")

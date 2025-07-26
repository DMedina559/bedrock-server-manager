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

import functools
import logging
import platform
import time
from typing import Any, Callable, Dict, List, Optional

import click
import questionary
from questionary import ValidationError, Validator

from ..api import (
    application as api_application,
    server_install_config as config_api,
    utils as api_utils,
)
from ..error import BSMError

logger = logging.getLogger(__name__)


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

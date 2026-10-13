# bedrock_server_manager/cli/utils.py
"""Command-Line Interface (CLI) Utilities."""

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
    elif response.status == "partial":
        click.secho(f"Partial: {message}", fg="yellow")
        raise click.ClickException("Operation completed with failures.")
    else:
        click.secho(f"Success: {message}", fg="green")

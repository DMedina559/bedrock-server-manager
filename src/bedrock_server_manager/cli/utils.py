# bedrock_server_manager/cli/utils.py
"""Command-Line Interface (CLI) Utilities."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import click

from ..models.common import ActionResponse, SuccessResponse

if TYPE_CHECKING:
    from ..context import AppContext

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


def assert_bsm_offline_cli(
    app_context: AppContext | Any = None,
    *,
    config_dir: str | None = None,
    data_dir: str | None = None,
    db_url: str | None = None,
    operation_name: str = "This operation",
) -> None:
    """Ensure BSM is offline before performing destructive maintenance operations."""
    from ..utils.general import run_async
    from ..web.process import check_bsm_offline

    c_dir = (
        config_dir
        or (getattr(app_context, "config_dir", None) if app_context else None)
        or ""
    )
    d_dir = (
        data_dir
        or (getattr(app_context, "data_dir", None) if app_context else None)
        or ""
    )
    d_url = (
        db_url or (getattr(app_context, "db_url", None) if app_context else None) or ""
    )

    res = check_bsm_offline(c_dir, d_dir, d_url)
    if asyncio.iscoroutine(res):
        is_offline, pid = run_async(res)
    else:
        is_offline, pid = res

    if not is_offline:
        raise click.ClickException(
            f"Bedrock Server Manager is currently running (PID {pid}).\n"
            f"{operation_name} requires BSM to be stopped first.\n"
            "Please stop BSM using 'bsm web stop' (or stop the system service) and retry."
        )

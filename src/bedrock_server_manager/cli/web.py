# bedrock_server_manager/cli/web.py
"""
Defines the `bsm web` command group for managing the Bedrock Server Manager Web UI.

This module provides CLI commands to control the lifecycle of the web server
application (FastAPI/Uvicorn based).

Key command groups and commands include:

    -   ``bsm web start``: Starts the web server, with options for host, port,
        debug mode, and detached/direct execution.
    -   ``bsm web stop``: Stops a detached web server process.

"""

import logging

import click

from ..api import web as web_api
from ..error import BSMError
from .utils import handle_api_response as _handle_api_response

logger = logging.getLogger(__name__)


@click.group()
def web():
    """
    Manages the Bedrock Server Manager Web UI application.

    This group of commands allows you to start and stop the web server,
    and to manage its integration as an OS-level system service for
    features like automatic startup.
    """
    pass


@web.command("start")
@click.option(
    "-H",
    "--host",
    "host",
    type=str,
    help="Host address to bind to.",
)
@click.option(
    "-p",
    "--port",
    "port",
    type=int,
    help="Port to bind to. Overrides the value in settings.",
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Run in Flask's debug mode (NOT for production).",
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["direct", "detached"], case_sensitive=False),
    default="direct",
    show_default=True,
    help="Run mode: 'direct' blocks the terminal, 'detached' runs in the background.",
)
@click.pass_context
def start_web_server(ctx: click.Context, host: str, port: int, debug: bool, mode: str):
    """
    Starts the Bedrock Server Manager web UI.

    This command launches the Uvicorn server that hosts the FastAPI web application.
    It can run in 'direct' mode (blocking the terminal, useful for development or
    when managed by an external process manager) or 'detached' mode (running in
    the background as a new process).

    The web server's listening host(s) and debug mode can be configured via options.

    Calls API: :func:`~bedrock_server_manager.api.web.start_web_server_api`.
    """
    app_context = ctx.obj["app_context"]
    click.echo(f"Attempting to start web server in '{mode}' mode...")
    if mode == "direct":
        click.secho(
            "Server will run in this terminal. Press Ctrl+C to stop.", fg="cyan"
        )

    try:
        response = web_api.start_web_server_api(
            host=host,
            port=port,
            debug=debug,
            mode=mode,
            app_context=app_context,
        )

        # In 'direct' mode, start_web_server_api (which calls bsm.start_web_ui_direct)
        # is blocking. So, we'll only reach here after it stops or if mode is 'detached'.
        if mode == "detached":
            if response.get("status") == "error":
                message = response.get("message", "An unknown error occurred.")
                click.secho(f"Error: {message}", fg="red")
                raise click.Abort()
            else:
                pid = response.get("pid", "N/A")
                message = response.get(
                    "message",
                    f"Web server start initiated in detached mode (PID: {pid}).",
                )
                click.secho(f"Success: {message}", fg="green")
        elif (
            response and response.get("status") == "error"
        ):  # Should only happen if direct mode itself fails to launch
            message = response.get(
                "message", "Failed to start web server in direct mode."
            )
            click.secho(f"Error: {message}", fg="red")
            raise click.Abort()

    except BSMError as e:  # Catch errors from API if they propagate
        click.secho(f"Failed to start web server: {e}", fg="red")
        raise click.Abort()


@web.command("stop")
@click.pass_context
def stop_web_server(ctx: click.Context):
    """
    Stops a detached Bedrock Server Manager web UI process.

    This command attempts to find and terminate a web server process that was
    previously started in 'detached' mode. It typically relies on a PID file
    to identify the correct process.

    This command does not affect web servers started in 'direct' mode or those
    managed by system services.

    Calls API: :func:`~bedrock_server_manager.api.web.stop_web_server_api`.
    """
    app_context = ctx.obj["app_context"]
    click.echo("Attempting to stop the web server...")
    try:
        response = web_api.stop_web_server_api(app_context=app_context)
        _handle_api_response(response, "Web server stopped successfully.")
    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()

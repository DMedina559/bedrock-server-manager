# bedrock_server_manager/cli/web.py
"""
Defines the `bsm web` command group for managing the Bedrock Server Manager Web UI.

This module provides CLI commands to control the lifecycle of the web server
application (FastAPI/Uvicorn based) and to manage its integration as an
OS-level system service (e.g., systemd on Linux, Windows Services on Windows).

Key command groups and commands include:

    -   ``bsm web start``: Starts the web server, with options for host, port,
        debug mode, and detached/direct execution.
    -   ``bsm web stop``: Stops a detached web server process.
    -   ``bsm web service ...``: A subgroup for managing the Web UI's system service:
        -   ``bsm web service configure``: Interactively or directly configures the
            Web UI system service (creation, autostart).
        -   ``bsm web service enable``: Enables the Web UI service for autostart.
        -   ``bsm web service disable``: Disables autostart for the Web UI service.
        -   ``bsm web service remove``: Removes the Web UI system service definition.
        -   ``bsm web service status``: Checks the status of the Web UI system service.

Interactions with system services are contingent on the availability of
appropriate service management tools on the host OS (e.g., `systemctl` for
systemd, `pywin32` for Windows Services). The commands use functions from
:mod:`~bedrock_server_manager.api.web` and the
:class:`~bedrock_server_manager.core.manager.BedrockServerManager`.
"""

import functools
import logging
import platform
import sys
from typing import Tuple, Callable, Optional, List, Any

import click
import questionary

from bedrock_server_manager.api import web as web_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.error import (
    BSMError,
    MissingArgumentError,
)

logger = logging.getLogger(__name__)


# --- Web System Service ---
def requires_web_service_manager(func: Callable) -> Callable:
    """
    A decorator to ensure Web UI service management commands only run on capable systems.

    This decorator checks if the system has a supported service manager
    (e.g., systemd for Linux, or `pywin32` installed for Windows services)
    by inspecting `bsm.can_manage_services` from the
    :class:`~.core.manager.BedrockServerManager` instance in the Click context.

    If the capability is not present, it prints an error and aborts the command.

    Args:
        func (Callable): The Click command function to decorate.

    Returns:
        Callable: The wrapped command function.
    """

    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx: click.Context, *args, **kwargs):
        bsm: BedrockServerManager = ctx.obj["bsm"]
        if not bsm.can_manage_services:
            os_type = bsm.get_os_type()
            if os_type == "Windows":
                msg = "Error: This command requires 'pywin32' to be installed (`pip install pywin32`) for Web UI service management."
            else:
                msg = "Error: This command requires a supported service manager (e.g., systemd for Linux), which was not found."
            click.secho(msg, fg="red")
            raise click.Abort()
        return func(*args, **kwargs)

    return wrapper


def _perform_web_service_configuration(
    bsm: BedrockServerManager,
    setup_service: Optional[bool],
    enable_autostart: Optional[bool],
):
    """
    Internal helper to apply Web UI service configurations via API calls.

    This non-interactive function is called by `configure_web_service` (when
    flags are used) and `interactive_web_service_workflow` to execute the
    actual service configuration changes. It only acts if the system has
    service management capabilities.

    Args:
        bsm (BedrockServerManager): The BedrockServerManager instance for
            capability checks.
        setup_service (Optional[bool]): If ``True``, attempts to create/update
            the Web UI system service.
        enable_autostart (Optional[bool]): If ``True``, enables autostart for the
            service; if ``False``, disables it. ``None`` means no change to
            autostart unless `setup_service` is also ``True``.

    Calls APIs:
        - :func:`~bedrock_server_manager.api.web.create_web_ui_service`
        - :func:`~bedrock_server_manager.api.web.enable_web_ui_service`
        - :func:`~bedrock_server_manager.api.web.disable_web_ui_service`

    Raises:
        click.Abort: If API calls handled by `_handle_api_response` report errors.
    """
    if not bsm.can_manage_services:
        click.secho(
            "System service manager not available. Skipping Web UI service configuration.",
            fg="yellow",
        )
        return

    if setup_service:
        # When setting up the service, enable_autostart choice (even if None)
        # is passed to create_web_ui_service, which might have its own default.
        enable_flag = (
            enable_autostart if enable_autostart is not None else False
        )  # Default to False if not specified alongside setup
        os_type = bsm.get_os_type()
        click.secho(
            f"\n--- Configuring Web UI System Service ({os_type}) ---", bold=True
        )
        response = web_api.create_web_ui_service(autostart=enable_flag)
        _handle_api_response(response, "Web UI system service configured successfully.")
    elif (
        enable_autostart is not None
    ):  # Only change autostart if setup_service is False but autostart is specified
        click.echo("Applying autostart setting to existing Web UI service...")
        if enable_autostart:
            response = web_api.enable_web_ui_service()
            _handle_api_response(response, "Web UI service enabled successfully.")
        else:
            response = web_api.disable_web_ui_service()
            _handle_api_response(response, "Web UI service disabled successfully.")


def interactive_web_service_workflow(bsm: BedrockServerManager):
    """
    Guides the user through an interactive session to configure the Web UI system service.

    Uses `questionary` to prompt for:

        - Creating/updating the system service.
        - Enabling/disabling autostart for the service.

    Args:
        bsm (BedrockServerManager): The BedrockServerManager instance.
    """
    click.secho("\n--- Interactive Web UI Service Configuration ---", bold=True)
    setup_service_choice = None
    enable_autostart_choice = None

    if bsm.can_manage_services:
        os_type = bsm.get_os_type()
        service_type_str = (
            "Systemd Service (Linux)" if os_type == "Linux" else "Windows Service"
        )
        click.secho(f"\n--- {service_type_str} for Web UI ---", bold=True)
        if os_type == "Windows":
            click.secho(
                "(Note: This requires running the command as an Administrator)",
                fg="yellow",
            )

        if questionary.confirm(
            f"Create or update the {service_type_str} for the Web UI?", default=True
        ).ask():
            setup_service_choice = True
            autostart_prompt = (
                "Enable the Web UI service to start automatically when you log in?"
                if os_type == "Linux"
                else "Enable the Web UI service to start automatically when the system boots?"
            )
            enable_autostart_choice = questionary.confirm(
                autostart_prompt, default=False
            ).ask()
    else:
        click.secho(
            "\nSystem service manager not available. Skipping Web UI service setup.",
            fg="yellow",
        )
        return

    if setup_service_choice is None:
        click.secho("No changes selected for Web UI service.", fg="cyan")
        return

    click.echo("\nApplying chosen settings for Web UI service...")
    try:
        _perform_web_service_configuration(
            bsm=bsm,
            setup_service=setup_service_choice,
            enable_autostart=enable_autostart_choice,
        )
        click.secho("\nWeb UI service configuration complete.", fg="green", bold=True)
    except BSMError as e:
        click.secho(f"Error during Web UI service configuration: {e}", fg="red")
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")


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
    "hosts",
    multiple=True,
    help="Host address to bind to. Use multiple times for multiple hosts.",
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
def start_web_server(hosts: Tuple[str], debug: bool, mode: str):
    """
    Starts the Bedrock Server Manager web UI.

    This command launches the Uvicorn server that hosts the FastAPI web application.
    It can run in 'direct' mode (blocking the terminal, useful for development or
    when managed by an external process manager) or 'detached' mode (running in
    the background as a new process).

    The web server's listening host(s) and debug mode can be configured via options.

    Calls API: :func:`~bedrock_server_manager.api.web.start_web_server_api`.
    """
    click.echo(f"Attempting to start web server in '{mode}' mode...")
    if mode == "direct":
        click.secho(
            "Server will run in this terminal. Press Ctrl+C to stop.", fg="cyan"
        )

    try:
        host_list = (
            list(hosts) if hosts else None
        )  # Pass None if no hosts are provided, API handles default
        response = web_api.start_web_server_api(host_list, debug, mode)

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
def stop_web_server():
    """
    Stops a detached Bedrock Server Manager web UI process.

    This command attempts to find and terminate a web server process that was
    previously started in 'detached' mode. It typically relies on a PID file
    to identify the correct process.

    This command does not affect web servers started in 'direct' mode or those
    managed by system services.

    Calls API: :func:`~bedrock_server_manager.api.web.stop_web_server_api`.
    """
    click.echo("Attempting to stop the web server...")
    try:
        response = web_api.stop_web_server_api()
        _handle_api_response(response, "Web server stopped successfully.")
    except BSMError as e:
        click.secho(f"An error occurred: {e}", fg="red")
        raise click.Abort()


@web.group("service")
def web_service_group():
    """
    Manages OS-level service integrations for the Web UI application.

    This group contains commands to configure, enable, disable, remove, and
    check the status of the system service (systemd on Linux, Windows Service
    on Windows) for the Bedrock Server Manager Web UI.
    """
    pass


@web_service_group.command("configure")
@click.option(
    "--setup-service",
    is_flag=True,
    help="Create or update the system service file for the Web UI.",
)
@click.option(
    "--enable-autostart/--no-enable-autostart",
    "autostart_flag",
    default=None,
    help="Enable or disable Web UI service autostart.",
)
@click.pass_context
def configure_web_service(
    ctx: click.Context,
    setup_service: bool,
    autostart_flag: Optional[bool],
):
    """
    Configures the OS-level system service for the Web UI application.

    This command allows setting up the Web UI to run as a system service,
    enabling features like automatic startup on boot/login.

    If run without any specific configuration flags (`--setup-service`,
    `--enable-autostart`), it launches an interactive wizard
    (:func:`~.interactive_web_service_workflow`) to guide the user.

    If flags are provided, it applies those settings directly. The command
    respects system capabilities (e.g., won't attempt service setup if a
    service manager isn't available or `pywin32` is missing on Windows).

    Calls internal helpers:

        - :func:`~.interactive_web_service_workflow` (if no flags)
        - :func:`~._perform_web_service_configuration` (if flags are present)

    """
    bsm: BedrockServerManager = ctx.obj["bsm"]
    if setup_service and not bsm.can_manage_services:
        click.secho(
            "Error: --setup-service is not available (service manager not found).",
            fg="red",
        )
        raise click.Abort()

    try:
        no_flags_used = not setup_service and autostart_flag is None

        if no_flags_used:
            click.secho(
                "No flags provided; starting interactive Web UI service setup...",
                fg="yellow",
            )
            interactive_web_service_workflow(bsm)
            return

        click.secho("\nApplying Web UI service configuration...", bold=True)
        _perform_web_service_configuration(
            bsm=bsm,
            setup_service=setup_service,
            enable_autostart=autostart_flag,
        )
        click.secho("\nWeb UI configuration applied successfully.", fg="green")
    except MissingArgumentError as e:
        click.secho(f"Configuration Error: {e}", fg="red")
    except BSMError as e:
        click.secho(f"Operation failed: {e}", fg="red")
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")


@web_service_group.command("enable")
@requires_web_service_manager
def enable_web_service_cli():
    """
    Enables the Web UI system service for automatic startup.

    Configures the OS service for the Web UI (systemd on Linux, Windows Service
    on Windows) to start automatically when the system boots or user logs in.

    Requires a supported service manager (checked by decorator).

    Calls API: :func:`~bedrock_server_manager.api.web.enable_web_ui_service`.
    """
    click.echo("Attempting to enable Web UI system service...")
    try:
        response = web_api.enable_web_ui_service()
        _handle_api_response(response, "Web UI service enabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to enable Web UI service: {e}", fg="red")
        raise click.Abort()


@web_service_group.command("disable")
@requires_web_service_manager
def disable_web_service_cli():
    """
    Disables the Web UI system service from starting automatically.

    Configures the OS service for the Web UI to not start automatically.

    Requires a supported service manager (checked by decorator).

    Calls API: :func:`~bedrock_server_manager.api.web.disable_web_ui_service`.
    """
    click.echo("Attempting to disable Web UI system service...")
    try:
        response = web_api.disable_web_ui_service()
        _handle_api_response(response, "Web UI service disabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to disable Web UI service: {e}", fg="red")
        raise click.Abort()


@web_service_group.command("remove")
@requires_web_service_manager
def remove_web_service_cli():
    """
    Removes the Web UI system service definition from the OS.

    .. danger::
        This is a destructive operation. The service definition will be
        deleted from the system.

    Prompts for confirmation before proceeding.
    Requires a supported service manager (checked by decorator).

    Calls API: :func:`~bedrock_server_manager.api.web.remove_web_ui_service`.
    """
    if not questionary.confirm(
        "Are you sure you want to remove the Web UI system service?", default=False
    ).ask():
        click.secho("Removal cancelled.", fg="yellow")
        return
    click.echo("Attempting to remove Web UI system service...")
    try:
        response = web_api.remove_web_ui_service()
        _handle_api_response(response, "Web UI service removed successfully.")
    except BSMError as e:
        click.secho(f"Failed to remove Web UI service: {e}", fg="red")
        raise click.Abort()


@web_service_group.command("status")
@requires_web_service_manager
def status_web_service_cli():
    """
    Checks and displays the status of the Web UI system service.

    Reports whether the service definition exists, if it's currently
    active (running), and if it's enabled for autostart.

    Requires a supported service manager (checked by decorator).

    Calls API: :func:`~bedrock_server_manager.api.web.get_web_ui_service_status`.
    """
    click.echo("Checking Web UI system service status...")
    try:
        response = web_api.get_web_ui_service_status()
        if response.get("status") == "success":
            click.secho("Web UI Service Status:", bold=True)
            click.echo(
                f"  Service Defined: {click.style(str(response.get('service_exists', False)), fg='cyan')}"
            )
            if response.get("service_exists"):
                click.echo(
                    f"  Currently Active (Running): {click.style(str(response.get('is_active', False)), fg='green' if response.get('is_active') else 'red')}"
                )
                click.echo(
                    f"  Enabled for Autostart: {click.style(str(response.get('is_enabled', False)), fg='green' if response.get('is_enabled') else 'red')}"
                )
            if response.get("message"):
                click.secho(f"  Info: {response.get('message')}", fg="yellow")
        else:
            _handle_api_response(response)
    except BSMError as e:
        click.secho(f"Failed to get Web UI service status: {e}", fg="red")
        raise click.Abort()

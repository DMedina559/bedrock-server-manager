# bedrock_server_manager/cli/system.py
"""
Defines the `bsm system` command group for OS-level server integrations and monitoring.

This module provides CLI commands and interactive workflows to manage system-level
aspects of both individual Bedrock server instances and the Bedrock Server Manager
Web UI application itself. Key functionalities include:

    -   **Server Service Management:**
        -   ``bsm system configure-service``: Interactively or directly configures
            system services (systemd on Linux, Windows Service on Windows) for a
            specific Bedrock server, including autostart and autoupdate settings.
        -   ``bsm system enable-service``: Enables a server's system service for autostart.
        -   ``bsm system disable-service``: Disables a server's system service autostart.
    -   **Web UI Service Management (via `bsm web service` commands - defined in `cli.web.py` but relevant context):**
        -   Manages the system service for the main Web UI application.
    -   **Resource Monitoring:**
        -   ``bsm system monitor``: Continuously displays CPU and memory usage for a
            specified running server process.
    -   **Interactive Workflows:**
        -   :func:`~.interactive_service_workflow`: A helper function that guides users
            through configuring system services for a server.
    -   **Decorators & Helpers:**
        -   :func:`~.requires_service_manager`: A Click command decorator that checks
            if the host system has a supported service manager (systemd or pywin32
            for Windows Services) before allowing a command to run.
        -   `_perform_service_configuration`: Internal helper for applying configurations.

Commands in this module typically interact with the API functions defined in
:mod:`~bedrock_server_manager.api.system` and rely on the
:class:`~bedrock_server_manager.core.manager.BedrockServerManager` for
capability checks and settings access.
"""

import functools
import logging
import time
import platform
import sys
from typing import Callable, Optional, Any

import click
import questionary

from bedrock_server_manager.api import system as system_api
from bedrock_server_manager.cli.utils import handle_api_response as _handle_api_response
from bedrock_server_manager.core.manager import BedrockServerManager
from bedrock_server_manager.error import BSMError

if platform.system() == "Windows":
    from bedrock_server_manager.core.system.windows_class import (
        BedrockServerWindowsService,
        PYWIN32_AVAILABLE,
    )

    if PYWIN32_AVAILABLE:
        import win32serviceutil
        import servicemanager

logger = logging.getLogger(__name__)


def requires_service_manager(func: Callable) -> Callable:
    """
    A Click command decorator that restricts command execution to systems
    with a recognized and available OS service manager.

    This decorator inspects the :class:`~.core.manager.BedrockServerManager`
    instance (expected in `ctx.obj['bsm']`) to determine if the host system
    has the necessary capabilities for service management (e.g., `systemctl`
    on Linux, or `pywin32` for Windows Services on Windows).

    If the capability is missing, an informative error message is printed,
    and the command execution is aborted using `click.Abort`.

    Args:
        func (Callable): The Click command function to be decorated.

    Returns:
        Callable: The decorated function, which includes the pre-execution
        capability check.
    """

    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx: click.Context, *args, **kwargs):
        """Wrapper that performs the capability check before execution."""
        bsm: BedrockServerManager = ctx.obj["bsm"]
        if not bsm.can_manage_services:
            os_type = bsm.get_os_type()
            if os_type == "Windows":
                msg = "Error: This command requires 'pywin32' to be installed (`pip install pywin32`)."
            else:  # Primarily targets Linux/systemd here
                msg = "Error: This command requires a service manager (e.g., systemd for Linux), which was not found or is not supported."
            click.secho(msg, fg="red")
            raise click.Abort()
        return func(*args, **kwargs)

    return wrapper


def _perform_service_configuration(
    bsm: BedrockServerManager,
    server_name: str,
    autoupdate: Optional[bool],
    setup_service: Optional[bool],
    enable_autostart: Optional[bool],
):
    """
    Internal helper to apply service configurations by calling the system API.

    This non-interactive function serves as the backend logic for applying
    service-related settings. It only processes configuration options that are
    explicitly provided (not ``None``) and respects the system's detected
    capabilities (e.g., presence of a service manager).

    Args:
        bsm (BedrockServerManager): The central BedrockServerManager instance,
            used for capability checks and potentially passing to API calls.
        server_name (str): The name of the server to configure.
        autoupdate (Optional[bool]): The desired state for the server's
            autoupdate setting. If ``None``, this setting is not changed.
        setup_service (Optional[bool]): If ``True``, creates or updates the system
            service for the server. If ``None`` or ``False`` (and `enable_autostart`
            is also ``None``), service creation/update is skipped.
        enable_autostart (Optional[bool]): Sets the system service's autostart
            state (enabled or disabled). If ``None``, this setting is not changed
            unless `setup_service` is also ``True`` (in which case it might default
            based on `setup_service`'s logic).

    Raises:
        BSMError: If any of the underlying API calls
            (e.g., :func:`~bedrock_server_manager.api.system.set_autoupdate`,
            :func:`~bedrock_server_manager.api.system.create_server_service`)
            fail and raise an exception that isn't handled by `_handle_api_response`
            (which would `click.Abort`).
        click.Abort: If `_handle_api_response` detects an API error.
    """
    if autoupdate is not None:
        autoupdate_value = "true" if autoupdate else "false"
        response = system_api.set_autoupdate(server_name, autoupdate_value)
        _handle_api_response(
            response, f"Autoupdate setting configured to '{autoupdate_value}'."
        )

    # Only proceed with service configuration if the capability exists.
    if bsm.can_manage_services:
        if setup_service:
            enable_flag = enable_autostart if enable_autostart is not None else False
            os_type = bsm.get_os_type()
            click.secho(f"\n--- Configuring System Service ({os_type}) ---", bold=True)
            response = system_api.create_server_service(server_name, enable_flag)
            _handle_api_response(response, "System service configured successfully.")
        elif enable_autostart is not None:
            # Handle enabling/disabling an existing service if setup is not requested.
            click.echo("Applying autostart setting to existing service...")
            if enable_autostart:
                response = system_api.enable_server_service(server_name)
                _handle_api_response(response, "Service enabled successfully.")
            else:
                response = system_api.disable_server_service(server_name)
                _handle_api_response(response, "Service disabled successfully.")


def interactive_service_workflow(bsm: BedrockServerManager, server_name: str):
    """
    Guides the user through an interactive session to configure server services.

    This function uses `questionary` prompts to ask the user about:
    1.  Enabling/disabling autoupdate on server start.
    2.  Creating/updating the system service (systemd/Windows Service), if a
        service manager is available on the host system.
    3.  Enabling/disabling autostart for the system service, if service setup
        is chosen.

    Based on the user's responses, it then calls
    :func:`~._perform_service_configuration` to apply the changes.

    Args:
        bsm (BedrockServerManager): The initialized BedrockServerManager instance,
            used to check system capabilities (e.g., `bsm.can_manage_services`).
        server_name (str): The name of the server for which services are being
            configured. This is used in prompts and passed to configuration functions.
    """
    click.secho(
        f"\n--- Interactive Service Configuration for '{server_name}' ---", bold=True
    )

    # 1. Gather Autoupdate preference.
    autoupdate_choice = questionary.confirm(
        "Enable check for updates when the server starts?", default=False
    ).ask()

    # 2. Gather system service preferences, only if available.
    setup_service_choice = None
    enable_autostart_choice = None
    if bsm.can_manage_services:
        os_type = bsm.get_os_type()
        service_type_str = (
            "Systemd Service (Linux)" if os_type == "Linux" else "Windows Service"
        )
        click.secho(f"\n--- {service_type_str} ---", bold=True)
        if os_type == "Windows":
            click.secho(
                "(Note: This requires running the command as an Administrator)",
                fg="yellow",
            )

        if questionary.confirm(
            f"Create or update the {service_type_str} for this server?",
            default=True,
        ).ask():
            setup_service_choice = True
            autostart_prompt = (
                "Enable the service to start automatically when you log in?"
                if os_type == "Linux"
                else "Enable the service to start automatically when the system boots?"
            )
            enable_autostart_choice = questionary.confirm(
                autostart_prompt,
                default=False,
            ).ask()
    else:
        click.secho(
            "\nSystem service manager not available. Skipping service setup.",
            fg="yellow",
        )

    # 3. Execute the configuration.
    if autoupdate_choice is None and setup_service_choice is None:
        click.secho("No changes selected.", fg="cyan")
        return

    click.echo("\nApplying chosen settings...")
    _perform_service_configuration(
        bsm=bsm,
        server_name=server_name,
        autoupdate=autoupdate_choice,
        setup_service=setup_service_choice,
        enable_autostart=enable_autostart_choice,
    )
    click.secho("\nService configuration complete.", fg="green", bold=True)


@click.group()
def system():
    """
    Manages OS-level integrations and server resource monitoring.

    This command group includes subcommands for configuring system services
    (like systemd on Linux or Windows Services) for individual Bedrock servers
    to enable features like autostart. It also provides tools for monitoring
    the resource usage (CPU, memory) of running server processes.
    """
    pass


@system.command("configure-service")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server to configure.",
)
@click.option(
    "--autoupdate/--no-autoupdate",
    "autoupdate_flag",
    default=None,
    help="Enable or disable checking for updates on server start.",
)
@click.option(
    "--setup-service",
    is_flag=True,
    help="Create or update the system service file (systemd/Windows Service).",
)
@click.option(
    "--enable-autostart/--no-enable-autostart",
    "autostart_flag",
    default=None,
    help="Enable or disable the system service to start on boot/login.",
)
@click.pass_context
def configure_service(
    ctx: click.Context,
    server_name: str,
    autoupdate_flag: Optional[bool],
    setup_service: bool,
    autostart_flag: Optional[bool],
):
    """
    Configures OS-specific service settings for a Bedrock server.

    This command allows setting up a server to run as a system service
    (systemd on Linux, Windows Service on Windows), enabling features like
    automatic startup on boot/login and automatic updates on server start.

    If run without any specific configuration flags (like `--autoupdate` or
    `--setup-service`), it launches an interactive wizard
    (:func:`~.interactive_service_workflow`) to guide the user through the
    available options.

    If configuration flags are provided, it applies those settings directly,
    making it suitable for scripting or non-interactive use. The command
    respects system capabilities (e.g., it won't attempt service setup if
    a service manager isn't available).

    The command can be used with flags like ``--autoupdate`` / ``--no-autoupdate``,
    ``--setup-service``, and ``--enable-autostart`` / ``--no-enable-autostart``
    for direct configuration. The ``--setup-service`` flag requires a supported
    service manager on the system.

    It calls API functions from :mod:`~bedrock_server_manager.api.system`
    indirectly via :func:`~._perform_service_configuration`.
    """
    bsm: BedrockServerManager = ctx.obj["bsm"]

    # Add a guard clause to prevent misuse of flags on incapable systems.
    if setup_service and not bsm.can_manage_services:
        click.secho(
            "Error: --setup-service flag is not available because a service manager was not found.",
            fg="red",
        )
        return

    try:
        no_flags_used = (
            autoupdate_flag is None and not setup_service and autostart_flag is None
        )
        if no_flags_used:
            click.secho(
                "No configuration flags provided; starting interactive setup...",
                fg="yellow",
            )
            interactive_service_workflow(bsm, server_name)
            return

        click.secho(
            f"\nApplying service configuration for '{server_name}'...", bold=True
        )
        _perform_service_configuration(
            bsm=bsm,
            server_name=server_name,
            autoupdate=autoupdate_flag,
            setup_service=setup_service,
            enable_autostart=autostart_flag,
        )
        click.secho("\nConfiguration applied successfully.", fg="green")

    except (BSMError, click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")


@system.command("enable-service")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server service to enable.",
)
@requires_service_manager
def enable_service(server_name: str):
    """
    Enables a server's system service for automatic startup.

    This command configures the OS service (systemd on Linux, Windows Service
    on Windows) associated with the specified server to start automatically
    when the system boots or when the user logs in (depending on service type).

    It requires a supported service manager to be available on the system,
    checked by the `@requires_service_manager` decorator.

    Calls API: :func:`~bedrock_server_manager.api.system.enable_server_service`.
    """
    click.echo(f"Attempting to enable system service for '{server_name}'...")
    try:
        response = system_api.enable_server_service(server_name)
        _handle_api_response(response, "Service enabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to enable service: {e}", fg="red")
        raise click.Abort()


@system.command("disable-service")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server service to disable.",
)
@requires_service_manager
def disable_service(server_name: str):
    """
    Disables a server's system service from starting automatically.

    This command configures the OS service (systemd on Linux, Windows Service
    on Windows) for the specified server to not start automatically on
    system boot or user login.

    It requires a supported service manager, checked by the
    `@requires_service_manager` decorator.

    Calls API: :func:`~bedrock_server_manager.api.system.disable_server_service`.
    """
    click.echo(f"Attempting to disable system service for '{server_name}'...")
    try:
        response = system_api.disable_server_service(server_name)
        _handle_api_response(response, "Service disabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to disable service: {e}", fg="red")
        raise click.Abort()


@system.command("monitor")
@click.option(
    "-s",
    "--server",
    "server_name",
    required=True,
    help="Name of the server to monitor.",
)
def monitor_usage(server_name: str):
    """
    Continuously monitors CPU and memory usage of a specific server process.

    This command repeatedly fetches and displays the Process ID (PID),
    CPU percentage, memory usage (in MB), and uptime for the specified
    server's running process. The display refreshes every 2 seconds.

    Press CTRL+C to stop monitoring. This feature relies on the `psutil`
    library being available for detailed process information.

    Calls API: :func:`~bedrock_server_manager.api.system.get_bedrock_process_info`
    in a loop.
    """
    click.secho(
        f"Starting resource monitoring for server '{server_name}'. Press CTRL+C to exit.",
        fg="cyan",
    )
    time.sleep(1)

    try:
        while True:
            response = system_api.get_bedrock_process_info(server_name)

            click.clear()
            click.secho(
                f"--- Monitoring Server: {server_name} ---", fg="magenta", bold=True
            )
            click.echo(
                f"(Last updated: {time.strftime('%H:%M:%S')}, Press CTRL+C to exit)\n"
            )

            if response.get("status") == "error":
                click.secho(f"Error: {response.get('message')}", fg="red")
            elif response.get("process_info") is None:
                click.secho("Server process not found (is it running?).", fg="yellow")
            else:
                info = response["process_info"]
                pid_str = info.get("pid", "N/A")
                cpu_str = f"{info.get('cpu_percent', 0.0):.1f}%"
                mem_str = f"{info.get('memory_mb', 0.0):.1f} MB"
                uptime_str = info.get("uptime", "N/A")

                click.echo(f"  {'PID':<15}: {click.style(str(pid_str), fg='cyan')}")
                click.echo(f"  {'CPU Usage':<15}: {click.style(cpu_str, fg='green')}")
                click.echo(
                    f"  {'Memory Usage':<15}: {click.style(mem_str, fg='green')}"
                )
                click.echo(f"  {'Uptime':<15}: {click.style(uptime_str, fg='white')}")

            time.sleep(2)
    except (KeyboardInterrupt, click.Abort):
        click.secho("\nMonitoring stopped.", fg="green")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    system()

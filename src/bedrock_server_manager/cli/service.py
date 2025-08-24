# bedrock_server_manager/cli/web.py
"""
Defines the `bsm web` command group for managing the Bedrock Server Manager Web UI.

This module provides CLI commands to control the web server
application (FastAPI/Uvicorn based) integration as an
OS-level system service (e.g., systemd on Linux, Windows Services on Windows).

Key command groups and commands include:

    -   ``bsm service ...``: A subgroup for managing the Web UI's system service:
        -   ``bsm service configure``: Interactively or directly configures the
            Web UI system service (creation, autostart).
        -   ``bsm service enable``: Enables the Web UI service for autostart.
        -   ``bsm service disable``: Disables autostart for the Web UI service.
        -   ``bsm service remove``: Removes the Web UI system service definition.
        -   ``bsm service status``: Checks the status of the Web UI system service.

Interactions with system services are contingent on the availability of
appropriate service management tools on the host OS (e.g., `systemctl` for
systemd, `pywin32` for Windows Services). The commands use functions from
:mod:`~bedrock_server_manager.api.web` and the
:class:`~bedrock_server_manager.core.manager.BedrockServerManager`.
"""

import functools
import logging
import sys
from typing import Callable, Optional

import click
import questionary

from ..api import web as web_api
from .utils import handle_api_response as _handle_api_response
from ..context import AppContext
from ..core import BedrockServerManager
from ..error import (
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
        app_context: AppContext = ctx.obj["app_context"]
        bsm = app_context.manager
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
    app_context: AppContext,
    setup_service: Optional[bool],
    enable_autostart: Optional[bool],
    system: bool = False,
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    """
    Internal helper to apply Web UI service configurations via API calls.

    This non-interactive function is called by `configure_web_service` (when
    flags are used) and `interactive_web_service_workflow` to execute the
    actual service configuration changes. It only acts if the system has
    service management capabilities.

    Args:
        app_context (AppContext): The AppContext instance for API calls.
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
    if not app_context.manager.can_manage_services:
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
        os_type = app_context.manager.get_os_type()
        click.secho(
            f"\n--- Configuring Web UI System Service ({os_type}) ---", bold=True
        )
        response = web_api.create_web_ui_service(
            app_context=app_context,
            autostart=enable_flag,
            system=system,
            username=username,
            password=password,
        )
        _handle_api_response(response, "Web UI system service configured successfully.")
    elif (
        enable_autostart is not None
    ):  # Only change autostart if setup_service is False but autostart is specified
        click.echo("Applying autostart setting to existing Web UI service...")
        if enable_autostart:
            response = web_api.enable_web_ui_service(app_context=app_context)
            _handle_api_response(response, "Web UI service enabled successfully.")
        else:
            response = web_api.disable_web_ui_service(app_context=app_context)
            _handle_api_response(response, "Web UI service disabled successfully.")


def interactive_web_service_workflow(app_context: AppContext):
    """
    Guides the user through an interactive session to configure the Web UI system service.

    Uses `questionary` to prompt for:

        - Creating/updating the system service.
        - Enabling/disabling autostart for the service.

    Args:
        app_context (AppContext): The AppContext instance.
    """
    click.secho("\n--- Interactive Web UI Service Configuration ---", bold=True)
    setup_service_choice = None
    enable_autostart_choice = None
    system_choice = False
    username = None
    password = None

    bsm = app_context.manager

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

            if os_type == "Linux":
                system_choice = questionary.confirm(
                    "Configure as a system-wide service? (Requires sudo)", default=False
                ).ask()
            elif os_type == "Windows":
                if questionary.confirm(
                    "Run the service as a specific user?", default=True
                ).ask():
                    username = questionary.text("Enter the username:").ask()
                    password = questionary.password("Enter the password:").ask()

            autostart_prompt = (
                "Enable the Web UI service to start automatically when you log in?"
                if os_type == "Linux" and not system_choice
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
            app_context=app_context,
            setup_service=setup_service_choice,
            enable_autostart=enable_autostart_choice,
            system=system_choice,
            username=username,
            password=password,
        )
        click.secho("\nWeb UI service configuration complete.", fg="green", bold=True)
    except BSMError as e:
        click.secho(f"Error during Web UI service configuration: {e}", fg="red")
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")


@click.group("service")
def service():
    """
    Manages the Bedrock Server Manager Web UI application's service.

    This group of commands allows you to manage its integration as an OS-level system service for
    features like automatic startup.
    """
    pass


@service.command("configure")
@click.option(
    "--setup-service",
    is_flag=True,
    help="Create or update the system service file for the Web UI.",
)
@click.option(
    "--enable-autostart/--no-enable-autostart",
    "autostart_flag",
    default=None,
    show_default=False,
    help="Enable or disable Web UI service autostart.",
)
@click.option(
    "-s",
    "--system",
    "system_flag",
    is_flag=True,
    default=False,
    show_default=True,
    help="Configure as a system-wide service (Linux only, requires sudo).",
)
@click.option("--username", help="Username to run the Windows service as.")
@click.option("--password", help="Password for the user.")
@click.pass_context
def configure_web_service(
    ctx: click.Context,
    setup_service: bool,
    autostart_flag: Optional[bool],
    system_flag: bool,
    username: Optional[str],
    password: Optional[str],
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
    app_context: AppContext = ctx.obj["app_context"]
    if setup_service and not app_context.manager.can_manage_services:
        click.secho(
            "Error: --setup-service is not available (service manager not found).",
            fg="red",
        )
        raise click.Abort()

    try:
        if (
            app_context.manager.get_os_type() == "Windows"
            and username
            and not password
            and (setup_service or autostart_flag is not None)
        ):
            password = click.prompt("Password for the user", hide_input=True)

        # Determine if any flags were passed that would override interactive mode.
        any_flags_provided = (
            setup_service
            or autostart_flag is not None
            or system_flag
            or username is not None
            or password is not None
        )

        if not any_flags_provided:
            click.secho(
                "No flags provided; starting interactive Web UI service setup...",
                fg="yellow",
            )
            interactive_web_service_workflow(app_context)
            return

        click.secho("\nApplying Web UI service configuration...", bold=True)
        _perform_web_service_configuration(
            app_context=app_context,
            setup_service=setup_service,
            enable_autostart=autostart_flag,
            system=system_flag,
            username=username,
            password=password,
        )
        click.secho("\nWeb UI configuration applied successfully.", fg="green")
    except MissingArgumentError as e:
        click.secho(f"Configuration Error: {e}", fg="red")
    except BSMError as e:
        click.secho(f"Operation failed: {e}", fg="red")
    except (click.Abort, KeyboardInterrupt):
        click.secho("\nOperation cancelled.", fg="yellow")


@service.command("enable")
@click.option(
    "-s",
    "--system",
    "system_flag",
    is_flag=True,
    default=False,
    show_default=True,
    help="Enable a system-wide service (Linux only, requires sudo).",
)
@requires_web_service_manager
@click.pass_context
def enable_web_service_cli(ctx: click.Context, system_flag: bool):
    """
    Enables the Web UI system service for automatic startup.

    Configures the OS service for the Web UI (systemd on Linux, Windows Service
    on Windows) to start automatically when the system boots or user logs in.

    Requires a supported service manager (checked by decorator).

    Calls API: :func:`~bedrock_server_manager.api.web.enable_web_ui_service`.
    """
    app_context: AppContext = ctx.obj["app_context"]
    click.echo("Attempting to enable Web UI system service...")
    try:
        response = web_api.enable_web_ui_service(
            app_context=app_context, system=system_flag
        )
        _handle_api_response(response, "Web UI service enabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to enable Web UI service: {e}", fg="red")
        raise click.Abort()


@service.command("disable")
@click.option(
    "-s",
    "--system",
    "system_flag",
    is_flag=True,
    default=False,
    show_default=True,
    help="Disable a system-wide service (Linux only, requires sudo).",
)
@requires_web_service_manager
@click.pass_context
def disable_web_service_cli(ctx: click.Context, system_flag: bool):
    """
    Disables the Web UI system service from starting automatically.

    Configures the OS service for the Web UI to not start automatically.

    Requires a supported service manager (checked by decorator).

    Calls API: :func:`~bedrock_server_manager.api.web.disable_web_ui_service`.
    """
    app_context: AppContext = ctx.obj["app_context"]
    click.echo("Attempting to disable Web UI system service...")
    try:
        response = web_api.disable_web_ui_service(
            app_context=app_context, system=system_flag
        )
        _handle_api_response(response, "Web UI service disabled successfully.")
    except BSMError as e:
        click.secho(f"Failed to disable Web UI service: {e}", fg="red")
        raise click.Abort()


@service.command("remove")
@click.option(
    "-s",
    "--system",
    "system_flag",
    is_flag=True,
    default=False,
    show_default=True,
    help="Remove a system-wide service (Linux only, requires sudo).",
)
@requires_web_service_manager
@click.pass_context
def remove_web_service_cli(ctx: click.Context, system_flag: bool):
    """
    Removes the Web UI system service definition from the OS.

    .. danger::
        This is a destructive operation. The service definition will be
        deleted from the system.

    Prompts for confirmation before proceeding.
    Requires a supported service manager (checked by decorator).

    Calls API: :func:`~bedrock_server_manager.api.web.remove_web_ui_service`.
    """
    app_context: AppContext = ctx.obj["app_context"]
    if not questionary.confirm(
        "Are you sure you want to remove the Web UI system service?", default=False
    ).ask():
        click.secho("Removal cancelled.", fg="yellow")
        return
    click.echo("Attempting to remove Web UI system service...")
    try:
        response = web_api.remove_web_ui_service(
            app_context=app_context, system=system_flag
        )
        _handle_api_response(response, "Web UI service removed successfully.")
    except BSMError as e:
        click.secho(f"Failed to remove Web UI service: {e}", fg="red")
        raise click.Abort()


@service.command("status")
@click.option(
    "-s",
    "--system",
    "system_flag",
    is_flag=True,
    default=False,
    show_default=True,
    help="Check status of a system-wide service (Linux only, requires sudo).",
)
@requires_web_service_manager
@click.pass_context
def status_web_service_cli(ctx: click.Context, system_flag: bool):
    """
    Checks and displays the status of the Web UI system service.

    Reports whether the service definition exists, if it's currently
    active (running), and if it's enabled for autostart.

    Requires a supported service manager (checked by decorator).

    Calls API: :func:`~bedrock_server_manager.api.web.get_web_ui_service_status`.
    """
    app_context: AppContext = ctx.obj["app_context"]
    click.echo("Checking Web UI system service status...")
    try:
        response = web_api.get_web_ui_service_status(
            app_context=app_context, system=system_flag
        )
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


# --- Windows Service Support ---
import platform

if platform.system() == "Windows":
    import win32serviceutil
    import servicemanager
    from ..core.system.windows_class import (
        WebServerWindowsService,
        PYWIN32_AVAILABLE,
    )

    @service.command(
        "_run-web",
        hidden=True,
        context_settings=dict(
            ignore_unknown_options=True,
            allow_extra_args=True,
        ),
    )
    @click.argument("actual_svc_name_arg", type=str)
    @click.pass_context
    def _run_web_service_windows(ctx, actual_svc_name_arg: str):
        """
        (Internal use only) Clean entry point for the Windows SCM and for debugging the Web UI service.
        """
        if platform.system() != "Windows" or not PYWIN32_AVAILABLE:
            sys.exit(1)

        class WebServiceHandler(WebServerWindowsService):
            _svc_name_ = actual_svc_name_arg
            _svc_display_name_ = f"Bedrock Manager Web UI ({actual_svc_name_arg})"

        if "debug" in ctx.args:
            logger.info(
                f"Starting Web UI service '{actual_svc_name_arg}' in DEBUG mode."
            )

            win32serviceutil.DebugService(WebServiceHandler, argv=[actual_svc_name_arg])
        else:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(WebServiceHandler)
            servicemanager.StartServiceCtrlDispatcher()

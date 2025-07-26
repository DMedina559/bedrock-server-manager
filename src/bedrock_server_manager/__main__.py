# bedrock_server_manager/__main__.py
"""
Main entry point for the Bedrock Server Manager command-line interface.

This module is responsible for setting up the application environment (logging,
settings), assembling all `click` commands and groups, and launching the
main application logic. If no command is specified, it defaults to running
the interactive menu system.
"""

import logging
import platform
import sys

import click

# --- Early and Essential Imports ---
# This block handles critical import failures gracefully.
import atexit

try:
    from . import __version__
    from . import api
    from .config import app_name_title
    from .error import UserExitError
    from .logging import log_separator, setup_logging
    from .utils.general import startup_checks
    from .instances import (
        get_manager_instance,
        get_settings_instance,
        get_plugin_manager_instance,
    )

    global_api_plugin_manager = get_plugin_manager_instance()

    def shutdown_hooks():
        from .api.utils import stop_all_servers

        stop_all_servers()
        global_api_plugin_manager.unload_plugins()

    atexit.register(shutdown_hooks)
except ImportError as e:
    # Use basic logging as a fallback if our custom logger isn't available.
    logging.basicConfig(level=logging.CRITICAL)
    logger = logging.getLogger("bsm_critical_setup")
    logger.critical(f"A critical module could not be imported: {e}", exc_info=True)
    print(
        f"CRITICAL ERROR: A required module could not be found: {e}.\n"
        "Please ensure the package is installed correctly.",
        file=sys.stderr,
    )
    sys.exit(1)

# --- Import all Click command modules ---
# These are grouped logically for clarity.
from .cli import (
    cleanup,
    generate_password,
    web,
)


# --- Main Click Group Definition ---
@click.group(
    invoke_without_command=True,
    context_settings=dict(help_option_names=["-h", "--help"]),
)
@click.version_option(
    __version__, "-v", "--version", message=f"{app_name_title} %(version)s"
)
@click.pass_context
def cli(ctx: click.Context):
    """A comprehensive CLI for managing Minecraft Bedrock servers.

    This tool provides a full suite of commands to install, configure,
    manage, and monitor Bedrock dedicated server instances.

    If run without any arguments, it launches a user-friendly interactive
    menu to guide you through all available actions.
    """
    try:
        # --- Initial Application Setup ---
        log_dir = get_settings_instance().get("paths.logs")

        logger = setup_logging(
            log_dir=log_dir,
            log_keep=get_settings_instance().get("retention.logs"),
            file_log_level=get_settings_instance().get("logging.file_level"),
            cli_log_level=get_settings_instance().get("logging.cli_level"),
            force_reconfigure=True,
            plugin_dir=get_settings_instance().get("paths.plugins"),
        )
        log_separator(logger, app_name=app_name_title, app_version=__version__)
        logger.info(f"Starting {app_name_title} v{__version__} (CLI context)...")

        startup_checks(app_name_title, __version__)

        # api_utils.update_server_statuses() might trigger api.__init__ if not already done.
        # This ensures plugin_manager.load_plugins() has been called.
        global_api_plugin_manager.trigger_guarded_event("on_manager_startup")
        api.utils.update_server_statuses()

    except Exception as setup_e:
        logging.getLogger("bsm_critical_setup").critical(
            f"An unrecoverable error occurred during CLI application startup: {setup_e}",
            exc_info=True,
        )
        click.secho(f"CRITICAL STARTUP ERROR: {setup_e}", fg="red", bold=True)
        sys.exit(1)

    ctx.obj = {
        "cli": cli,
    }

    if ctx.invoked_subcommand is None:
        logger.info("No command specified.")
        sys.exit(1)


# --- Command Assembly ---
# A structured way to add all commands to the main `cli` group.
def _add_commands_to_cli():
    """Attaches all core command groups/standalone commands AND plugin commands to the main CLI group."""

    # Core Command Groups
    cli.add_command(web.web)

    if platform.system() == "Windows":
        from .cli import windows_service

        cli.add_command(windows_service.service)

    # Standalone Commands
    cli.add_command(cleanup.cleanup)
    cli.add_command(
        generate_password.generate_password_hash_command, name="generate-password"
    )


# Call the assembly function to build the CLI with core and plugin commands
_add_commands_to_cli()


def main():
    """Main execution function wrapped for final, fatal exception handling."""
    try:
        cli()
    except Exception as e:
        # This is a last-resort catch-all for unexpected errors not handled by Click.
        logger = logging.getLogger("bsm_critical_fatal")
        logger.critical("A fatal, unhandled error occurred.", exc_info=True)
        click.secho(
            f"\nFATAL UNHANDLED ERROR: {type(e).__name__}: {e}", fg="red", bold=True
        )
        click.secho("Please check the logs for more details.", fg="yellow")
        sys.exit(1)


if __name__ == "__main__":
    main()

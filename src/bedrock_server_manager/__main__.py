# bedrock_server_manager/__main__.py
"""
Main entry point for the Bedrock Server Manager command-line interface.

This module is responsible for setting up the application environment (logging,
settings), assembling all `click` commands and groups, and launching the
main application logic. If no command is specified, it defaults to running
the interactive menu system.
"""

import logging
import sys

import click

# --- Early and Essential Imports ---
# This block handles critical import failures gracefully.
try:
    from bedrock_server_manager import __version__
    from bedrock_server_manager.api import utils as api_utils
    from bedrock_server_manager.config.const import app_name_title
    from bedrock_server_manager.config.settings import Settings
    from bedrock_server_manager.core.manager import BedrockServerManager
    from bedrock_server_manager.error import UserExitError
    from bedrock_server_manager.logging import log_separator, setup_logging
    from bedrock_server_manager.utils.general import startup_checks
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
from bedrock_server_manager.cli import (
    addon,
    backup_restore,
    cleanup,
    generate_password,
    main_menus,
    player,
    server_actions,
    server_allowlist,
    server_permissions,
    server_properties,
    system,
    task_scheduler,
    utils,
    web,
    world,
    plugins,
    windows_service,
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
        # This block runs every time the CLI is invoked.
        settings = Settings()
        log_dir = settings.get("paths.logs")
        logger = setup_logging(
            log_dir=log_dir,
            log_keep=settings.get("retention.logs"),
            file_log_level=settings.get("logging.file_level"),
            cli_log_level=settings.get("logging.cli_level"),
        )
        log_separator(logger, app_name=app_name_title, app_version=__version__)

        logger.info(f"Starting {app_name_title} v{__version__}...")

        bsm = BedrockServerManager(settings_instance=settings)
        startup_checks(app_name_title, __version__)
        api_utils.update_server_statuses()

    except Exception as setup_e:
        # If setup fails, it's a critical error.
        click.secho(f"CRITICAL STARTUP ERROR: {setup_e}", fg="red", bold=True)
        logging.getLogger("bsm_critical_setup").critical(
            "An unrecoverable error occurred during application startup.", exc_info=True
        )
        sys.exit(1)

    # Pass the main `cli` group object to the context. This is crucial for
    # sub-menus to be able to find and invoke other commands.
    ctx.obj = {"cli": cli, "bsm": bsm, "settings": settings}

    # If no subcommand was invoked, run the main interactive menu.
    if ctx.invoked_subcommand is None:
        logger.info("No command specified; launching main interactive menu.")
        try:
            main_menus.main_menu(ctx)
        except UserExitError:
            # A clean, intentional exit from the main menu.
            sys.exit(0)
        except (click.Abort, KeyboardInterrupt):
            # The user pressed Ctrl+C or cancelled a top-level prompt.
            click.secho("\nOperation cancelled by user.", fg="red")
            sys.exit(1)


# --- Command Assembly ---
# A structured way to add all commands to the main `cli` group.
def _add_commands_to_cli():
    """Attaches all command groups and standalone commands to the main CLI group."""
    # Command Groups
    cli.add_command(backup_restore.backup)
    cli.add_command(player.player)
    cli.add_command(server_permissions.permissions)
    cli.add_command(server_properties.properties)
    cli.add_command(task_scheduler.schedule)
    cli.add_command(server_actions.server)
    cli.add_command(system.system)
    cli.add_command(web.web)
    cli.add_command(world.world)
    cli.add_command(server_allowlist.allowlist)
    cli.add_command(plugins.plugin)
    cli.add_command(windows_service.service)

    # Standalone Commands
    cli.add_command(addon.install_addon)
    cli.add_command(cleanup.cleanup)
    cli.add_command(
        generate_password.generate_password_hash_command, name="generate-password"
    )
    cli.add_command(utils.list_servers)


# Call the assembly function to build the CLI
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

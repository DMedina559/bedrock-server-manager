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
try:
    from . import __version__
    from .api import utils as api_utils
    from .config import app_name_title
    from .core import BedrockServerManager
    from .error import UserExitError
    from .logging import log_separator, setup_logging
    from .utils.general import startup_checks
    from .instances import get_manager_instance, get_settings_instance
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
)

# --- Import the shared PluginManager instance ---
# This instance is created in bedrock_server_manager/__init__.py
# and plugins are loaded by bedrock_server_manager/api/__init__.py when it's imported.
# So, by the time __main__ fully runs, plugins should be loaded if api module was imported.
# One of the CLI modules (e.g. cli.plugins) or api.utils might import api.__init__ early.
try:
    from . import plugin_manager as global_api_plugin_manager
except ImportError as e_imp_pm:
    # Fallback or error logging if bedrock_server_manager.api.plugin_manager cannot be imported
    # This might happen if `api.__init__` itself has an issue or isn't processed yet.
    # Using print for very early messages as logger might not be set up.
    print(
        f"WARNING [BSM __main__]: Could not import global_api_plugin_manager from bedrock_server_manager.api: {e_imp_pm}. Plugin CLI extensions might be unavailable.",
        file=sys.stderr,
    )
    global_api_plugin_manager = None


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
        )
        log_separator(logger, app_name=app_name_title, app_version=__version__)
        logger.info(f"Starting {app_name_title} v{__version__} (CLI context)...")

        bsm = get_manager_instance()
        startup_checks(app_name_title, __version__)

        # api_utils.update_server_statuses() might trigger api.__init__ if not already done.
        # This ensures plugin_manager.load_plugins() has been called.
        api_utils.update_server_statuses()

    except Exception as setup_e:
        logging.getLogger("bsm_critical_setup").critical(
            f"An unrecoverable error occurred during CLI application startup: {setup_e}",
            exc_info=True,
        )
        click.secho(f"CRITICAL STARTUP ERROR: {setup_e}", fg="red", bold=True)
        sys.exit(1)

    ctx.obj = {
        "cli": cli,
        "bsm": bsm,
        "settings": get_settings_instance(),
        "plugin_manager": global_api_plugin_manager,
    }

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


# --- Helper function to add plugin CLI commands ---
def _add_plugin_cli_commands(main_cli_group: click.Group, pm_instance):
    """Adds CLI commands from plugins to the main CLI group."""
    if pm_instance and hasattr(pm_instance, "plugin_cli_commands"):
        plugin_commands = pm_instance.plugin_cli_commands
        if plugin_commands:
            # Using print as this runs very early, before logger might be fully set up by CLI.
            print(
                f"[BSM __main__] Adding {len(plugin_commands)} CLI command(s) from plugins to group '{main_cli_group.name}'."
            )
            for cmd_idx, cmd in enumerate(plugin_commands):
                if isinstance(cmd, (click.Command, click.Group)):
                    main_cli_group.add_command(cmd)
                    cmd_name = getattr(cmd, "name", f"unknown_cmd_idx_{cmd_idx}")
                    print(f"[BSM __main__] Added plugin CLI command/group: {cmd_name}")
                else:
                    print(
                        f"[BSM __main__] WARNING: Plugin provided an object that is not a valid Click command/group at index {cmd_idx}: {type(cmd)}"
                    )
        # No explicit message if plugin_commands is empty, as PluginManager logs collection.
    elif pm_instance:
        print(
            "[BSM __main__] WARNING: Imported plugin_manager has no 'plugin_cli_commands' attribute.",
            file=sys.stderr,
        )
    else:
        # This case is logged by the import try-except block for global_api_plugin_manager
        print(
            "[BSM __main__] INFO: global_api_plugin_manager is None. Cannot add plugin CLI commands.",
            file=sys.stderr,
        )


# --- Command Assembly ---
# A structured way to add all commands to the main `cli` group.
def _add_commands_to_cli():
    """Attaches all core command groups/standalone commands AND plugin commands to the main CLI group."""
    # `cli` is the globally defined Click group.
    # `global_api_plugin_manager` is the plugin_manager from bedrock_server_manager.api

    # Core Command Groups
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

    if platform.system() == "Windows":
        from .cli import windows_service

        cli.add_command(windows_service.service)

    # Standalone Commands
    cli.add_command(addon.install_addon)
    cli.add_command(cleanup.cleanup)
    cli.add_command(
        generate_password.generate_password_hash_command, name="generate-password"
    )
    cli.add_command(utils.list_servers)

    # After adding all core commands, add plugin commands using the global plugin manager instance
    if (
        global_api_plugin_manager
    ):  # Check if it was successfully imported and initialized
        _add_plugin_cli_commands(cli, global_api_plugin_manager)
    # If global_api_plugin_manager is None, warnings/errors already printed during its import attempt


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

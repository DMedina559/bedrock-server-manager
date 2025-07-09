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

# --- Global Settings and PluginManager Initialization ---
# These are initialized when the module is first imported/run.
settings_instance = Settings()
plugin_manager_instance = None
try:
    from bedrock_server_manager.plugins.plugin_manager import PluginManager
    # PluginManager uses the global `settings` object from config.settings,
    # which is initialized when PluginManager imports it.
    # So, settings_instance here is primarily for BedrockServerManager later.
    plugin_manager_instance = PluginManager()
    plugin_manager_instance.load_plugins()
    # Using print here as logger might not be configured yet.
    print(f"[BSM __main__] PluginManager initialized and plugins loaded. Found {len(plugin_manager_instance.plugin_cli_commands)} CLI commands, {len(plugin_manager_instance.plugin_fastapi_routers)} FastAPI routers.")
except ImportError:
    print("CRITICAL [BSM __main__]: Could not import PluginManager. Plugin functionality will be disabled.", file=sys.stderr)
except Exception as e_pm:
    print(f"CRITICAL [BSM __main__]: Error initializing PluginManager or loading plugins: {e_pm}. Plugin functionality may be disabled.", file=sys.stderr)
    # Optionally, re-raise or sys.exit if plugins are critical for CLI startup

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
    # Access the global instances.
    global settings_instance, plugin_manager_instance
    
    try:
        # --- Initial Application Setup ---
        # Settings instance is already created globally.
        log_dir = settings_instance.get("paths.logs")

        logger = setup_logging(
            log_dir=log_dir,
            log_keep=settings_instance.get("retention.logs"),
            file_log_level=settings_instance.get("logging.file_level"),
            cli_log_level=settings_instance.get("logging.cli_level"),
            force_reconfigure=True,
        )
        log_separator(logger, app_name=app_name_title, app_version=__version__)

        logger.info(f"Starting {app_name_title} v{__version__}...")

        # Pass the global settings_instance to BedrockServerManager
        bsm = BedrockServerManager(settings_instance=settings_instance)
        startup_checks(app_name_title, __version__)
        api_utils.update_server_statuses()

    except Exception as setup_e:
        # If setup fails, it's a critical error.
        click.secho(f"CRITICAL STARTUP ERROR: {setup_e}", fg="red", bold=True)
        # Attempt to use logger if available, otherwise basicConfig would have been called.
        logging.getLogger("bsm_critical_setup").critical(
            "An unrecoverable error occurred during application startup.", exc_info=True
        )
        sys.exit(1)

    # Pass instances to the context.
    # `cli` here refers to this function (the main Click group).
    ctx.obj = {
        "cli_group": cli, 
        "bsm": bsm, 
        "settings": settings_instance,
        "plugin_manager": plugin_manager_instance # Add the plugin manager
    }

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


# --- Helper function to add plugin CLI commands ---
def _add_plugin_cli_commands(main_cli_group: click.Group, pm_instance):
    """Adds CLI commands from plugins to the main CLI group."""
    if pm_instance and hasattr(pm_instance, 'plugin_cli_commands'):
        plugin_commands = pm_instance.plugin_cli_commands
        if plugin_commands:
            # Using print as logger might not be fully configured when this runs.
            print(f"[BSM __main__] Attempting to add {len(plugin_commands)} CLI command(s) from plugins to group '{main_cli_group.name}'.")
            for cmd in plugin_commands:
                if isinstance(cmd, (click.Command, click.Group)):
                    main_cli_group.add_command(cmd)
                    print(f"[BSM __main__] Added plugin CLI command/group: {cmd.name}")
                else:
                    print(f"[BSM __main__] WARNING: Plugin provided an invalid CLI command object: {cmd}")
        else:
            print("[BSM __main__] No plugin CLI commands to add.")
    elif pm_instance:
        print("[BSM __main__] Plugin manager instance has no 'plugin_cli_commands' attribute.")
    else:
        print("[BSM __main__] Plugin manager instance is None, cannot add plugin CLI commands.")

# --- Command Assembly ---
# A structured way to add all commands to the main `cli` group.
def _add_commands_to_cli():
    """Attaches all core command groups and standalone commands to the main CLI group."""
    # Access the global `cli` group and `plugin_manager_instance`
    global cli, plugin_manager_instance

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
    cli.add_command(windows_service.service)

    # Standalone Commands
    cli.add_command(addon.install_addon)
    cli.add_command(cleanup.cleanup)
    cli.add_command(
        generate_password.generate_password_hash_command, name="generate-password"
    )
    cli.add_command(utils.list_servers)

    # After adding all core commands, add plugin commands
    _add_plugin_cli_commands(cli, plugin_manager_instance)


# Call the assembly function to build the CLI
# This now also handles adding plugin commands internally if plugin_manager_instance is valid
_add_commands_to_cli()


def main():
    """Main execution function wrapped for final, fatal exception handling."""
    # `settings_instance` and `plugin_manager_instance` are already initialized globally.
    # `_add_commands_to_cli` (which now includes plugin commands) has also been called.
    # The `cli` object (the main Click group) is fully populated with core and plugin commands.
    try:
        # Simply call the main cli group.
        # The `cli` function itself will handle creating BSM and populating ctx.obj
        # with the global settings_instance and plugin_manager_instance.
        cli()
    except Exception as e:
        # This is a last-resort catch-all for unexpected errors not handled by Click.
        # Try to get a logger; if main CLI setup failed, this might be basic.
        logger = logging.getLogger("bsm_critical_fatal")
        logger.critical("A fatal, unhandled error occurred.", exc_info=True)
        click.secho(
            f"\nFATAL UNHANDLED ERROR: {type(e).__name__}: {e}", fg="red", bold=True
        )
        click.secho("Please check the logs for more details.", fg="yellow")
        sys.exit(1)


if __name__ == "__main__":
    main()

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
import atexit
import click

try:
    from . import __version__
    from .config import app_name_title
    from .logging import log_separator, setup_logging
    from .utils.general import startup_checks
    from .context import AppContext
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
    setup,
    service,
    migrate,
    reset_password,
    database,
)


def create_cli_app():
    """Creates and configures the CLI application."""

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
            app_context = AppContext()

            # --- Event Handling and Shutdown ---
            def shutdown_cli_app(app_context: AppContext):
                """A cleanup function to be run on exit."""
                # Use a generic logger, as the full logger may not be configured
                # for all commands (e.g., setup, migrate).
                shutdown_logger = logging.getLogger("bsm_shutdown")
                shutdown_logger.info("Running CLI app shutdown hooks...")
                app_context.db.close()
                shutdown_logger.info("CLI app shutdown hooks complete.")

            atexit.register(shutdown_cli_app, app_context)

            # Load the full application context only if the command is not 'setup' or 'migrate'
            if ctx.invoked_subcommand in ["setup", "migrate"]:
                logging.basicConfig(level=logging.INFO)
                logger = logging.getLogger("bsm_setup")

            if ctx.invoked_subcommand not in ["setup", "migrate"]:
                app_context.load()

                log_dir = app_context.settings.get("paths.logs")
                logger = setup_logging(
                    log_dir=log_dir,
                    log_keep=app_context.settings.get("retention.logs"),
                    file_log_level=app_context.settings.get("logging.file_level"),
                    cli_log_level=app_context.settings.get("logging.cli_level"),
                    force_reconfigure=True,
                    plugin_dir=app_context.settings.get("paths.plugins"),
                )
                log_separator(logger, app_name=app_name_title, app_version=__version__)
                logger.info(
                    f"Starting {app_name_title} v{__version__} (CLI context)..."
                )

                startup_checks(app_context, app_name_title, __version__)

        except Exception as setup_e:
            logging.getLogger("bsm_critical_setup").critical(
                f"An unrecoverable error occurred during CLI application startup: {setup_e}",
                exc_info=True,
            )
            click.secho(f"CRITICAL STARTUP ERROR: {setup_e}", fg="red", bold=True)
            sys.exit(1)

        ctx.obj = {"cli": cli, "app_context": app_context}

        if ctx.invoked_subcommand is None:
            logger.info("No command specified.")
            sys.exit(1)

    # --- Command Assembly ---
    # A structured way to add all commands to the main `cli` group.
    def _add_commands_to_cli():
        """Attaches all core command groups/standalone commands AND plugin commands to the main CLI group."""

        cli.add_command(web.web)
        cli.add_command(cleanup.cleanup)
        cli.add_command(setup.setup)
        cli.add_command(
            generate_password.generate_password_hash_command, name="generate-password"
        )
        cli.add_command(reset_password.reset_password_command)
        cli.add_command(service.service)
        cli.add_command(migrate.migrate)
        cli.add_command(database.database)

    # Call the assembly function to build the CLI with core and plugin commands
    _add_commands_to_cli()

    return cli


def main():
    """Main execution function wrapped for final, fatal exception handling."""
    try:
        cli = create_cli_app()
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

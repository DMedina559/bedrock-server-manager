# bedrock_server_manager/__main__.py
"""
Main entry point for the Bedrock Server Manager command-line interface.

This module is responsible for setting up the application environment (logging,
settings), assembling all `click` commands and groups, and launching the
main application logic. If no command is specified, it defaults to running
the interactive menu system.
"""

import atexit
import logging
import sys

import click

from . import __version__
from .cli import (
    cleanup,
    database,
    reset_password,
    service,
    setup,
    web,
)
from .config import app_name_title
from .context import AppContext
from .logging import log_separator, setup_logging
from .utils.general import startup_checks


def create_cli_app():
    """Creates and configures the CLI application."""

    @click.group(
        invoke_without_command=True,
        context_settings=dict(help_option_names=["-h", "--help"]),
    )
    @click.option(
        "--config-dir",
        type=click.Path(file_okay=False, dir_okay=True, resolve_path=True),
        help="Override the configuration directory.",
    )
    @click.option(
        "--data-dir",
        type=click.Path(file_okay=False, dir_okay=True, resolve_path=True),
        help="Override the application data directory.",
    )
    @click.option(
        "--db-url",
        type=str,
        help="Override the database URL connection string.",
    )
    @click.option(
        "--log-level",
        type=click.Choice(
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
        ),
        help="Set the logging level.",
    )
    @click.version_option(
        __version__, "-v", "--version", message=f"{app_name_title} %(version)s"
    )
    @click.pass_context
    def cli(
        ctx: click.Context,
        config_dir: str | None,
        data_dir: str | None,
        db_url: str | None,
        log_level: str | None,
    ):
        """A comprehensive CLI for managing Minecraft Bedrock servers.

        This tool provides a full suite of commands to install, configure,
        manage, and monitor Bedrock dedicated server instances.

        If run without any arguments, it launches a user-friendly interactive
        menu to guide you through all available actions.
        """
        from .config import bcm_config

        # --- Configuration Overrides ---
        bcm_config.set_custom_config_dir(config_dir)
        bcm_config.set_custom_data_dir(data_dir)
        bcm_config.set_custom_db_url(db_url)
        bcm_config.set_custom_log_level(log_level)

        try:
            logger = setup_logging(force_reconfigure=True)
            log_separator(logger, app_name=app_name_title, app_version=__version__)
            logger.info(f"Starting {app_name_title} v{__version__} (CLI context)...")
        except Exception as log_setup_e:
            # If logging setup fails, we still want to inform the user.
            print(
                f"CRITICAL ERROR: Failed to set up logging: {log_setup_e}",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            # --- Initial Application Setup ---
            app_context = AppContext(
                config_dir=config_dir,
                data_dir=data_dir,
                db_url=db_url,
                log_level=log_level,
                logger=logger,
            )

            # --- Event Handling and Shutdown ---
            def shutdown_cli_app(app_context: AppContext):
                """A cleanup function to be run on exit."""

                logger.info("Running CLI app shutdown hooks...")
                app_context.db.close()
                logger.info("CLI app shutdown hooks complete.")

            atexit.register(shutdown_cli_app, app_context)

            if ctx.invoked_subcommand not in ["setup", "migrate"]:
                app_context.load()
                startup_checks(app_context)

        except Exception as setup_e:
            logger.critical(
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
        cli.add_command(reset_password.reset_password_command)
        cli.add_command(service.service)
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

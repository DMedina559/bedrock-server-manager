"""
Provides application factory functions for creating and configuring the CLI and web apps.
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
    from .config import app_name_title
    from .db import database
    from .error import UserExitError
    from .logging import log_separator, setup_logging
    from .utils.general import startup_checks
    from .config.settings import Settings
    from .core.manager import BedrockServerManager
    from .context import AppContext
    from .plugins import PluginManager
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
)

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pathlib import Path
import os
from .web import templating
from .config import get_installed_version
from .web import routers
from .web.dependencies import needs_setup
from starlette.middleware.authentication import AuthenticationMiddleware
from .web.auth_utils import CustomAuthBackend, get_current_user_optional


def create_web_app(settings: Settings) -> FastAPI:
    """Creates and configures the web application."""
    logger = logging.getLogger(__name__)
    from .web import main as web_main
    from . import api

    # --- Application Context Setup ---
    plugin_manager = PluginManager(settings)

    # Define shutdown hooks here to capture the plugin_manager instance
    def shutdown_web_app():
        logger.info("Running web app shutdown hooks...")
        api.utils.stop_all_servers(app_context=app_context)
        app_context.plugin_manager.unload_plugins()
        if database.engine:
            database.engine.dispose()
        logger.info("Web app shutdown hooks complete.")

    atexit.register(shutdown_web_app)

    APP_ROOT = os.path.dirname(os.path.abspath(web_main.__file__))
    TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")
    STATIC_DIR = os.path.join(APP_ROOT, "static")
    version = get_installed_version()

    # --- Template Directories Setup ---
    all_template_dirs = [Path(TEMPLATES_DIR)]
    if plugin_manager.plugin_template_paths:
        logger.info(
            f"Adding {len(plugin_manager.plugin_template_paths)} template paths from plugins."
        )
        unique_plugin_paths = {
            p for p in plugin_manager.plugin_template_paths if isinstance(p, Path)
        }
        all_template_dirs.extend(list(unique_plugin_paths))
    logger.info(f"Configuring Jinja2 with directories: {all_template_dirs}")
    templating.configure_templates(all_template_dirs, settings)

    # --- FastAPI App Initialization ---
    app = FastAPI(
        title="Bedrock Server Manager",
        version=version,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "filter": True,
            "deepLinking": True,
        },
    )
    manager = BedrockServerManager(settings)
    app_context = AppContext(settings=settings, manager=manager)
    app.state.app_context = app_context

    app_context.plugin_manager.load_plugins()

    app_context.plugin_manager.trigger_guarded_event("on_manager_startup")

    api.utils.update_server_statuses(app_context=app_context)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    # Mount custom themes directory
    themes_path = settings.get("paths.themes")
    if os.path.isdir(themes_path):
        app.mount("/themes", StaticFiles(directory=themes_path), name="themes")

    @app.middleware("http")
    async def setup_check_middleware(request: Request, call_next):
        if (
            await needs_setup()
            and not request.url.path.startswith("/setup")
            and not request.url.path.startswith("/static")
        ):
            return RedirectResponse(url="/setup")

        # Manually handle authentication to bypass it for static files
        if not request.url.path.startswith("/static"):
            auth_backend = CustomAuthBackend()
            auth_result = await auth_backend.authenticate(request)
            if auth_result:
                creds, user = auth_result
                request.state.user = user
            else:
                request.state.user = None

        response = await call_next(request)
        return response

    @app.middleware("http")
    async def add_user_to_request(request: Request, call_next):
        user = await get_current_user_optional(request)
        request.state.current_user = user
        response = await call_next(request)
        return response

    app.include_router(routers.setup_router)
    app.include_router(routers.auth_router)
    app.include_router(routers.users_router)
    app.include_router(routers.register_router)
    app.include_router(routers.server_actions_router)
    app.include_router(routers.server_install_config_router)
    app.include_router(routers.backup_restore_router)
    app.include_router(routers.content_router)
    app.include_router(routers.settings_router)
    app.include_router(routers.api_info_router)
    app.include_router(routers.plugin_router)
    app.include_router(routers.tasks_router)
    app.include_router(routers.main_router)
    app.include_router(routers.account_router)
    app.include_router(routers.audit_log_router)

    # --- Dynamically include FastAPI routers from plugins ---
    if plugin_manager.plugin_fastapi_routers:
        logger.info(
            f"Found {len(plugin_manager.plugin_fastapi_routers)} FastAPI router(s) from plugins. Attempting to include them."
        )
        for i, router in enumerate(plugin_manager.plugin_fastapi_routers):
            try:
                if hasattr(router, "routes"):
                    app.include_router(router)
                    logger.info(
                        f"Successfully included FastAPI router (prefix: '{router.prefix}') from a plugin."
                    )
                else:
                    logger.warning(
                        f"Plugin provided an object at index {i} that is not a valid FastAPI APIRouter."
                    )
            except Exception as e:
                logger.error(
                    f"Failed to include a FastAPI router from a plugin: {e}",
                    exc_info=True,
                )
    else:
        logger.info("No additional FastAPI routers found from plugins.")

    # --- Dynamically mount static directories from plugins ---
    if plugin_manager.plugin_static_mounts:
        logger.info(
            f"Found {len(plugin_manager.plugin_static_mounts)} static mount configurations from plugins."
        )
        for mount_path, dir_path, name in plugin_manager.plugin_static_mounts:
            try:
                app.mount(mount_path, StaticFiles(directory=dir_path), name=name)
                logger.info(
                    f"Mounted static directory '{dir_path}' at '{mount_path}' (name: '{name}')."
                )
            except Exception as e:
                logger.error(
                    f"Failed to mount static directory '{dir_path}' at '{mount_path}': {e}",
                    exc_info=True,
                )

    app.include_router(routers.util_router)

    return app


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
            settings = Settings()
            manager = BedrockServerManager(settings)

            app_context = AppContext(settings=settings, manager=manager)
            from .instances import set_app_context

            set_app_context(app_context)

            log_dir = settings.get("paths.logs")

            logger = setup_logging(
                log_dir=log_dir,
                log_keep=settings.get("retention.logs"),
                file_log_level=settings.get("logging.file_level"),
                cli_log_level=settings.get("logging.cli_level"),
                force_reconfigure=True,
                plugin_dir=settings.get("paths.plugins"),
            )
            log_separator(logger, app_name=app_name_title, app_version=__version__)
            logger.info(f"Starting {app_name_title} v{__version__} (CLI context)...")

            startup_checks(app_name_title, __version__)

            # --- Event Handling and Shutdown ---
            def shutdown_cli_app():
                logger.info("Running CLI app shutdown hooks...")
                if database.engine:
                    database.engine.dispose()
                logger.info("CLI app shutdown hooks complete.")

            atexit.register(shutdown_cli_app)

        except Exception as setup_e:
            logging.getLogger("bsm_critical_setup").critical(
                f"An unrecoverable error occurred during CLI application startup: {setup_e}",
                exc_info=True,
            )
            click.secho(f"CRITICAL STARTUP ERROR: {setup_e}", fg="red", bold=True)
            sys.exit(1)

        ctx.obj = {"cli": cli, "bsm": manager, "app_context": app_context}

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
        cli.add_command(service.service)
        cli.add_command(migrate.migrate)

    # Call the assembly function to build the CLI with core and plugin commands
    _add_commands_to_cli()

    return cli

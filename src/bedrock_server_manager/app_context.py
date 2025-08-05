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
    from .instances import (
        get_plugin_manager_instance,
    )

    global_api_plugin_manager = get_plugin_manager_instance()

    def shutdown_hooks():
        from .api.utils import stop_all_servers

        stop_all_servers()
        global_api_plugin_manager.unload_plugins()
        if database.engine:
            database.engine.dispose()

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
from .instances import get_plugin_manager_instance
from .web import routers
from .web.dependencies import needs_setup
from starlette.middleware.authentication import AuthenticationMiddleware
from .web.auth_utils import CustomAuthBackend, get_current_user_optional


def create_web_app(settings):
    """Creates and configures the web application."""
    import logging
    from .web import main as web_main

    APP_ROOT = os.path.dirname(os.path.abspath(web_main.__file__))
    TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")  # This is a string path
    STATIC_DIR = os.path.join(APP_ROOT, "static")
    version = get_installed_version()

    # --- Setup Template Directories ---
    # Start with the main application's template directory
    all_template_dirs = [Path(TEMPLATES_DIR)]

    web_main_templating_logger = logging.getLogger("bsm_web_main_templating_setup")

    global_api_plugin_manager = get_plugin_manager_instance()

    if global_api_plugin_manager and hasattr(
        global_api_plugin_manager, "plugin_template_paths"
    ):
        if global_api_plugin_manager.plugin_template_paths:
            web_main_templating_logger.info(
                f"Adding {len(global_api_plugin_manager.plugin_template_paths)} template paths from plugins."
            )
            # Ensure paths are unique and are Path objects
            unique_plugin_paths = {
                p
                for p in global_api_plugin_manager.plugin_template_paths
                if isinstance(p, Path)
            }
            all_template_dirs.extend(list(unique_plugin_paths))
        else:
            web_main_templating_logger.info(
                "No additional template paths found from plugins."
            )
    else:
        web_main_templating_logger.warning(
            "global_api_plugin_manager or its plugin_template_paths attribute is unavailable. "
            "Only main app templates will be loaded."
        )

    web_main_templating_logger.info(
        f"Configuring Jinja2 environment with directories: {all_template_dirs}"
    )
    templating.configure_templates(all_template_dirs)

    app = FastAPI(
        title="Bedrock Server Manager",
        version=version,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,  # Hide models section by default
            "filter": True,  # Enable filtering for operations
            "deepLinking": True,  # Enable deep linking for tags and operations
        },
    )

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

    import logging  # Use standard logging

    web_main_plugin_logger = logging.getLogger(
        "bsm_web_main_plugin_loader"
    )  # Specific logger

    if (
        global_api_plugin_manager
        and hasattr(global_api_plugin_manager, "plugin_fastapi_routers")
        and global_api_plugin_manager.plugin_fastapi_routers
    ):
        web_main_plugin_logger.info(
            f"Found {len(global_api_plugin_manager.plugin_fastapi_routers)} FastAPI router(s) "
            "from plugins via bedrock_server_manager.api.plugin_manager. Attempting to include them."
        )
        for router_idx, router_obj in enumerate(
            global_api_plugin_manager.plugin_fastapi_routers
        ):
            try:
                # Basic check if it's an APIRouter (can be made more robust)
                if hasattr(router_obj, "routes") and callable(
                    getattr(router_obj, "include_router", None)
                ):  # Heuristic check
                    app.include_router(router_obj)
                    router_prefix = getattr(
                        router_obj, "prefix", f"N/A_idx_{router_idx}"
                    )
                    web_main_plugin_logger.info(
                        f"Successfully included FastAPI router with prefix '{router_prefix}' from a plugin."
                    )
                else:
                    web_main_plugin_logger.warning(
                        f"Plugin provided an object that does not appear to be a valid FastAPI APIRouter at index {router_idx}. Object type: {type(router_obj)}"
                    )
            except Exception as e_router:
                web_main_plugin_logger.error(
                    f"Failed to include a FastAPI router (index {router_idx}) from a plugin: {e_router}",
                    exc_info=True,
                )
    elif global_api_plugin_manager:
        web_main_plugin_logger.info(
            "No additional FastAPI routers found from plugins via bedrock_server_manager.api.plugin_manager."
        )
    else:
        # This case implies global_api_plugin_manager import failed or it's None.
        web_main_plugin_logger.error(
            "global_api_plugin_manager is None or unavailable. Cannot include FastAPI routers from plugins. "
            "Check logs for import errors related to 'bedrock_server_manager.api.plugin_manager'."
        )

    # --- Dynamically mount static directories from plugins ---
    if (
        global_api_plugin_manager
        and hasattr(global_api_plugin_manager, "plugin_static_mounts")
        and global_api_plugin_manager.plugin_static_mounts
    ):
        web_main_plugin_logger.info(
            f"Found {len(global_api_plugin_manager.plugin_static_mounts)} static mount configurations "
            "from plugins. Attempting to mount them."
        )
        for (
            mount_path,
            dir_path,
            name,
        ) in global_api_plugin_manager.plugin_static_mounts:
            try:
                app.mount(mount_path, StaticFiles(directory=dir_path), name=name)
                web_main_plugin_logger.info(
                    f"Successfully mounted static directory '{dir_path}' at '{mount_path}' with name '{name}' from a plugin."
                )
            except Exception as e_static_mount:
                web_main_plugin_logger.error(
                    f"Failed to mount static directory '{dir_path}' at '{mount_path}' (name: '{name}') from a plugin: {e_static_mount}",
                    exc_info=True,
                )
    elif global_api_plugin_manager:
        web_main_plugin_logger.info("No additional static mounts found from plugins.")
    # No else here, as the error for global_api_plugin_manager being unavailable is already logged above.

    app.include_router(routers.util_router)

    return app


import functools


def with_app_context(func):
    """
    A decorator that creates an application context and passes it to the decorated function.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        settings = Settings()
        with BedrockServerManager(settings) as manager:
            return func(manager, *args, **kwargs)

    return wrapper


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

            # --- LOAD PLUGINS AND FIRE STARTUP EVENT ---
            from . import api

            plugin_manager = get_plugin_manager_instance()

            # Now that all APIs are registered, we can safely load the plugins.
            plugin_manager.load_plugins()

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
            "bsm": manager,
        }

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

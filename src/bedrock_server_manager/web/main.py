# bedrock_server_manager/web/main.py
"""
Provides the main function for configuring and running the Uvicorn web server.

This module contains the :func:`run_web_server` function, which is responsible
for initializing and starting the Uvicorn server that serves the FastAPI application.
The FastAPI application instance (`app`) itself is expected to be defined in
:mod:`bedrock_server_manager.web.main`. This module handles parsing command-line
arguments and application settings to correctly configure Uvicorn's host, port,
debug mode, and worker processes.
"""

import ipaddress
import logging
from typing import Optional

import uvicorn

from ..context import AppContext
from .app import create_web_app

logger = logging.getLogger(__name__)


def run_web_server(  # noqa: C901
    app_context: "AppContext",
    host: Optional[str] = None,
    port: Optional[int] = None,
    debug: bool = False,
) -> None:
    """
    Configures and starts the Uvicorn web server to serve the FastAPI application.
    """
    settings = app_context.settings

    # Determine port to use
    final_port = 11325  # Default fallback
    if port is not None:
        logger.info(f"Using port provided via command-line: {port}")
        final_port = port
    else:
        logger.info("No port via command-line, using settings.")
        port_setting_key = "web.port"
        port_val = settings.get(port_setting_key, 11325)
        try:
            settings_port = int(port_val)
            if not (0 < settings_port < 65536):
                raise ValueError("Port out of range")
            final_port = settings_port
        except (ValueError, TypeError):
            logger.error(
                f"Invalid port number configured: {port_val}. Using default {final_port}."
            )
    logger.info(f"FastAPI server configured to run on port: {final_port}")

    hosts_to_use_cli: Optional[str] = None
    if host:
        logger.info(f"Using host(s) provided via command-line: {host}")
        if not isinstance(host, str):
            raise ValueError("Host must be a string, representing an IP or hostname.")
        hosts_to_use_cli = host

    final_host_to_bind = "127.0.0.1"

    if hosts_to_use_cli:
        final_host_to_bind = hosts_to_use_cli
        logger.info(f"Host from command-line: {final_host_to_bind}")
    else:
        # Fallback to settings if no command-line host is given.
        logger.info("No host via command-line, using settings.")
        settings_host = settings.get("web.host")

        if isinstance(settings_host, str) and settings_host:
            # Use the host from settings if it's a valid string.
            final_host_to_bind = settings_host
        else:
            # Log a warning if the setting is invalid and use the default.
            logger.warning(
                f"Host setting 'web.host' is invalid ('{settings_host}'). "
                f"Defaulting to {final_host_to_bind}."
            )

    try:
        ipaddress.ip_address(final_host_to_bind)
        logger.info(f"Uvicorn will bind to IP: {final_host_to_bind}")
    except ValueError:
        logger.info(f"Uvicorn will bind to hostname: {final_host_to_bind}")

    uvicorn_log_level = "info"
    reload_enabled = False

    if debug:
        logger.warning("Running FastAPI in DEBUG mode (Uvicorn reload enabled).")
        uvicorn_log_level = "debug"
        reload_enabled = True
    else:
        logger.info("Uvicorn production mode with 1 worker.")

    server_mode = (
        "DEBUG (Uvicorn with reload)" if reload_enabled else "PRODUCTION (Uvicorn)"
    )
    logger.info(f"Starting FastAPI web server in {server_mode} mode...")
    logger.info(f"Listening on: http://{final_host_to_bind}:{final_port}")

    try:
        from uvicorn.config import LOGGING_CONFIG

        # To prevent uvicorn from taking over the logger, we need to disable it.
        # More info: https://github.com/encode/uvicorn/issues/1285
        LOGGING_CONFIG["loggers"]["uvicorn"]["propagate"] = True

        # Create the FastAPI app
        app = create_web_app(app_context)

        config = uvicorn.Config(
            app,
            host=final_host_to_bind,
            port=final_port,
            log_config=LOGGING_CONFIG,
            log_level=uvicorn_log_level.lower(),  # Ensure log level is lowercase
            reload=reload_enabled,
            workers=1,  # workers if not reload_enabled and workers > 1 else None,
            forwarded_allow_ips="*",
            proxy_headers=True,
            timeout_graceful_shutdown=5,
        )
        server = uvicorn.Server(config)
        app_context._web_server = server
        server.run()
    except Exception as e:
        logger.critical(f"Failed to start Uvicorn: {e}", exc_info=True)

        raise

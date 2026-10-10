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
from ..logging import configure_web_logging
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
        logger.debug("Using port provided via command-line: %s", port)
        final_port = port
    else:
        logger.debug("No port via command-line, using settings.")
        port_setting_key = "web.port"
        port_val = settings.get(port_setting_key, 11325)
        try:
            settings_port = int(port_val)
            if not (0 < settings_port < 65536):
                raise ValueError("Port out of range")
            final_port = settings_port
        except (ValueError, TypeError):
            logger.warning("Invalid web port %r; using port %s.", port_val, final_port)
    logger.debug("FastAPI server configured to run on port: %s", final_port)

    hosts_to_use_cli: Optional[str] = None
    if host:
        logger.debug("Using host(s) provided via command-line: %s", host)
        if not isinstance(host, str):
            raise ValueError("Host must be a string, representing an IP or hostname.")
        hosts_to_use_cli = host

    final_host_to_bind = "127.0.0.1"

    if hosts_to_use_cli:
        final_host_to_bind = hosts_to_use_cli
        logger.debug("Host from command-line: %s", final_host_to_bind)
    else:
        # Fallback to settings if no command-line host is given.
        logger.debug("No host via command-line, using settings.")
        settings_host = settings.get("web.host")

        if isinstance(settings_host, str) and settings_host:
            # Use the host from settings if it's a valid string.
            final_host_to_bind = settings_host
        else:
            # Log a warning if the setting is invalid and use the default.
            logger.warning(
                "Host setting 'web.host' is invalid ('%s'). Defaulting to %s.",
                settings_host,
                final_host_to_bind,
            )

    try:
        ipaddress.ip_address(final_host_to_bind)
        logger.debug("Uvicorn will bind to IP: %s", final_host_to_bind)
    except ValueError:
        logger.debug("Uvicorn will bind to hostname: %s", final_host_to_bind)

    reload_enabled = False

    if debug:
        logger.warning("Running FastAPI in DEBUG mode (Uvicorn reload enabled).")
        reload_enabled = True
    else:
        logger.debug("Uvicorn production mode with 1 worker.")

    server_mode = (
        "DEBUG (Uvicorn with reload)" if reload_enabled else "PRODUCTION (Uvicorn)"
    )
    logger.debug("Starting FastAPI web server in %s mode...", server_mode)
    logger.info(
        "Web server starting at http://%s:%s (%s mode).",
        final_host_to_bind,
        final_port,
        "development" if debug else "production",
    )

    try:
        # Create the FastAPI app
        app = create_web_app(app_context)

        config = uvicorn.Config(
            app,
            host=final_host_to_bind,
            port=final_port,
            log_config=None,
            log_level=None,  # Inherit the configured application logging level.
            access_log=True,  # Classify access records at DEBUG without clearing handlers.
            reload=reload_enabled,
            workers=1,  # workers if not reload_enabled and workers > 1 else None,
            forwarded_allow_ips="*",
            proxy_headers=True,
            timeout_graceful_shutdown=10,
        )
        configure_web_logging()
        server = uvicorn.Server(config)
        app_context._web_server = server
        server.run()
    except Exception as e:
        logger.critical("Failed to start Uvicorn: %s", e, exc_info=True)

        raise

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
from typing import List, Optional, Union

import uvicorn

from ..context import AppContext
from .app import create_web_app

logger = logging.getLogger(__name__)


def run_web_server(
    app_context: "AppContext",
    host: Optional[str] = None,
    port: Optional[int] = None,
    debug: bool = False,
    threads: Optional[int] = None,
) -> None:
    """
    Configures and starts the Uvicorn web server to serve the FastAPI application.

    This function is the main entry point for launching the web interface and API
    for the Bedrock Server Manager. It handles:
    - Checking for required authentication environment variables.
    - Determining the host and port based on command-line arguments and application settings.
    - Configuring Uvicorn's operational mode (debug/production), log level, and worker count.
    - Launching Uvicorn to serve the FastAPI application located at
      ``bedrock_server_manager.web.main:app``.

    Extensive logging is performed throughout the configuration and startup sequence.

    Args:
        host (Optional[str]): Specifies the host address
            for Uvicorn to bind to. This can be a single IP address/hostname as a
            string, or a list of addresses/hostnames. If provided via CLI, these
            values take precedence over the ``web.host`` setting in the application
            configuration.
            Defaults to ``None``, in which case the host is determined by the
            ``web.host`` setting (defaulting to "127.0.0.1").
        debug (bool): If ``True``, Uvicorn is run in development mode. This typically
            enables auto-reload on code changes, sets a more verbose log level (debug),
            and uses a single worker process. If ``False`` (default), Uvicorn runs in
            production mode, with the number of worker processes determined by the
            ``web.threads`` setting (or its default).
        threads (Optional[int]): Specifies the number of worker processes for Uvicorn

            Only used for Windows Service

    Raises:
        Exception: Re-raises any exception encountered during `uvicorn.run` if
            Uvicorn itself fails to start (e.g., port already in use, invalid app path).

    Settings Interaction:
        This function reads the following keys from the global ``settings`` object:
        - ``web.port`` (int): The port number for Uvicorn to listen on.
          Defaults to 11325 if not set or invalid. Valid range: 1-65535.
        - ``web.host`` (Union[str, List[str]]): The host address(es) to bind to if
          not overridden by the ``host`` argument. Defaults to "127.0.0.1".
        - ``web.threads`` (int): The number of Uvicorn worker processes to use when
          not in ``debug`` mode. Defaults to 4 if not set or invalid (must be > 0).
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
    workers = 1

    if debug:
        logger.warning("Running FastAPI in DEBUG mode (Uvicorn reload enabled).")
        uvicorn_log_level = "debug"
        reload_enabled = True
    else:
        threads_setting_key = "web.threads"
        try:
            if threads is None:
                workers_val = int(settings.get(threads_setting_key, 4))
                if workers_val > 0:
                    workers = workers_val
                else:
                    logger.warning(
                        f"Invalid '{threads_setting_key}' ({workers_val}). Using default: {workers}."
                    )
            else:
                workers_val = int(threads)
                if workers_val > 0:
                    workers = workers_val
                else:
                    logger.warning(
                        f"Invalid 'threads' passed ({workers}). Using default: {workers}."
                    )
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid format for '{threads_setting_key}'. Using default: {workers}."
            )

        if (
            workers > 1 and reload_enabled
        ):  # This state should ideally be avoided for stability
            logger.warning(
                "Uvicorn reload mode is enabled with multiple workers. This may lead to unexpected behavior. For production, disable reload or use a process manager like Gunicorn with Uvicorn workers."
            )
            # Consider forcing reload_enabled = False if workers > 1 in production mode
        logger.info(f"Uvicorn production mode with {workers} worker(s).")

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

        uvicorn.run(
            app,
            host=final_host_to_bind,
            port=final_port,
            log_config=LOGGING_CONFIG,
            log_level=uvicorn_log_level.lower(),  # Ensure log level is lowercase
            reload=reload_enabled,
            workers=1,  # workers if not reload_enabled and workers > 1 else None,
            forwarded_allow_ips="*",
            proxy_headers=True,
        )
    except Exception as e:
        logger.critical(f"Failed to start Uvicorn: {e}", exc_info=True)

        raise

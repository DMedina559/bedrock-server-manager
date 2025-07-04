# bedrock_server_manager/web/app.py
"""
Provides the main function for configuring and running the Uvicorn web server.

This module contains the :func:`run_web_server` function, which is responsible
for initializing and starting the Uvicorn server that serves the FastAPI application.
The FastAPI application instance (`app`) itself is expected to be defined in
:mod:`bedrock_server_manager.web.main`. This module handles parsing command-line
arguments and application settings to correctly configure Uvicorn's host, port,
debug mode, and worker processes.
"""

import os
import sys
import logging
import ipaddress
from typing import Optional, List, Union

import uvicorn

from bedrock_server_manager.config.const import env_name
from bedrock_server_manager.config.settings import settings

logger = logging.getLogger(__name__)


def run_web_server(
    host: Optional[Union[str, List[str]]] = None, debug: bool = False
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
        host (Optional[Union[str, List[str]]]): Specifies the host address(es)
            for Uvicorn to bind to. This can be a single IP address/hostname as a
            string, or a list of addresses/hostnames. If provided via CLI, these
            values take precedence over the ``web.host`` setting in the application
            configuration. If multiple hosts are given (either via CLI or settings),
            Uvicorn will typically bind to the first one in the list.
            Defaults to ``None``, in which case the host is determined by the
            ``web.host`` setting (defaulting to "127.0.0.1").
        debug (bool): If ``True``, Uvicorn is run in development mode. This typically
            enables auto-reload on code changes, sets a more verbose log level (debug),
            and uses a single worker process. If ``False`` (default), Uvicorn runs in
            production mode, with the number of worker processes determined by the
            ``web.threads`` setting (or its default).

    Raises:
        RuntimeError: If the required authentication environment variables
            (e.g., ``BSM_USERNAME``, ``BSM_PASSWORD``, prefix from :data:`~bedrock_server_manager.config.const.env_name`)
            are not set. The server will not start without these credentials.
        Exception: Re-raises any exception encountered during `uvicorn.run` if
            Uvicorn itself fails to start (e.g., port already in use, invalid app path).

    Environment Variables:
        - ``BSM_USERNAME``: The username for web authentication. (Required, prefix from :data:`~bedrock_server_manager.config.const.env_name`)
        - ``BSM_PASSWORD``: The password for web authentication. (Required, prefix from :data:`~bedrock_server_manager.config.const.env_name`)

    Settings Interaction:
        This function reads the following keys from the global ``settings`` object:
        - ``web.port`` (int): The port number for Uvicorn to listen on.
          Defaults to 11325 if not set or invalid. Valid range: 1-65535.
        - ``web.host`` (Union[str, List[str]]): The host address(es) to bind to if
          not overridden by the ``host`` argument. Defaults to "127.0.0.1".
        - ``web.threads`` (int): The number of Uvicorn worker processes to use when
          not in ``debug`` mode. Defaults to 4 if not set or invalid (must be > 0).
    """

    username_env = f"{env_name}_USERNAME"
    password_env = f"{env_name}_PASSWORD"
    if not os.environ.get(username_env) or not os.environ.get(password_env):
        error_msg = (
            f"Cannot start web server: Required authentication environment variables "
            f"('{username_env}', '{password_env}') are not set."
        )
        logger.critical(error_msg)
        raise RuntimeError(error_msg)
    else:
        logger.info("Web authentication credentials found in environment variables.")

    port_setting_key = "web.port"
    port_val = settings.get(port_setting_key, 11325)
    try:
        port = int(port_val)
        if not (0 < port < 65536):
            raise ValueError("Port out of range")
    except (ValueError, TypeError):
        logger.error(
            f"Invalid port number configured: {port_val}. Using default 11325."
        )
        port = 11325
    logger.info(f"FastAPI server configured to run on port: {port}")

    hosts_to_use_cli: Optional[List[str]] = None
    if host:
        logger.info(f"Using host(s) provided via command-line: {host}")
        if isinstance(host, str):
            hosts_to_use_cli = [host]
        elif isinstance(host, list):
            hosts_to_use_cli = host

    final_host_to_bind = "127.0.0.1"

    if hosts_to_use_cli:
        final_host_to_bind = hosts_to_use_cli[0]
        if len(hosts_to_use_cli) > 1:
            logger.warning(
                f"Multiple hosts via CLI {hosts_to_use_cli}, Uvicorn binds to first: {final_host_to_bind}"
            )
    else:
        logger.info("No host via command-line, using settings.")
        settings_host = settings.get("web.host")
        if isinstance(settings_host, list) and settings_host:
            final_host_to_bind = settings_host[0]
            if len(settings_host) > 1:
                logger.warning(
                    f"Multiple hosts in settings {settings_host}, Uvicorn binds to first: {final_host_to_bind}"
                )
        elif isinstance(settings_host, str) and settings_host:
            final_host_to_bind = settings_host
        else:
            logger.warning(
                f"Host setting 'web.host' invalid ('{settings_host}'). Defaulting to {final_host_to_bind}."
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
            workers_val = int(settings.get(threads_setting_key, 4))
            if workers_val > 0:
                workers = workers_val
            else:
                logger.warning(
                    f"Invalid '{threads_setting_key}' ({workers_val}). Using default: {workers}."
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
    logger.info(f"Listening on: http://{final_host_to_bind}:{port}")

    try:
        uvicorn.run(
            "bedrock_server_manager.web.main:app",  # Path to the FastAPI app instance as a string
            host=final_host_to_bind,
            port=port,
            log_level=uvicorn_log_level.lower(),  # Ensure log level is lowercase
            reload=reload_enabled,
            workers=workers if not reload_enabled and workers > 1 else None,
        )
    except Exception as e:
        logger.critical(f"Failed to start Uvicorn: {e}", exc_info=True)

        raise

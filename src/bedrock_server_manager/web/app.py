# bedrock_server_manager/web/app.py
"""
Initializes and configures the web application instance (FastAPI).
Provides a function to run the web server.
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
    Starts the FastAPI web server using Uvicorn.
    Args:
        host: The host address or list of addresses to bind to from the CLI.
              This takes precedence over the settings file.
        debug: If True, run Uvicorn in development mode (with auto-reload).
               If False (default), run Uvicorn in production mode.
    Raises:
        RuntimeError: If required authentication environment variables are not set.
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

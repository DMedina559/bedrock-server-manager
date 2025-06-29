# bedrock_server_manager/web/app.py
"""
Initializes and configures the Flask web application instance.

Sets up configurations (secret keys, JWT, authentication), registers blueprints
for different application sections, initializes extensions (CSRF, JWT), defines
context processors, and provides a function to run the web server using Waitress
(production) or Flask's built-in development server.
"""

import os
import sys
import logging
import ipaddress
import datetime
import secrets
from typing import Optional, Dict, List, Union

# Third-party imports
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask import Flask

try:
    from waitress import serve

    WAITRESS_AVAILABLE = True
except ImportError:
    WAITRESS_AVAILABLE = False

# Local imports
from bedrock_server_manager.config.const import env_name
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.web.routes.main_routes import main_bp
from bedrock_server_manager.web.utils.variable_inject import inject_global_variables
from bedrock_server_manager.web.routes.schedule_tasks_routes import schedule_tasks_bp
from bedrock_server_manager.web.routes.server_actions_routes import server_actions_bp
from bedrock_server_manager.web.routes.backup_restore_routes import backup_restore_bp
from bedrock_server_manager.web.routes.settings_routes import settings_bp
from bedrock_server_manager.web.routes.api_info_routes import api_info_bp
from bedrock_server_manager.web.routes.content_routes import content_bp
from bedrock_server_manager.web.routes.util_routes import util_bp
from bedrock_server_manager.web.routes.auth_routes import (
    auth_bp,
    jwt,
)
from bedrock_server_manager.web.utils.validators import register_server_validation
from bedrock_server_manager.web.routes.server_install_config_routes import (
    server_install_config_bp,
)
from bedrock_server_manager.web.routes.plugin_routes import plugin_bp
from bedrock_server_manager.error import ConfigurationError

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """
    Factory function to create and configure the Flask application instance.

    Initializes Flask, sets up secret keys, configures CSRF protection and JWT,
    loads authentication credentials, registers blueprints, and sets up context processors.

    Returns:
        The configured Flask application instance.

    Raises:
        RuntimeError: If essential configurations like SECRET_KEY or JWT_SECRET_KEY
                      cannot be properly set.
        ConfigurationError: If required settings like 'paths.servers' are missing.
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    logger.info("Creating and configuring Flask application instance...")

    # --- Basic App Setup (Paths) ---
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    app.template_folder = os.path.join(APP_ROOT, "templates")
    app.static_folder = os.path.join(APP_ROOT, "static")
    app.static_url_path = "/static"
    app.jinja_env.filters["basename"] = os.path.basename
    logger.debug(f"Application Root: {APP_ROOT}")
    logger.debug(f"Template Folder: {app.template_folder}")
    logger.debug(f"Static Folder: {app.static_folder}")

    # --- Validate Essential Settings ---
    if not settings.get("paths.servers"):
        logger.critical(
            "Configuration error: 'paths.servers' setting is missing or empty."
        )
        raise ConfigurationError("Essential setting 'paths.servers' is not configured.")

    # --- Configure Secret Key ( Session) ---
    secret_key_env = f"{env_name}_SECRET"
    secret_key_value = os.environ.get(secret_key_env)
    if secret_key_value:
        app.config["SECRET_KEY"] = secret_key_value
        logger.info(f"Loaded SECRET_KEY from environment variable '{secret_key_env}'.")
    else:
        app.config["SECRET_KEY"] = secrets.token_hex(16)
        logger.warning(
            f"!!! SECURITY WARNING !!! Using randomly generated SECRET_KEY. "
            f"Flask sessions will not persist across application restarts. "
            f"Set the '{secret_key_env}' environment variable for production."
        )
    if not app.config.get("SECRET_KEY"):
        logger.critical(
            "FATAL: SECRET_KEY is missing after configuration attempt. Cannot initialize CSRF/Session."
        )
        raise RuntimeError(
            "SECRET_KEY must be set for CSRF protection and session management."
        )
    logger.debug("SECRET_KEY configured.")

    # --- Configure JWT ---
    jwt_secret_key_env = f"{env_name}_TOKEN"
    jwt_secret_key_value = os.environ.get(jwt_secret_key_env)
    if jwt_secret_key_value:
        app.config["JWT_SECRET_KEY"] = jwt_secret_key_value
        logger.info(
            f"Loaded JWT_SECRET_KEY from environment variable '{jwt_secret_key_env}'."
        )
    else:
        app.config["JWT_SECRET_KEY"] = secrets.token_urlsafe(32)
        logger.critical(
            f"!!! SECURITY WARNING !!! Using randomly generated JWT_SECRET_KEY. "
            f"This is NOT suitable for production deployments. Existing JWTs will become invalid "
            f"after application restarts. Set the '{jwt_secret_key_env}' environment variable "
            f"with a persistent, strong, secret key!"
        )
    if not app.config.get("JWT_SECRET_KEY"):
        logger.critical(
            "FATAL: JWT_SECRET_KEY is missing after configuration attempt. JWT functionality will fail."
        )
        raise RuntimeError("JWT_SECRET_KEY must be set for JWT functionality.")
    logger.debug("JWT_SECRET_KEY configured.")

    # Configure JWT expiration time from settings
    try:
        jwt_expires_weeks = float(settings.get("web.token_expires_weeks", 4.0))
        app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(
            weeks=jwt_expires_weeks
        )
        logger.debug(f"JWT access token expiration set to {jwt_expires_weeks} weeks.")
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Invalid format for 'web.token_expires_weeks' setting. Using default (4 weeks). Error: {e}",
            exc_info=True,
        )
        app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(weeks=4)

    # Configure JWT to look for tokens in cookies and headers
    app.config["JWT_TOKEN_LOCATION"] = ["cookies", "headers"]

    app.config["JWT_COOKIE_SECURE"] = settings.get("web.jwt_cookie_secure", False)
    app.config["JWT_COOKIE_SAMESITE"] = settings.get("web.jwt_cookie_samesite", "Lax")
    app.config["JWT_COOKIE_HTTPONLY"] = True  # JavaScript cannot access the cookie
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    app.config["JWT_SESSION_COOKIE"] = (
        False  # Make it a persistent cookie based on token expiration, not browser session
    )

    # Initialize JWT Manager
    jwt.init_app(app)
    logger.info("Initialized Flask-JWT-Extended with cookie and header support.")
    logger.debug(f"JWT_TOKEN_LOCATION: {app.config['JWT_TOKEN_LOCATION']}")
    logger.debug(f"JWT_COOKIE_SECURE: {app.config['JWT_COOKIE_SECURE']}")
    logger.debug(f"JWT_COOKIE_SAMESITE: {app.config['JWT_COOKIE_SAMESITE']}")

    # --- Load Web UI Authentication Credentials ---
    username_env = f"{env_name}_USERNAME"
    password_env = f"{env_name}_PASSWORD"
    app.config[username_env] = os.environ.get(username_env)
    app.config[password_env] = os.environ.get(password_env)

    if not app.config[username_env] or not app.config[password_env]:
        logger.warning(
            f"Web authentication environment variables ('{username_env}', '{password_env}') "
            f"are not set. Web UI login will not function correctly."
        )
    else:
        logger.info("Web authentication credentials loaded from environment variables.")

    # --- Register Blueprints ---
    app.register_blueprint(main_bp)
    app.register_blueprint(schedule_tasks_bp)
    app.register_blueprint(server_actions_bp)
    app.register_blueprint(server_install_config_bp)
    app.register_blueprint(backup_restore_bp)
    app.register_blueprint(content_bp)
    app.register_blueprint(util_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_info_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(plugin_bp)
    logger.debug("Registered application blueprints.")

    # --- Register Context Processors ---
    app.context_processor(inject_global_variables)
    logger.debug("Registered context processor: inject_global_variables.")

    @app.context_processor
    def inject_user() -> Dict[str, Union[bool, str, None]]:
        is_logged_in = False
        current_username = None
        try:
            # Check for JWT presence without enforcing authentication if optional=True
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
            if identity:
                is_logged_in = True
                current_username = identity
        except Exception:
            # If any JWT related error (even optional check), assume not logged in via JWT
            pass
        return dict(is_logged_in=is_logged_in, current_username=current_username)
    logger.debug("Registered context processor: inject_user (login status).")

    # --- Register Request Validators ---
    register_server_validation(app)
    logger.debug("Registered before_request handler: register_server_validation.")

    logger.info("Flask application creation and configuration complete.")
    return app


def run_web_server(
    host: Optional[Union[str, List[str]]] = None, debug: bool = False
) -> None:
    """
    Starts the Flask web server using Waitress (production) or Flask dev server (debug).
    Args:
        host: The host address or list of addresses to bind to from the CLI.
              This takes precedence over the settings file.
        debug: If True, run using Flask's built-in development server.
               If False (default), run using Waitress production WSGI server.
    Raises:
        RuntimeError: If required authentication environment variables are not set.
    """
    app = create_app()

    username_env = f"{env_name}_USERNAME"
    password_env = f"{env_name}_PASSWORD"
    if not app.config.get(username_env) or not app.config.get(password_env):
        error_msg = (
            f"Cannot start web server: Required authentication environment variables "
            f"('{username_env}', '{password_env}') are not set."
        )
        logger.critical(error_msg)
        raise RuntimeError(error_msg)

    # --- Get Port from Settings ---
    port_setting_key = "web.port"
    port_val = settings.get(port_setting_key, 11325)
    try:
        port = int(port_val)
        if not (0 < port < 65536):
            raise ValueError("Port out of range")
    except (ValueError, TypeError):
        logger.error(
            f"Invalid port number configured in setting '{port_setting_key}': {port_val}. Using default 11325."
        )
        port = 11325
    logger.info(f"Web server configured to run on port: {port}")

    # --- Determine Host Binding ---
    # Prioritize host from CLI argument, otherwise use settings.
    hosts_to_use: Optional[List[str]] = None
    if host:
        logger.info(f"Using host(s) provided via command-line: {host}")
        if isinstance(host, str):
            hosts_to_use = [host]
        elif isinstance(host, list):
            hosts_to_use = host
    else:
        logger.info(
            "No host provided via command-line, using host(s) from settings file."
        )
        hosts_to_use = settings.get("web.host")

    # --- Prepare Listen Addresses ---
    listen_addresses = []
    host_info = ""
    valid_hosts = (
        [str(h) for h in hosts_to_use if h] if isinstance(hosts_to_use, list) else []
    )

    if valid_hosts:
        host_info = f"specified address(es): {', '.join(valid_hosts)}"
        for h_item in valid_hosts:
            try:
                ip = ipaddress.ip_address(h_item)
                if isinstance(ip, ipaddress.IPv6Address):
                    listen_addresses.append(f"[{h_item}]:{port}")
                else:
                    listen_addresses.append(f"{h_item}:{port}")
            except ValueError:
                listen_addresses.append(f"{h_item}:{port}")  # Assume hostname
        logger.info(f"Preparing to bind to {host_info} -> {listen_addresses}")
    else:
        # Fallback if settings are misconfigured or empty
        listen_addresses = [f"127.0.0.1:{port}", f"[::1]:{port}"]
        host_info = f"default local interfaces (host setting was empty or invalid: {hosts_to_use})"
        logger.warning(f"Binding to {host_info} -> {listen_addresses}")

    server_mode = (
        "DEBUG (Flask Development Server)" if debug else "PRODUCTION (Waitress)"
    )
    logger.info(f"Starting web server in {server_mode} mode...")

    if debug:
        logger.warning("Running in DEBUG mode. NOT SUITABLE FOR PRODUCTION.")
        # Flask dev server can only bind to one host. Use the first valid one.
        debug_host_to_run = "127.0.0.1"  # Default
        if valid_hosts:
            debug_host_to_run = valid_hosts[0]
            if len(valid_hosts) > 1:
                logger.warning(
                    f"Debug mode: Multiple hosts specified {valid_hosts}, but will only bind to the first: {debug_host_to_run}"
                )

        logger.info(
            f"Attempting to start Flask dev server on http://{debug_host_to_run}:{port}"
        )
        try:
            app.run(host=debug_host_to_run, port=port, debug=True)
        except OSError as e:
            logger.critical(
                f"Failed to start Flask development server on {debug_host_to_run}:{port}. Error: {e}",
                exc_info=True,
            )
            sys.exit(1)

    else:  # Production (Waitress)
        if not WAITRESS_AVAILABLE:
            logger.error("Waitress package not found. Cannot start production server.")
            raise ImportError(
                "Install Waitress to run in production mode: pip install waitress"
            )

        threads_setting_key = "web.threads"
        waitress_threads = 8  # Default fallback
        try:
            threads_val = int(settings.get(threads_setting_key, 8))
            if threads_val > 0:
                waitress_threads = threads_val
            else:
                logger.warning(
                    f"Invalid value for '{threads_setting_key}' ({threads_val}). "
                    "Must be a positive number. Using default: {waitress_threads}."
                )
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid format for '{threads_setting_key}' setting. "
                f"Expected an integer. Using default: {waitress_threads}."
            )

        logger.info(f"Waitress will use {waitress_threads} worker threads.")

        listen_string = " ".join(listen_addresses)
        logger.info(
            f"Starting Waitress production server. Listening on: {listen_string}"
        )
        try:
            serve(app, listen=listen_string, threads=waitress_threads)
        except Exception as e:
            logger.critical(
                f"Failed to start Waitress server. Error: {e}", exc_info=True
            )
            raise

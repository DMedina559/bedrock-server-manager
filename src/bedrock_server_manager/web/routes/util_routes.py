# bedrock_server_manager/web/routes/util_routes.py
"""
Flask Blueprint for utility routes within the web application.

Includes routes for serving dynamic content like world/server icons,
custom panoramas, the server monitoring page, and a catch-all route
for undefined paths.
"""

import os
import logging

from flask import (
    Blueprint,
    send_from_directory,
    current_app,
    url_for,
    redirect,
    Response,
)

from bedrock_server_manager.core.bedrock_server import BedrockServer
from bedrock_server_manager.config.settings import settings

from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
)
from bedrock_server_manager.error import BSMError, AppFileNotFoundError

logger = logging.getLogger(__name__)

util_bp = Blueprint(
    "util_routes", __name__, template_folder="../templates", static_folder="../static"
)


# --- Route: Serve World Icon ---
@util_bp.route("/api/server/<string:server_name>/world/icon")
@auth_required
def serve_world_icon(server_name: str) -> Response:
    """Serves the `world_icon.jpeg` file for a specific server's world."""
    logger.debug(f"Request to serve world icon for server '{server_name}'.")
    icon_path: str | None = None
    try:
        server = BedrockServer(server_name)
        icon_path = server.world_icon_filesystem_path
        if server.has_world_icon():
            logger.debug(f"Serving world icon from path: {icon_path}")
            return send_from_directory(
                directory=os.path.dirname(icon_path),
                path=os.path.basename(icon_path),
                mimetype="image/jpeg",
            )
        else:
            raise AppFileNotFoundError(str(icon_path), "World icon")
    except BSMError as e:
        if not isinstance(e, AppFileNotFoundError):
            logger.error(
                f"Error serving world icon for '{server_name}': {e}", exc_info=True
            )
        else:
            logger.info(f"World icon for '{server_name}' not found. Serving default.")
        try:
            default_icon_dir = os.path.join(current_app.static_folder, "image", "icon")
            default_icon_file = "favicon.ico"
            return send_from_directory(
                directory=default_icon_dir,
                path=default_icon_file,
                mimetype="image/vnd.microsoft.icon",
            )
        except Exception as fallback_err:
            logger.error(
                f"Failed to serve default fallback icon: {fallback_err}", exc_info=True
            )
            return "Default icon not found", 404
    except Exception as e:
        logger.error(
            f"Unexpected error serving world icon for '{server_name}': {e}",
            exc_info=True,
        )
        return "Error serving icon", 500


# --- Route: Serve Custom Panorama ---
@util_bp.route("/api/panorama")
def serve_custom_panorama() -> Response:
    """Serves a custom `panorama.jpeg` background image if it exists."""
    logger.debug("Request received to serve custom panorama background.")
    try:
        config_dir = settings.config_dir
        if not config_dir:
            raise AppFileNotFoundError("CONFIG_DIR not set in settings.", "Setting")
        return send_from_directory(
            directory=config_dir, path="panorama.jpeg", mimetype="image/jpeg"
        )
    except AppFileNotFoundError:
        logger.info("Custom panorama not found. Serving default.")
        try:
            return send_from_directory(
                directory=os.path.join(current_app.static_folder, "image"),
                path="panorama.jpeg",
                mimetype="image/jpeg",
            )
        except Exception as fallback_err:
            logger.error(
                f"Failed to serve default panorama: {fallback_err}", exc_info=True
            )
            return "Default panorama not found", 404
    except Exception as e:
        logger.error(f"Unexpected error serving custom panorama: {e}", exc_info=True)
        return "Error serving panorama image", 500


# --- Catch-all Route ---
@util_bp.route("/<path:unused_path>")
@auth_required
def catch_all(unused_path: str) -> Response:
    """Redirects any unmatched route to the main dashboard page."""
    logger.warning(
        f"Caught undefined path: '/{unused_path}'. Redirecting to dashboard."
    )
    return redirect(url_for("main_routes.index"))

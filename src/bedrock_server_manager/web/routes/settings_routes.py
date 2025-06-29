# bedrock_server_manager/web/routes/settings_routes.py
"""
Flask Blueprint for managing global application settings through the web UI.
"""
import logging
from typing import Tuple, Dict, Any

from flask import Blueprint, render_template, request, jsonify, Response

from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.api import settings as settings_api
from bedrock_server_manager.error import BSMError, UserInputError, MissingArgumentError

logger = logging.getLogger(__name__)

settings_bp = Blueprint(
    "settings_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


# --- Route: Manage Global Settings Page ---
@settings_bp.route("/settings")
@auth_required
def manage_settings_page() -> Response:
    """
    Renders the global settings management page.
    """
    identity = get_current_identity() or "Unknown User"
    logger.info(f"User '{identity}' accessed global settings page.")
    return render_template("manage_settings.html")


# --- API Route: Get All Global Settings ---
@settings_bp.route("/api/settings", methods=["GET"])
@auth_required
def get_settings_route() -> Tuple[Response, int]:
    identity = get_current_identity() or "API Request"
    logger.info(f"API: Get global settings request by '{identity}'.")
    try:
        result = settings_api.get_all_global_settings()
        status_code = 200 if result.get("status") == "success" else 500
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"API Get Settings: Unexpected error. {e}", exc_info=True)
        return jsonify(status="error", message="An unexpected error occurred."), 500


# --- API Route: Set a Global Setting ---
@settings_bp.route("/api/settings", methods=["POST"])
@auth_required
def set_setting_route() -> Tuple[Response, int]:
    identity = get_current_identity() or "API Request"
    data = request.get_json()
    if not data or "key" not in data:
        return (
            jsonify(status="error", message="Request must be JSON with a 'key' field."),
            400,
        )
    key = data.get("key")
    value = data.get("value")
    logger.info(f"API: Set global setting request for '{key}' by '{identity}'.")
    try:
        result = settings_api.set_global_setting(key, value)
        status_code = 200 if result.get("status") == "success" else 500
        return jsonify(result), status_code
    except (UserInputError, MissingArgumentError) as e:
        logger.warning(f"API Set Setting '{key}': Input error. {e}")
        return jsonify(status="error", message=str(e)), 400
    except Exception as e:
        logger.error(f"API Set Setting '{key}': Unexpected error. {e}", exc_info=True)
        return jsonify(status="error", message="An unexpected error occurred."), 500


# --- API Route: Reload Global Settings ---
@settings_bp.route("/api/settings/reload", methods=["POST"])
@auth_required
def reload_settings_route() -> Tuple[Response, int]:
    identity = get_current_identity() or "API Request"
    logger.info(f"API: Reload global settings request by '{identity}'.")
    try:
        result = settings_api.reload_global_settings()
        status_code = 200 if result.get("status") == "success" else 500
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"API Reload Settings: Unexpected error. {e}", exc_info=True)
        return jsonify(status="error", message="An unexpected error occurred."), 500

# bedrock_server_manager/web/routes/plugin_routes.py
"""
Flask Blueprint for managing plugin configurations through the web UI.
"""
import logging
from typing import Tuple, Dict, Any

from flask import Blueprint, render_template, request, jsonify, Response

from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.api import plugins as plugins_api
from bedrock_server_manager.error import BSMError, UserInputError

logger = logging.getLogger(__name__)

plugin_bp = Blueprint("plugin_routes", __name__, template_folder="../templates")


# --- Route: Manage Plugins Page ---
@plugin_bp.route("/plugins")
@auth_required
def manage_plugins_page() -> Response:
    """
    Renders the plugin management page.
    """
    identity = get_current_identity() or "Unknown User"
    logger.info(f"User '{identity}' accessed plugin management page.")
    return render_template("manage_plugins.html")


# --- API Route: Get Plugin Statuses ---
@plugin_bp.route("/api/plugins", methods=["GET"])
@auth_required
def get_plugins_status_route() -> Tuple[Response, int]:
    identity = get_current_identity() or "API Request"
    logger.info(f"API: Get plugin statuses request by '{identity}'.")
    result: Dict[str, Any]
    status_code: int
    try:
        result = plugins_api.get_plugin_statuses()
        if result.get("status") == "success":
            status_code = 200
        else:
            status_code = 500
            logger.error(f"API Get Plugins: Failed. {result.get('message')}")
    except Exception as e:
        status_code = 500
        result = {"status": "error", "message": "An unexpected error occurred."}
        logger.error(f"API Get Plugins: Unexpected error. {e}", exc_info=True)
    return jsonify(result), status_code


# --- API Route: Trigger Custom Plugin Event ---
@plugin_bp.route("/api/plugins/trigger_event", methods=["POST"])
@auth_required
def trigger_custom_event_route() -> Tuple[Response, int]:
    identity = get_current_identity() or "External API Event Trigger"
    logger.info(f"API: Custom plugin event trigger request by '{identity}'.")
    data = request.get_json()
    if data is None:
        return jsonify(status="error", message="Request must be JSON."), 400
    event_name = data.get("event_name")
    payload = data.get("payload")
    if not event_name:
        return jsonify(status="error", message="'event_name' is a required field."), 400
    if payload is not None and not isinstance(payload, dict):
        return (
            jsonify(status="error", message="'payload' must be an object if provided."),
            400,
        )

    result: Dict[str, Any]
    status_code: int
    try:
        result = plugins_api.trigger_external_plugin_event_api(event_name, payload)
        if result.get("status") == "success":
            status_code = 200
        else:
            status_code = 500
            logger.error(f"API Trigger Event: Failed. {result.get('message')}")
    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
    except BSMError as e:
        status_code = 500
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        status_code = 500
        result = {"status": "error", "message": "An unexpected error occurred."}
        logger.error(
            f"API Trigger Event '{event_name}': Unexpected error. {e}", exc_info=True
        )
    return jsonify(result), status_code


# --- API Route: Set Plugin Status ---
@plugin_bp.route("/api/plugins/<string:plugin_name>", methods=["POST"])
@auth_required
def set_plugin_status_route(plugin_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "API Request"
    logger.info(f"API: Set plugin status request for '{plugin_name}' by '{identity}'.")
    data = request.get_json()
    if data is None or "enabled" not in data or not isinstance(data["enabled"], bool):
        return (
            jsonify(
                status="error", message="Request must be JSON with 'enabled' boolean."
            ),
            400,
        )

    enabled = data["enabled"]
    result: Dict[str, Any]
    status_code: int
    try:
        result = plugins_api.set_plugin_status(plugin_name, enabled)
        if result.get("status") == "success":
            status_code = 200
        else:
            status_code = result.get("error_code", 500)
            logger.error(
                f"API Set Plugin '{plugin_name}': Failed. {result.get('message')}"
            )
    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
    except BSMError as e:
        status_code = 500
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        status_code = 500
        result = {"status": "error", "message": "An unexpected error occurred."}
        logger.error(
            f"API Set Plugin '{plugin_name}': Unexpected error. {e}", exc_info=True
        )
    return jsonify(result), status_code


@plugin_bp.route("/api/plugins/reload", methods=["POST"])
@auth_required
def reload_plugins_route() -> Tuple[Response, int]:
    identity = get_current_identity() or "API Request"
    logger.info(f"API: Reload plugins request by '{identity}'.")
    result: Dict[str, Any]
    status_code: int
    try:
        result = plugins_api.reload_plugins()
        if result.get("status") == "success":
            status_code = 200
        else:
            status_code = 500
            logger.error(f"API Reload Plugins: Failed. {result.get('message')}")
    except Exception as e:
        status_code = 500
        result = {"status": "error", "message": "An unexpected error occurred."}
        logger.error(f"API Reload Plugins: Unexpected error. {e}", exc_info=True)
    return jsonify(result), status_code

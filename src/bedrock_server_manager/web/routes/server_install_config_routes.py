# bedrock_server_manager/web/routes/server_install_config_routes.py
"""
Flask Blueprint handling web routes and API endpoints related to new server
installation and the configuration of existing servers (properties, allowlist,
permissions, OS services).
"""

import logging
import platform
import threading
from typing import Dict, List, Any, Tuple

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    Response,
)

from bedrock_server_manager.api import server_install_config
from bedrock_server_manager.api import server as server_api
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.api import system as system_api
from bedrock_server_manager.api import utils as utils_api

from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
    InvalidServerNameError,
)

logger = logging.getLogger(__name__)

server_install_config_bp = Blueprint(
    "install_config_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


# --- HTML Routes ---
@server_install_config_bp.route("/install", methods=["GET"])
@auth_required
def install_server_route() -> Response:
    identity = get_current_identity()
    logger.info(f"User '{identity}' accessed new server install page.")
    return render_template("install.html")


@server_install_config_bp.route(
    "/server/<string:server_name>/configure_properties", methods=["GET"]
)
@auth_required
def configure_properties_route(server_name: str) -> Response:
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed configure properties for server '{server_name}'."
    )
    return render_template(
        "configure_properties.html",
        server_name=server_name,
        new_install=request.args.get("new_install", "false").lower() == "true",
    )


@server_install_config_bp.route(
    "/server/<string:server_name>/configure_allowlist", methods=["GET"]
)
@auth_required
def configure_allowlist_route(server_name: str) -> Response:
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed configure allowlist for server '{server_name}'."
    )
    return render_template(
        "configure_allowlist.html",
        server_name=server_name,
        new_install=request.args.get("new_install", "false").lower() == "true",
    )


@server_install_config_bp.route(
    "/server/<string:server_name>/configure_permissions", methods=["GET"]
)
@auth_required
def configure_permissions_route(server_name: str) -> Response:
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed configure permissions for server '{server_name}'."
    )
    return render_template(
        "configure_permissions.html",
        server_name=server_name,
        new_install=request.args.get("new_install", "false").lower() == "true",
    )


@server_install_config_bp.route(
    "/server/<string:server_name>/configure_service", methods=["GET"]
)
@auth_required
def configure_service_route(server_name: str) -> Response:
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed configure service page for server '{server_name}'."
    )
    try:
        template_data = {
            "server_name": server_name,
            "os": platform.system(),
            "new_install": request.args.get("new_install", "false").lower() == "true",
            "service_exists": False,
            "autostart_enabled": False,
            "autoupdate_enabled": False,
        }
        return render_template("configure_service.html", **template_data)
    except Exception as e:
        flash("An unexpected error occurred loading service settings.", "danger")
        logger.error(
            f"Unexpected error loading service page for '{server_name}': {e}",
            exc_info=True,
        )
        return render_template(
            "configure_service.html",
            os=platform.system(),
            new_install=request.args.get("new_install", "false").lower() == "true",
        )


# --- API Routes ---
@server_install_config_bp.route("/api/server/install", methods=["POST"])
@auth_required
def install_server_api_route() -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: New server install request from user '{identity}'.")
    data = request.get_json()
    if not data:
        return jsonify(status="error", message="Invalid or missing JSON body."), 400
    server_name = data.get("server_name", "").strip()
    server_version = data.get("server_version", "LATEST").strip()
    overwrite = data.get("overwrite", False)
    validation_result = utils_api.validate_server_name_format(server_name)
    if validation_result.get("status") == "error":
        return jsonify(validation_result), 400
    result: Dict[str, Any]
    status_code: int
    try:
        if not overwrite and utils_api.validate_server_exist(server_name):
            return (
                jsonify(
                    status="confirm_needed",
                    message=f"Server '{server_name}' already exists. Overwrite?",
                ),
                200,
            )
        if overwrite and utils_api.validate_server_exist(server_name):
            delete_result = server_api.delete_server_data(server_name)
            if delete_result.get("status") == "error":
                return (
                    jsonify(
                        status="error",
                        message=f"Failed to delete existing server: {delete_result['message']}",
                    ),
                    500,
                )
        result = server_install_config.install_new_server(server_name, server_version)
        if result.get("status") == "success":
            status_code = 201
            result["next_step_url"] = url_for(
                ".configure_properties_route", server_name=server_name, new_install=True
            )
        else:
            status_code = 500
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
            f"API Install Server '{server_name}': Unexpected error. {e}", exc_info=True
        )
    return jsonify(result), status_code


@server_install_config_bp.route(
    "/api/server/<string:server_name>/properties/set", methods=["POST"]
)
@auth_required
def configure_properties_api_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Configure properties request for '{server_name}' by user '{identity}'."
    )
    properties_data = request.get_json()
    if not isinstance(properties_data, dict):
        return (
            jsonify(status="error", message="Invalid or missing JSON object body."),
            400,
        )
    result: Dict[str, Any]
    status_code: int
    try:
        result = server_install_config.modify_server_properties(
            server_name, properties_data
        )
        status_code = 200 if result.get("status") == "success" else 400
    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
    except Exception as e:
        status_code = 500
        result = {"status": "error", "message": "An unexpected error occurred."}
        logger.error(
            f"API Modify Properties '{server_name}': Unexpected error. {e}",
            exc_info=True,
        )
    return jsonify(result), status_code


@server_install_config_bp.route(
    "/api/server/<string:server_name>/properties/get", methods=["GET"]
)
@auth_required
def get_server_properties_route(server_name: str) -> Tuple[Response, int]:
    result = server_install_config.get_server_properties_api(server_name)
    if result.get("status") == "success":
        return jsonify(result), 200
    if "not found" in result.get("message", "").lower():
        return jsonify(result), 404
    return jsonify(result), 500


@server_install_config_bp.route(
    "/api/server/<string:server_name>/allowlist/add", methods=["POST"]
)
@auth_required
def add_to_allowlist_api_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Add to allowlist request for '{server_name}' by user '{identity}'."
    )
    data = request.get_json()
    if not data or not isinstance(data.get("players"), list):
        return (
            jsonify(status="error", message="Request must contain a 'players' list."),
            400,
        )
    new_players = [
        {"name": p, "ignoresPlayerLimit": data.get("ignoresPlayerLimit", False)}
        for p in data["players"]
    ]
    try:
        result = server_install_config.add_players_to_allowlist_api(
            server_name, new_players
        )
        return jsonify(result), 200 if result.get("status") == "success" else 500
    except BSMError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.error(
            f"API Add Allowlist '{server_name}': Unexpected error. {e}", exc_info=True
        )
        return (
            jsonify({"status": "error", "message": "An unexpected error occurred."}),
            500,
        )


@server_install_config_bp.route(
    "/api/server/<string:server_name>/allowlist/get", methods=["GET"]
)
@auth_required
def get_allowlist_api_route(server_name: str) -> Tuple[Response, int]:
    result = server_install_config.get_server_allowlist_api(server_name)
    if result.get("status") == "success":
        return (
            jsonify(
                {"status": "success", "existing_players": result.get("players", [])}
            ),
            200,
        )
    return jsonify(result), 500


@server_install_config_bp.route(
    "/api/server/<string:server_name>/allowlist/remove", methods=["DELETE"]
)
@auth_required
def remove_allowlist_players_api_route(server_name: str) -> Tuple[Response, int]:
    try:
        data = request.get_json()
        if not data or "players" not in data or not isinstance(data["players"], list):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Request body must be JSON object with 'players' list.",
                    }
                ),
                400,
            )
        result = server_install_config.remove_players_from_allowlist(
            server_name, data["players"]
        )
        return jsonify(result), 200
    except BSMError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.error(
            f"API Bulk Remove Allowlist Players '{server_name}': Unexpected error. {e}",
            exc_info=True,
        )
        return (
            jsonify(
                {"status": "error", "message": "An unexpected server error occurred."}
            ),
            500,
        )


@server_install_config_bp.route(
    "/api/server/<string:server_name>/permissions/set", methods=["PUT"]
)
@auth_required
def configure_permissions_api_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Configure permissions request for '{server_name}' by user '{identity}'."
    )
    data = request.get_json()
    if not isinstance(data, dict) or not isinstance(data.get("permissions"), dict):
        return (
            jsonify(
                status="error", message="Request must contain a 'permissions' object."
            ),
            400,
        )
    permissions_map = data["permissions"]
    errors = {}
    success_count = 0
    for xuid, level in permissions_map.items():
        try:
            result = server_install_config.configure_player_permission(
                server_name, xuid, None, level
            )
            if result.get("status") == "success":
                success_count += 1
            else:
                errors[xuid] = result.get("message", "Unknown error")
        except BSMError as e:
            errors[xuid] = str(e)
        except Exception as e:
            logger.error(
                f"API Permissions Update '{server_name}': Error for XUID {xuid}. {e}",
                exc_info=True,
            )
            errors[xuid] = "An unexpected server error occurred."
    if not errors:
        return (
            jsonify(
                status="success",
                message=f"Permissions updated for {success_count} player(s).",
            ),
            200,
        )
    else:
        return (
            jsonify(
                status="error", message="One or more errors occurred.", errors=errors
            ),
            500,
        )


@server_install_config_bp.route(
    "/api/server/<string:server_name>/permissions/get", methods=["GET"]
)
@auth_required
def get_server_permissions_data_route(server_name: str) -> Tuple[Response, int]:
    result = server_install_config.get_server_permissions_api(server_name)
    if result.get("status") == "success":
        return jsonify(result), 200
    if "not found" in result.get("message", "").lower():
        return jsonify(result), 404
    return jsonify(result), 500


@server_install_config_bp.route(
    "/api/server/<string:server_name>/service/update", methods=["POST"]
)
@auth_required
def configure_service_api_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Configure service request for '{server_name}' by user '{identity}'."
    )
    current_os = platform.system()
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify(status="error", message="Invalid JSON body."), 400
    autoupdate = data.get("autoupdate")
    autostart = data.get("autostart")
    if autoupdate is None and autostart is None:
        return jsonify(status="error", message="No options provided."), 400
    try:
        if autoupdate is not None:
            if not isinstance(autoupdate, bool):
                return jsonify(status="error", message="'autoupdate' boolean."), 400
            result = system_api.set_autoupdate(server_name, str(autoupdate))
            if result.get("status") != "success":
                return jsonify(result), 500
        if autostart is not None:
            if not isinstance(autostart, bool):
                return jsonify(status="error", message="'autostart' boolean."), 400
            if current_os in ["Linux", "Windows"]:
                result = system_api.create_server_service(server_name, autostart)
                if result.get("status") != "success":
                    return jsonify(result), 500
            else:
                logger.warning(
                    f"API: 'autostart' ignored for '{server_name}': unsupported OS ({current_os})."
                )
        return (
            jsonify(
                {"status": "success", "message": "Configuration applied successfully."}
            ),
            200,
        )
    except BSMError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        logger.error(
            f"API Configure Service '{server_name}': Unexpected error. {e}",
            exc_info=True,
        )
        return (
            jsonify(
                {"status": "error", "message": "An unexpected server error occurred."}
            ),
            500,
        )

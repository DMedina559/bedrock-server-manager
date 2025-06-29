# bedrock_server_manager/web/routes/content_routes.py
"""
Flask Blueprint for handling web routes and API endpoints related to
server content management (Worlds, Addons).
"""

import os
import logging
import threading
from typing import Tuple, Dict, Any, List

# Third-party imports
from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    jsonify,
    Response,
)

# Local imports
from bedrock_server_manager.api import world as world_api
from bedrock_server_manager.api import addon as addon_api
from bedrock_server_manager.api import application as api_application
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.error import (
    BSMError,
    InvalidServerNameError,
)

logger = logging.getLogger(__name__)

content_bp = Blueprint(
    "content_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)

# --- HTML Routes ---


@content_bp.route("/server/<string:server_name>/install_world")
@auth_required
def install_world_route(server_name: str) -> Response:
    """Renders the page allowing users to select a world for installation."""
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed world install selection page for server '{server_name}'."
    )

    list_result = api_application.list_available_worlds_api()
    world_files: List[str] = []
    if list_result.get("status") == "error":
        flash(
            f"Error listing world files: {list_result.get('message', 'Unknown error')}",
            "error",
        )
    else:
        full_paths = list_result.get("files", [])
        world_files = [os.path.basename(p) for p in full_paths]

    return render_template(
        "select_world.html",
        server_name=server_name,
        world_files=world_files,
    )


@content_bp.route("/server/<string:server_name>/install_addon")
@auth_required
def install_addon_route(server_name: str) -> Response:
    """Renders the page for selecting an addon to install."""
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed addon install selection page for server '{server_name}'."
    )

    list_result = api_application.list_available_addons_api()
    addon_files: List[str] = []
    if list_result.get("status") == "error":
        flash(
            f"Error listing addon files: {list_result.get('message', 'Unknown error')}",
            "error",
        )
    else:
        full_paths = list_result.get("files", [])
        addon_files = [os.path.basename(p) for p in full_paths]

    return render_template(
        "select_addon.html",
        server_name=server_name,
        addon_files=addon_files,
    )


# ------


# --- API Routes ---
@content_bp.route("/api/content/worlds", methods=["GET"])
@auth_required
def list_worlds_route() -> Tuple[Response, int]:
    """API endpoint to list available world content files."""
    logger.info("API Route: Request to list world content files.")
    try:
        api_result = api_application.list_available_worlds_api()
        if api_result.get("status") == "success":
            full_paths = api_result.get("files", [])
            basenames = [os.path.basename(p) for p in full_paths]
            return jsonify({"status": "success", "files": basenames}), 200
        else:
            logger.warning(
                f"API Route: Error listing worlds: {api_result.get('message')}"
            )
            return jsonify(api_result), 500
    except Exception as e:
        logger.error(
            f"API Route: Unexpected critical error listing worlds: {e}", exc_info=True
        )
        return (
            jsonify(
                {"status": "error", "message": "A critical server error occurred."}
            ),
            500,
        )


@content_bp.route("/api/content/addons", methods=["GET"])
@auth_required
def list_addons_route() -> Tuple[Response, int]:
    """API endpoint to list available addon content files."""
    logger.info("API Route: Request to list addon content files.")
    try:
        api_result = api_application.list_available_addons_api()
        if api_result.get("status") == "success":
            full_paths = api_result.get("files", [])
            basenames = [os.path.basename(p) for p in full_paths]
            return jsonify({"status": "success", "files": basenames}), 200
        else:
            logger.warning(
                f"API Route: Error listing addons: {api_result.get('message')}"
            )
            return jsonify(api_result), 500
    except Exception as e:
        logger.error(
            f"API Route: Unexpected critical error listing addons: {e}", exc_info=True
        )
        return (
            jsonify(
                {"status": "error", "message": "A critical server error occurred."}
            ),
            500,
        )


@content_bp.route("/api/server/<string:server_name>/world/install", methods=["POST"])
@auth_required
def install_world_api_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to install a user-selected world to a server."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: World install requested for '{server_name}' by user '{identity}'."
    )

    data = request.get_json()
    if not data or "filename" not in data:
        return (
            jsonify(
                status="error",
                message="Invalid or missing JSON body with 'filename' key.",
            ),
            400,
        )

    selected_filename = data["filename"]

    try:
        content_base_dir = os.path.join(settings.get("paths.content"), "worlds")
        full_world_file_path = os.path.normpath(
            os.path.join(content_base_dir, selected_filename)
        )

        if not os.path.abspath(full_world_file_path).startswith(
            os.path.abspath(content_base_dir)
        ):
            return (
                jsonify(
                    status="error", message="Invalid file path (security check failed)."
                ),
                400,
            )

        if not os.path.isfile(full_world_file_path):
            return (
                jsonify(
                    status="error",
                    message=f"World file '{selected_filename}' not found for import.",
                ),
                404,
            )
    except Exception as e_pre_check:
        logger.error(
            f"API Install World '{server_name}': Pre-check error: {e_pre_check}",
            exc_info=True,
        )
        return (
            jsonify(
                status="error", message=f"Server error during pre-check: {e_pre_check}"
            ),
            500,
        )

    def install_world_thread_target(s_name: str, world_f_path: str):
        logger.info(
            f"Thread started for installing world '{os.path.basename(world_f_path)}' to server '{s_name}'."
        )
        try:
            thread_result = world_api.import_world(s_name, world_f_path)
            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Install World '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Install World '{s_name}': Failed. {thread_result.get('message')}"
                )
        except BSMError as e_thread:
            logger.error(
                f"Thread for Install World '{s_name}': Application error. {e_thread}",
                exc_info=True,
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Install World '{s_name}': Unexpected error. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(
        target=install_world_thread_target, args=(server_name, full_world_file_path)
    )
    thread.start()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"World install from '{selected_filename}' for server '{server_name}' initiated in background.",
            }
        ),
        202,
    )


@content_bp.route("/api/server/<string:server_name>/world/export", methods=["POST"])
@auth_required
def export_world_api_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: World export requested for '{server_name}' by user '{identity}'."
    )

    def export_world_thread_target(s_name: str):
        logger.info(f"Thread started for exporting world from server '{s_name}'.")
        try:
            thread_result = world_api.export_world(s_name)
            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Export World '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Export World '{s_name}': Failed. {thread_result.get('message')}"
                )
        except BSMError as e_thread:
            logger.error(
                f"Thread for Export World '{s_name}': Application error. {e_thread}",
                exc_info=True,
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Export World '{s_name}': Unexpected error. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(target=export_world_thread_target, args=(server_name,))
    thread.start()
    return (
        jsonify(
            {
                "status": "success",
                "message": f"World export for server '{server_name}' initiated in background.",
            }
        ),
        202,
    )


@content_bp.route("/api/server/<string:server_name>/world/reset", methods=["DELETE"])
@auth_required
def reset_world_api_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: World reset requested for '{server_name}' by user '{identity}'.")

    def reset_world_thread_target(s_name: str):
        logger.info(f"Thread started for resetting world for server '{s_name}'.")
        try:
            thread_result = world_api.reset_world(s_name)
            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Reset World '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Reset World '{s_name}': Failed. {thread_result.get('message')}"
                )
        except BSMError as e_thread:
            logger.warning(
                f"Thread for Reset World '{s_name}': Application error. {e_thread}",
                exc_info=True,
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Reset World '{s_name}': Unexpected error. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(target=reset_world_thread_target, args=(server_name,))
    thread.start()
    return (
        jsonify(
            {
                "status": "success",
                "message": f"World reset for server '{server_name}' initiated in background.",
            }
        ),
        202,
    )


@content_bp.route("/api/server/<string:server_name>/addon/install", methods=["POST"])
@auth_required
def install_addon_api_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Addon install requested for '{server_name}' by user '{identity}'."
    )
    data = request.get_json()
    if not data or "filename" not in data:
        return (
            jsonify(
                status="error",
                message="Invalid or missing JSON body with 'filename' key.",
            ),
            400,
        )
    selected_filename = data["filename"]
    try:
        content_base_dir = os.path.join(settings.get("paths.content"), "addons")
        full_addon_file_path = os.path.normpath(
            os.path.join(content_base_dir, selected_filename)
        )
        if not os.path.abspath(full_addon_file_path).startswith(
            os.path.abspath(content_base_dir)
        ):
            return (
                jsonify(
                    status="error", message="Invalid file path (security check failed)."
                ),
                400,
            )
        if not os.path.isfile(full_addon_file_path):
            return (
                jsonify(
                    status="error",
                    message=f"Addon file '{selected_filename}' not found for import.",
                ),
                404,
            )
    except Exception as e_pre_check:
        logger.error(
            f"API Install Addon '{server_name}': Pre-check error: {e_pre_check}",
            exc_info=True,
        )
        return (
            jsonify(
                status="error", message=f"Server error during pre-check: {e_pre_check}"
            ),
            500,
        )

    def install_addon_thread_target(s_name: str, addon_f_path: str):
        logger.info(
            f"Thread started for installing addon '{os.path.basename(addon_f_path)}' to server '{s_name}'."
        )
        try:
            thread_result = addon_api.import_addon(s_name, addon_f_path)
            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Install Addon '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Install Addon '{s_name}': Failed. {thread_result.get('message')}"
                )
        except BSMError as e_thread:
            logger.error(
                f"Thread for Install Addon '{s_name}': Application error. {e_thread}",
                exc_info=True,
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Install Addon '{s_name}': Unexpected error. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(
        target=install_addon_thread_target, args=(server_name, full_addon_file_path)
    )
    thread.start()
    return (
        jsonify(
            {
                "status": "success",
                "message": f"Addon install from '{selected_filename}' for server '{server_name}' initiated in background.",
            }
        ),
        202,
    )

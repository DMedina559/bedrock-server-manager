# bedrock_server_manager/web/routes/backup_restore_routes.py
"""
Flask Blueprint handling web routes and API endpoints for server backup
and restore operations.
"""

import os
import logging
import threading
from typing import Dict, Any, Tuple, Optional

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

from bedrock_server_manager.api import backup_restore as backup_restore_api
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
)

logger = logging.getLogger(__name__)

backup_restore_bp = Blueprint(
    "backup_restore_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)

# --- HTML Routes ---


@backup_restore_bp.route("/server/<string:server_name>/backup", methods=["GET"])
@auth_required
def backup_menu_route(server_name: str) -> Response:
    identity = get_current_identity()
    logger.info(f"User '{identity}' accessed backup menu for server '{server_name}'.")
    return render_template(
        "backup_menu.html",
        server_name=server_name,
    )


@backup_restore_bp.route("/server/<string:server_name>/backup/select", methods=["GET"])
@auth_required
def backup_config_select_route(server_name: str) -> Response:
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' accessed config backup selection page for server '{server_name}'."
    )
    return render_template(
        "backup_config_options.html",
        server_name=server_name,
    )


@backup_restore_bp.route("/server/<string:server_name>/restore", methods=["GET"])
@auth_required
def restore_menu_route(server_name: str) -> Response:
    identity = get_current_identity()
    logger.info(f"User '{identity}' accessed restore menu for server '{server_name}'.")
    return render_template(
        "restore_menu.html",
        server_name=server_name,
    )


@backup_restore_bp.route(
    "/server/<string:server_name>/restore/<string:restore_type>/select_file",
    methods=["GET"],
)
@auth_required
def show_select_backup_file_page_route(server_name: str, restore_type: str) -> Response:
    identity = get_current_identity()
    logger.info(
        f"User '{identity}' viewing selection page for '{restore_type}' backups for server '{server_name}'."
    )
    valid_types = ["world", "properties", "allowlist", "permissions"]
    if restore_type.lower() not in valid_types:
        flash(f"Invalid restore type '{restore_type}' specified.", "warning")
        return redirect(url_for(".restore_menu_route", server_name=server_name))
    try:
        api_result = backup_restore_api.list_backup_files(server_name, restore_type)
        if api_result.get("status") == "success":
            full_paths = api_result.get("backups", [])
            if not full_paths:
                flash(
                    f"No '{restore_type}' backups found for server '{server_name}'.",
                    "info",
                )
                return redirect(url_for(".restore_menu_route", server_name=server_name))
            backups_for_template = [
                {"name": os.path.basename(p), "path": os.path.basename(p)}
                for p in full_paths
            ]
            return render_template(
                "restore_select_backup.html",
                server_name=server_name,
                restore_type=restore_type,
                backups=backups_for_template,
            )
        else:
            error_msg = api_result.get("message", "Unknown error listing backups.")
            logger.error(
                f"Error listing backups for '{server_name}' ({restore_type}): {error_msg}"
            )
            flash(f"Error listing backups: {error_msg}", "error")
            return redirect(url_for(".restore_menu_route", server_name=server_name))
    except Exception as e:
        logger.error(
            f"Unexpected error on backup selection page for '{server_name}' ({restore_type}): {e}",
            exc_info=True,
        )
        flash("An unexpected error occurred while preparing backup selection.", "error")
        return redirect(url_for(".restore_menu_route", server_name=server_name))


# --- API Routes ---


@backup_restore_bp.route(
    "/api/server/<string:server_name>/restore/select_backup_type", methods=["POST"]
)
@auth_required
def handle_restore_select_backup_api(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity()
    data = request.get_json()
    if not data or not (restore_type := data.get("restore_type", "").lower()):
        logger.warning(
            f"API: Invalid/missing restore_type from '{identity}' for server '{server_name}'. Data: {data}"
        )
        return (
            jsonify(
                status="error",
                message="Missing or invalid 'restore_type' in request body.",
            ),
            400,
        )
    logger.info(
        f"API: User '{identity}' initiated selection of restore_type '{restore_type}' for server '{server_name}'."
    )
    valid_types = ["world", "properties", "allowlist", "permissions"]
    if restore_type not in valid_types:
        logger.warning(
            f"API: Invalid restore_type '{restore_type}' selected by '{identity}' for '{server_name}'."
        )
        return (
            jsonify(
                status="error",
                message=f"Invalid restore type '{restore_type}' selected.",
            ),
            400,
        )
    try:
        redirect_page_url = url_for(
            ".show_select_backup_file_page_route",
            server_name=server_name,
            restore_type=restore_type,
        )
        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Proceed to select {restore_type} backup.",
                    "redirect_url": redirect_page_url,
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(
            f"API: Unexpected error during restore type selection for '{server_name}' by '{identity}': {e}",
            exc_info=True,
        )
        return (
            jsonify(status="error", message="An unexpected server error occurred."),
            500,
        )


@backup_restore_bp.route(
    "/api/server/<string:server_name>/backups/prune", methods=["POST"]
)
@auth_required
def prune_backups_api_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request to prune backups for server '{server_name}' by user '{identity}'."
    )

    def prune_backups_thread_target(s_name: str):
        logger.info(f"Thread started for pruning backups for server '{s_name}'.")
        try:
            thread_result = backup_restore_api.prune_old_backups(s_name)
            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Prune Backups '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Prune Backups '{s_name}': Failed. {thread_result.get('message')}"
                )
        except BSMError as e_thread:
            logger.warning(
                f"Thread for Prune Backups '{s_name}': Application error. {e_thread}"
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Prune Backups '{s_name}': Unexpected error in thread. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(target=prune_backups_thread_target, args=(server_name,))
    thread.start()
    return (
        jsonify(
            {
                "status": "success",
                "message": f"Backup pruning for server '{server_name}' initiated in background.",
            }
        ),
        202,
    )


@backup_restore_bp.route(
    "/api/server/<string:server_name>/backup/list/<string:backup_type>", methods=["GET"]
)
@auth_required
def list_server_backups_route(
    server_name: str, backup_type: str
) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Request to list '{backup_type}' backups for server '{server_name}' by user '{identity}'."
    )
    result_dict: Dict[str, Any]
    status_code: int
    try:
        api_result = backup_restore_api.list_backup_files(
            server_name=server_name, backup_type=backup_type
        )
        if api_result.get("status") == "success":
            full_paths = api_result.get("backups", [])
            basenames = [os.path.basename(p) for p in full_paths]
            result_dict = {"status": "success", "backups": basenames}
            status_code = 200
        else:
            result_dict = api_result
            status_code = 400
            logger.warning(
                f"API List Backups: Handler for '{server_name}' returned error: {result_dict.get('message')}"
            )
    except BSMError as e:
        status_code = 400 if isinstance(e, UserInputError) else 500
        result_dict = {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            f"API List Backups: Unexpected critical error for '{server_name}': {e}",
            exc_info=True,
        )
        result_dict = {
            "status": "error",
            "message": "A critical server error occurred.",
        }
        status_code = 500
    return jsonify(result_dict), status_code


@backup_restore_bp.route(
    "/api/server/<string:server_name>/backup/action", methods=["POST"]
)
@auth_required
def backup_action_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Backup action requested for server '{server_name}' by user '{identity}'."
    )
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify(status="error", message="Invalid or missing JSON body."), 400
    backup_type = data.get("backup_type", "").lower()
    file_to_backup = data.get("file_to_backup")
    valid_types = ["world", "config", "all"]
    if backup_type not in valid_types:
        return (
            jsonify(
                status="error",
                message=f"Invalid 'backup_type'. Must be one of: {valid_types}.",
            ),
            400,
        )
    if backup_type == "config" and (
        not file_to_backup or not isinstance(file_to_backup, str)
    ):
        return (
            jsonify(
                status="error",
                message="Missing or invalid 'file_to_backup' for config backup.",
            ),
            400,
        )

    def backup_action_thread_target(
        s_name: str, b_type: str, f_to_backup: Optional[str]
    ):
        logger.info(
            f"Thread started for backup action '{b_type}' for server '{s_name}'."
        )
        try:
            if b_type == "world":
                thread_result = backup_restore_api.backup_world(s_name)
            elif b_type == "config":
                if not f_to_backup:
                    return
                thread_result = backup_restore_api.backup_config_file(
                    s_name, f_to_backup.strip()
                )
            elif b_type == "all":
                thread_result = backup_restore_api.backup_all(s_name)
            else:
                return

            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Backup Action '{b_type}' for '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Backup Action '{b_type}' for '{s_name}': Failed. {thread_result.get('message')}"
                )
        except BSMError as e_thread:
            logger.error(
                f"Thread for Backup Action '{b_type}' for '{s_name}': BSMError. {e_thread}",
                exc_info=True,
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Backup Action '{b_type}' for '{s_name}': Unexpected error. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(
        target=backup_action_thread_target,
        args=(server_name, backup_type, file_to_backup),
    )
    thread.start()
    return (
        jsonify(
            status="success",
            message=f"Backup action '{backup_type}' for server '{server_name}' initiated.",
        ),
        202,
    )


@backup_restore_bp.route(
    "/api/server/<string:server_name>/restore/action", methods=["POST"]
)
@auth_required
def restore_action_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Restore action requested for server '{server_name}' by user '{identity}'."
    )
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify(status="error", message="Invalid or missing JSON body."), 400
    restore_type = data.get("restore_type", "").lower()
    relative_backup_file = data.get("backup_file")
    valid_types = ["world", "properties", "allowlist", "permissions", "all"]
    if restore_type not in valid_types:
        return jsonify(status="error", message="Invalid 'restore_type' specified."), 400
    if restore_type != "all" and (
        not relative_backup_file or not isinstance(relative_backup_file, str)
    ):
        return (
            jsonify(
                status="error",
                message="Missing or invalid 'backup_file' for this restore type.",
            ),
            400,
        )

    def restore_action_thread_target(
        s_name: str, r_type: str, rel_backup_file: Optional[str]
    ):
        logger.info(
            f"Thread started for restore action '{r_type}' for server '{s_name}'."
        )
        try:
            thread_result: Dict[str, Any]
            if r_type == "all":
                thread_result = backup_restore_api.restore_all(s_name)
            else:
                if not rel_backup_file:
                    return
                backup_base_dir = settings.get("paths.backups")
                if not backup_base_dir:
                    raise BSMError("BACKUP_DIR not configured.")
                server_backup_dir = os.path.join(backup_base_dir, s_name)
                full_backup_path = os.path.normpath(
                    os.path.join(server_backup_dir, rel_backup_file)
                )
                if not os.path.abspath(full_backup_path).startswith(
                    os.path.abspath(server_backup_dir)
                ):
                    logger.error(
                        f"Thread Restore '{s_name}': Security violation - Invalid backup path."
                    )
                    return
                if not os.path.isfile(full_backup_path):
                    logger.error(
                        f"Thread Restore '{s_name}': Backup file not found: {rel_backup_file}"
                    )
                    return
                if r_type == "world":
                    thread_result = backup_restore_api.restore_world(
                        s_name, full_backup_path
                    )
                else:
                    thread_result = backup_restore_api.restore_config_file(
                        s_name, full_backup_path
                    )

            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Restore Action '{r_type}' for '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Restore Action '{r_type}' for '{s_name}': Failed. {thread_result.get('message')}"
                )
        except BSMError as e_thread:
            logger.error(
                f"Thread for Restore Action '{r_type}' for '{s_name}': BSMError. {e_thread}",
                exc_info=True,
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Restore Action '{r_type}' for '{s_name}': Unexpected error. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(
        target=restore_action_thread_target,
        args=(server_name, restore_type, relative_backup_file),
    )
    thread.start()
    return (
        jsonify(
            status="success",
            message=f"Restore action '{restore_type}' for server '{server_name}' initiated.",
        ),
        202,
    )

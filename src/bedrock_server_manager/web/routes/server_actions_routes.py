# bedrock_server_manager/web/routes/action_routes.py
"""
Flask Blueprint defining API endpoints for controlling Bedrock server instances.
"""

import logging
import threading
from typing import Tuple, Dict, Any

# Third-party imports
from flask import Blueprint, request, jsonify, Response

# Local imports
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)
from bedrock_server_manager.api import server as server_api, server_install_config
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
    InvalidServerNameError,
    AppFileNotFoundError,
    ServerNotRunningError,
    BlockedCommandError,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
server_actions_bp = Blueprint("action_routes", __name__)


# --- API Route: Start Server ---
@server_actions_bp.route("/api/server/<string:server_name>/start", methods=["POST"])
@auth_required
def start_server_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to start a specific Bedrock server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Start server request for '{server_name}' by user '{identity}'.")

    def start_server_thread_target(s_name: str):
        logger.info(f"Thread started for starting server '{s_name}'.")
        try:
            # This call can have minor blocking due to plugin after_server_start hook
            thread_result = server_api.start_server(s_name, mode="detached")
            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Start Server '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Start Server '{s_name}': Failed. {thread_result.get('message')}"
                )
        except UserInputError as e_thread:
            logger.warning(
                f"Thread for Start Server '{s_name}': Input error. {e_thread}"
            )
        except BSMError as e_thread:
            logger.error(
                f"Thread for Start Server '{s_name}': Application error. {e_thread}"
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Start Server '{s_name}': Unexpected error in thread. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(target=start_server_thread_target, args=(server_name,))
    thread.start()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Start operation for server '{server_name}' initiated in background.",
            }
        ),
        202,
    )


# --- API Route: Stop Server ---
@server_actions_bp.route("/api/server/<string:server_name>/stop", methods=["POST"])
@auth_required
def stop_server_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to stop a specific running Bedrock server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Stop server request for '{server_name}' by user '{identity}'.")

    def stop_server_thread_target(s_name: str):
        logger.info(f"Thread started for stopping server '{s_name}'.")
        try:
            # This call can block due to sleeps in server.stop() and plugin hooks
            thread_result = server_api.stop_server(s_name)
            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Stop Server '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Stop Server '{s_name}': Failed. {thread_result.get('message')}"
                )
        except UserInputError as e_thread:
            logger.warning(
                f"Thread for Stop Server '{s_name}': Input error. {e_thread}"
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Stop Server '{s_name}': Unexpected error in thread. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(target=stop_server_thread_target, args=(server_name,))
    thread.start()

    # Return immediately to the client
    return (
        jsonify(
            {
                "status": "success",
                "message": f"Stop operation for server '{server_name}' initiated in background.",
            }
        ),
        202,
    )


# --- API Route: Restart Server ---
@server_actions_bp.route("/api/server/<string:server_name>/restart", methods=["POST"])
@auth_required
def restart_server_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to restart a specific Bedrock server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Restart server request for '{server_name}' by user '{identity}'."
    )

    def restart_server_thread_target(s_name: str):
        logger.info(f"Thread started for restarting server '{s_name}'.")
        try:
            # This call can block due to stop_server and start_server (plugin sleeps)
            thread_result = server_api.restart_server(s_name)
            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Restart Server '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Restart Server '{s_name}': Failed. {thread_result.get('message')}"
                )
        except UserInputError as e_thread:
            logger.warning(
                f"Thread for Restart Server '{s_name}': Input error. {e_thread}"
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Restart Server '{s_name}': Unexpected error in thread. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(target=restart_server_thread_target, args=(server_name,))
    thread.start()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Restart operation for server '{server_name}' initiated in background.",
            }
        ),
        202,
    )


# --- API Route: Send Command ---
@server_actions_bp.route(
    "/api/server/<string:server_name>/send_command", methods=["POST"]
)
@auth_required
def send_command_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to send a command to a running Bedrock server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Send command request for '{server_name}' by user '{identity}'.")

    data = request.get_json()
    if not data or "command" not in data or not data["command"].strip():
        return (
            jsonify(
                status="error", message="Request must contain a non-empty 'command'."
            ),
            400,
        )

    command = data["command"].strip()
    result: Dict[str, Any]
    status_code: int

    try:
        result = server_api.send_command(server_name, command)
        status_code = 200
        logger.info(f"API Send Command '{server_name}': Succeeded.")

    except BlockedCommandError as e:
        status_code = 403  # Forbidden
        result = {"status": "error", "message": str(e)}
        logger.warning(
            f"API Send Command '{server_name}': Blocked command attempt. {e}"
        )
    except UserInputError as e:
        status_code = 400
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Send Command '{server_name}': Input error. {e}")
    except AppFileNotFoundError as e:
        status_code = 404
        result = {"status": "error", "message": str(e)}
        logger.error(f"API Send Command '{server_name}': Server not found. {e}")
    except ServerNotRunningError as e:
        status_code = 409  # Conflict - server is in the wrong state
        result = {"status": "error", "message": str(e)}
        logger.warning(f"API Send Command '{server_name}': Server not running. {e}")
    except Exception as e:
        status_code = 500
        result = {
            "status": "error",
            "message": "An unexpected error occurred while sending the command.",
        }
        logger.error(
            f"API Send Command '{server_name}': Unexpected error in route. {e}",
            exc_info=True,
        )

    return jsonify(result), status_code


# --- API Route: Update Server ---
@server_actions_bp.route("/api/server/<string:server_name>/update", methods=["POST"])
@auth_required
def update_server_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to trigger an update for a specific Bedrock server instance."""
    identity = get_current_identity() or "Unknown"
    logger.info(f"API: Update server request for '{server_name}' by user '{identity}'.")

    def update_server_thread_target(s_name: str):
        logger.info(f"Thread started for updating server '{s_name}'.")
        try:
            # This call can block due to stop_server and start_server (plugin sleeps)
            # within the update_server logic.
            thread_result = server_install_config.update_server(s_name)
            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Update Server '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Update Server '{s_name}': Failed. {thread_result.get('message')}"
                )
        except UserInputError as e_thread:
            logger.warning(
                f"Thread for Update Server '{s_name}': Input error. {e_thread}"
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Update Server '{s_name}': Unexpected error in thread. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(target=update_server_thread_target, args=(server_name,))
    thread.start()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Update operation for server '{server_name}' initiated in background.",
            }
        ),
        202,
    )


# --- API Route: Delete Server ---
@server_actions_bp.route("/api/server/<string:server_name>/delete", methods=["DELETE"])
@auth_required
def delete_server_route(server_name: str) -> Tuple[Response, int]:
    """API endpoint to delete a specific server's data."""
    identity = get_current_identity() or "Unknown"
    logger.warning(
        f"API: DELETE server request for '{server_name}' by user '{identity}'."
    )

    def delete_server_thread_target(s_name: str):
        logger.info(f"Thread started for deleting server '{s_name}'.")
        try:
            # This call can block if it needs to stop the server first.
            thread_result = server_api.delete_server_data(s_name)
            if thread_result.get("status") == "success":
                logger.info(
                    f"Thread for Delete Server '{s_name}': Succeeded. {thread_result.get('message')}"
                )
            else:
                logger.error(
                    f"Thread for Delete Server '{s_name}': Failed. {thread_result.get('message')}"
                )
        except UserInputError as e_thread:
            logger.warning(
                f"Thread for Delete Server '{s_name}': Input error. {e_thread}"
            )
        except Exception as e_thread:
            logger.error(
                f"Thread for Delete Server '{s_name}': Unexpected error in thread. {e_thread}",
                exc_info=True,
            )

    thread = threading.Thread(target=delete_server_thread_target, args=(server_name,))
    thread.start()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Delete operation for server '{server_name}' initiated in background.",
            }
        ),
        202,
    )

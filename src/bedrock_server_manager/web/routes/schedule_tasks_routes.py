# bedrock_server_manager/web/routes/schedule_tasks_routes.py
"""
Flask Blueprint handling web routes and API endpoints for managing scheduled tasks
(Linux cron jobs and Windows Task Scheduler tasks) related to server operations.
"""

import logging
from typing import Dict, Any, Tuple

# Third-party imports
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

# Local imports
from bedrock_server_manager.api import task_scheduler as api_task_scheduler
from bedrock_server_manager.error import (
    BSMError,
)
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.config.const import EXPATH

from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
schedule_tasks_bp = Blueprint(
    "schedule_tasks_routes",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


# --- HTML Routes ---
@schedule_tasks_bp.route("/server/<string:server_name>/cron_scheduler", methods=["GET"])
@auth_required
def schedule_tasks_route(server_name: str) -> Response:
    """Displays the Linux cron job scheduling management page for a specific server."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed Linux cron schedule page for server '{server_name}'."
    )

    if not isinstance(
        api_task_scheduler.scheduler, api_task_scheduler.core_task.LinuxTaskScheduler
    ):
        msg = "Cron job scheduling is only available on supported Linux systems."
        flash(msg, "warning")
        return redirect(url_for("main_routes.index"))

    table_data = []
    try:
        cron_jobs_response = api_task_scheduler.get_server_cron_jobs(server_name)
        if cron_jobs_response.get("status") == "error":
            flash(
                f"Error retrieving cron jobs: {cron_jobs_response.get('message')}",
                "error",
            )
        else:
            cron_jobs_list = cron_jobs_response.get("cron_jobs", [])
            if cron_jobs_list:
                table_response = api_task_scheduler.get_cron_jobs_table(cron_jobs_list)
                if table_response.get("status") == "error":
                    flash(
                        f"Error formatting cron jobs: {table_response.get('message')}",
                        "error",
                    )
                else:
                    table_data = table_response.get("table_data", [])
    except Exception as e:
        flash("An unexpected error occurred while loading scheduled tasks.", "error")
        logger.error(
            f"Unexpected error on Linux scheduler page for '{server_name}': {e}",
            exc_info=True,
        )

    return render_template(
        "schedule_tasks.html",
        server_name=server_name,
        table_data=table_data,
        EXPATH=EXPATH,
    )


@schedule_tasks_bp.route("/server/<string:server_name>/task_scheduler", methods=["GET"])
@auth_required
def schedule_tasks_windows_route(server_name: str) -> Response:
    """Displays the Windows Task Scheduler management page for a specific server."""
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed Windows Task Scheduler page for '{server_name}'."
    )

    if not isinstance(
        api_task_scheduler.scheduler, api_task_scheduler.core_task.WindowsTaskScheduler
    ):
        msg = "Windows Task Scheduling is only available on supported Windows systems."
        flash(msg, "warning")
        return redirect(url_for("main_routes.index"))

    tasks = []
    try:
        config_dir = getattr(settings, "config_dir", None)
        if not config_dir:
            raise BSMError("Base configuration directory not set.")

        task_names_resp = api_task_scheduler.get_server_task_names(
            server_name, config_dir
        )
        if task_names_resp.get("status") == "error":
            flash(
                f"Error retrieving task files: {task_names_resp.get('message')}",
                "error",
            )
        else:
            task_names = [t[0] for t in task_names_resp.get("task_names", [])]
            if task_names:
                task_info_resp = api_task_scheduler.get_windows_task_info(task_names)
                if task_info_resp.get("status") == "error":
                    flash(
                        f"Error retrieving task details: {task_info_resp.get('message')}",
                        "error",
                    )
                else:
                    tasks = task_info_resp.get("task_info", [])
    except Exception as e:
        flash("An unexpected error occurred while loading scheduled tasks.", "error")
        logger.error(
            f"Error on Windows scheduler page for '{server_name}': {e}", exc_info=True
        )

    return render_template(
        "schedule_tasks_windows.html", server_name=server_name, tasks=tasks
    )


# ------


# --- API Endpoints ---
@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/cron_scheduler/add", methods=["POST"]
)
@auth_required
def add_cron_job_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Add cron job request by '{identity}' (context: '{server_name}')."
    )
    if not isinstance(
        api_task_scheduler.scheduler, api_task_scheduler.core_task.LinuxTaskScheduler
    ):
        return (
            jsonify(status="error", message="Cron jobs are only supported on Linux."),
            403,
        )
    data = request.get_json(silent=True)
    if not data or not (cron_string := data.get("new_cron_job")):
        return (
            jsonify(
                status="error", message="Cron job string ('new_cron_job') is required."
            ),
            400,
        )
    try:
        result = api_task_scheduler.add_cron_job(cron_string)
        if result.get("status") == "success":
            return jsonify(result), 201
        return jsonify(result), 500
    except BSMError as e:
        return jsonify(status="error", message=str(e)), 400
    except Exception as e:
        logger.error(f"API Add Cron Job: Unexpected error: {e}", exc_info=True)
        return jsonify(status="error", message="An unexpected error occurred."), 500


@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/cron_scheduler/modify", methods=["POST"]
)
@auth_required
def modify_cron_job_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Modify cron job request by '{identity}' (context: '{server_name}')."
    )
    if not isinstance(
        api_task_scheduler.scheduler, api_task_scheduler.core_task.LinuxTaskScheduler
    ):
        return (
            jsonify(status="error", message="Cron jobs are only supported on Linux."),
            403,
        )
    data = request.get_json(silent=True)
    if (
        not data
        or not (old_cron := data.get("old_cron_job"))
        or not (new_cron := data.get("new_cron_job"))
    ):
        return (
            jsonify(
                status="error",
                message="'old_cron_job' and 'new_cron_job' are required.",
            ),
            400,
        )
    try:
        result = api_task_scheduler.modify_cron_job(old_cron, new_cron)
        if result.get("status") == "success":
            return jsonify(result), 200
        if "not found" in (result.get("message") or "").lower():
            return jsonify(result), 404
        return jsonify(result), 500
    except BSMError as e:
        status_code = 404 if "not found" in str(e).lower() else 400
        return jsonify(status="error", message=str(e)), status_code
    except Exception as e:
        logger.error(f"API Modify Cron Job: Unexpected error: {e}", exc_info=True)
        return jsonify(status="error", message="An unexpected error occurred."), 500


@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/cron_scheduler/delete", methods=["DELETE"]
)
@auth_required
def delete_cron_job_route(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Delete cron job request by '{identity}' (context: '{server_name}')."
    )
    if not isinstance(
        api_task_scheduler.scheduler, api_task_scheduler.core_task.LinuxTaskScheduler
    ):
        return (
            jsonify(status="error", message="Cron jobs are only supported on Linux."),
            403,
        )
    cron_string = request.args.get("cron_string")
    if not cron_string:
        return (
            jsonify(
                status="error", message="'cron_string' query parameter is required."
            ),
            400,
        )
    try:
        result = api_task_scheduler.delete_cron_job(cron_string)
        if result.get("status") == "success":
            return jsonify(result), 200
        return jsonify(result), 500
    except BSMError as e:
        return jsonify(status="error", message=str(e)), 400
    except Exception as e:
        logger.error(f"API Delete Cron Job: Unexpected error: {e}", exc_info=True)
        return jsonify(status="error", message="An unexpected error occurred."), 500


@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/task_scheduler/add", methods=["POST"]
)
@auth_required
def add_windows_task_api(server_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"API: Add Windows task request by '{identity}' for server '{server_name}'."
    )
    if not isinstance(
        api_task_scheduler.scheduler, api_task_scheduler.core_task.WindowsTaskScheduler
    ):
        return (
            jsonify(
                status="error", message="Windows tasks are only supported on Windows."
            ),
            403,
        )
    data = request.get_json(silent=True)
    if (
        not data
        or not (command := data.get("command"))
        or not (triggers := data.get("triggers"))
    ):
        return (
            jsonify(status="error", message="'command' and 'triggers' are required."),
            400,
        )
    valid_commands = [
        "update-server",
        "backup-all",
        "start-server",
        "stop-server",
        "restart-server",
        "scan-players",
    ]
    if command not in valid_commands:
        return (
            jsonify(
                status="error",
                message=f"Invalid command. Must be one of: {valid_commands}.",
            ),
            400,
        )
    try:
        config_dir = getattr(settings, "config_dir", None)
        if not config_dir:
            raise BSMError("Base configuration directory not set.")
        command_args = f"--server {server_name}" if command != "scan-players" else ""
        task_name = api_task_scheduler.create_task_name(server_name, command)
        result = api_task_scheduler.create_windows_task(
            server_name, command, command_args, task_name, triggers, config_dir
        )
        if result.get("status") == "success":
            result["created_task_name"] = task_name
            return jsonify(result), 201
        return jsonify(result), 500
    except BSMError as e:
        return jsonify(status="error", message=str(e)), 500
    except Exception as e:
        logger.error(f"API Add Windows Task: Unexpected error: {e}", exc_info=True)
        return jsonify(status="error", message="An unexpected error occurred."), 500


@schedule_tasks_bp.route(
    "/api/server/<string:server_name>/task_scheduler/task/<path:task_name>",
    methods=["PUT", "DELETE"],
)
@auth_required
def manage_windows_task_api(server_name: str, task_name: str) -> Tuple[Response, int]:
    identity = get_current_identity() or "Unknown"
    if not isinstance(
        api_task_scheduler.scheduler, api_task_scheduler.core_task.WindowsTaskScheduler
    ):
        return (
            jsonify(
                status="error", message="Windows tasks are only supported on Windows."
            ),
            403,
        )
    try:
        config_dir = getattr(settings, "config_dir", None)
        if not config_dir:
            raise BSMError("Base configuration directory not set.")
        task_list = api_task_scheduler.get_server_task_names(
            server_name, config_dir
        ).get("task_names", [])
        task_file_path = next(
            (path for name, path in task_list if name.lstrip("\\") == task_name), None
        )

        if request.method == "PUT":
            logger.info(
                f"API: Modify Windows task '{task_name}' request by '{identity}'."
            )
            data = request.get_json(silent=True)
            if (
                not data
                or not (command := data.get("command"))
                or not (triggers := data.get("triggers"))
            ):
                return (
                    jsonify(
                        status="error", message="'command' and 'triggers' are required."
                    ),
                    400,
                )
            command_args = (
                f"--server {server_name}" if command != "scan-players" else ""
            )
            new_task_name = api_task_scheduler.create_task_name(server_name, command)
            result = api_task_scheduler.modify_windows_task(
                task_name,
                server_name,
                command,
                command_args,
                new_task_name,
                triggers,
                config_dir,
            )
            if result.get("status") == "success":
                result["new_task_name"] = new_task_name
                return jsonify(result), 200
            return jsonify(result), 500
        elif request.method == "DELETE":
            logger.info(
                f"API: Delete Windows task '{task_name}' request by '{identity}'."
            )
            if not task_file_path:
                return (
                    jsonify(
                        status="error",
                        message=f"Task configuration file for '{task_name}' not found.",
                    ),
                    404,
                )
            result = api_task_scheduler.delete_windows_task(task_name, task_file_path)
            if result.get("status") == "success":
                return jsonify(result), 200
            return jsonify(result), 500
    except BSMError as e:
        return jsonify(status="error", message=str(e)), 500
    except Exception as e:
        logger.error(
            f"API Manage Windows Task '{task_name}': Unexpected error: {e}",
            exc_info=True,
        )
        return jsonify(status="error", message="An unexpected error occurred."), 500
    return jsonify(status="error", message="Invalid request method."), 405

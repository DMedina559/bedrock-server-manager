# bedrock_server_manager/web/routes/main_routes.py
"""
Flask Blueprint for the main user interface routes of the application,
primarily the server dashboard.
"""

import platform
import logging

# Third-party imports
from flask import Blueprint, render_template, redirect, url_for, flash, Response

# Local imports
from bedrock_server_manager.web.utils.auth_decorators import (
    auth_required,
    get_current_identity,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
main_bp = Blueprint(
    "main_routes", __name__, template_folder="../templates", static_folder="../static"
)


# --- Route: Main Dashboard ---
@main_bp.route("/")
@auth_required
def index() -> Response:
    """
    Renders the main dashboard page.

    Displays a list of all detected servers, their status, version, and world icon (if available).
    """
    logger.info("Dashboard route '/' accessed. Rendering server list.")

    return render_template("index.html")


# --- Route: Redirect to OS-Specific Scheduler Page ---
@main_bp.route("/server/<string:server_name>/scheduler")
@auth_required
def task_scheduler_route(server_name: str) -> Response:
    """
    Redirects the user to the appropriate task scheduling page based on the host OS.
    """
    current_os = platform.system()
    identity = get_current_identity() or "Unknown"
    logger.info(
        f"User '{identity}' accessed scheduler route for server '{server_name}'. OS detected: {current_os}."
    )

    if current_os == "Linux":
        return redirect(
            url_for(
                "schedule_tasks_routes.schedule_tasks_route", server_name=server_name
            )
        )
    elif current_os == "Windows":
        return redirect(
            url_for(
                "schedule_tasks_routes.schedule_tasks_windows_route",
                server_name=server_name,
            )
        )
    else:
        flash(
            f"Task scheduling is not supported on this operating system ({current_os}).",
            "warning",
        )
        return redirect(url_for(".index"))


@main_bp.route("/server/<string:server_name>/monitor")
@auth_required
def monitor_server_route(server_name: str) -> Response:
    """Renders the server monitoring page for a specific server."""
    identity = get_current_identity()
    logger.info(f"User '{identity}' accessed monitor page for server '{server_name}'.")
    return render_template("monitor.html", server_name=server_name)

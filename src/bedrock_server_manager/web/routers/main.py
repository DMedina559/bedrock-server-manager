# bedrock_server_manager/web/routers/main.py
"""
FastAPI router for the main web application pages and core navigation.

This module defines routes for essential parts of the user interface, including:
- The main dashboard (index page) which typically lists servers.
- A route to redirect users to the OS-specific task scheduler page.
- The server-specific monitoring page.

Authentication is required for most routes, handled via FastAPI dependencies.
Templates are rendered using Jinja2.
"""
import platform
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Path
from fastapi.responses import HTMLResponse, RedirectResponse

from bedrock_server_manager.web.templating import templates
from bedrock_server_manager.web.auth_utils import (
    get_current_user,
    get_current_user_optional,
)
from ..dependencies import validate_server_exists

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Route: Main Dashboard ---
@router.get("/", response_class=HTMLResponse, name="index", include_in_schema=False)
async def index(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """
    Renders the main dashboard page (index).

    This page typically displays a list of manageable Bedrock servers.
    Authentication is required; if the user is not authenticated, they are
    redirected to the login page.

    Args:
        request (Request): The incoming FastAPI request object.
        current_user (Optional[Dict[str, Any]]): The authenticated user object,
                                                 injected by `get_current_user_optional`.
                                                 If None, user is redirected.

    Returns:
        HTMLResponse: Renders the `index.html` template with the current user's
                      information.
        RedirectResponse: If the user is not authenticated, redirects to `/auth/login`.
    """

    if not current_user:

        return RedirectResponse(url="/auth/login", status_code=302)

    logger.info(
        f"Dashboard route '/' accessed by user '{current_user.get('username')}'. Rendering server list."
    )
    return templates.TemplateResponse(
        "index.html", {"request": request, "current_user": current_user}
    )


# --- Route: Redirect to OS-Specific Scheduler Page ---
@router.get(
    "/server/{server_name}/scheduler", name="task_scheduler", include_in_schema=False
)
async def task_scheduler_route(
    server_name: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Redirects to the OS-specific task scheduler page for a given server.

    Detects the current operating system and redirects the user to either the
    Linux cron job page or the Windows Scheduled Tasks page. If the OS is not
    supported, it redirects back to the main dashboard with an error message.

    Args:
        server_name (str): The name of the server for which to access the scheduler.
                           This is a path parameter.
        request (Request): The incoming FastAPI request object.
        current_user (Dict[str, Any]): The authenticated user object, injected by
                                       `get_current_user`.

    Returns:
        RedirectResponse: Redirects to the appropriate scheduler page
                          (`/schedule-tasks/{server_name}/linux` or
                          `/schedule-tasks/{server_name}/windows`) or to the
                          index page with an error message if the OS is unsupported.
    """
    current_os = platform.system()
    username = current_user.get("username", "Unknown")
    logger.info(
        f"User '{username}' accessed scheduler route for server '{server_name}'. OS detected: {current_os}."
    )

    if current_os == "Linux":

        return RedirectResponse(url=f"/schedule-tasks/{server_name}/linux")
    elif current_os == "Windows":
        return RedirectResponse(url=f"/schedule-tasks/{server_name}/windows")
    else:

        redirect_url = request.url_for("index").include_query_params(
            message="Task scheduling is not supported on this operating system."
        )
        return RedirectResponse(url=redirect_url)


@router.get(
    "/server/{server_name}/monitor",
    response_class=HTMLResponse,
    name="monitor_server",
    include_in_schema=False,
)
async def monitor_server_route(
    request: Request,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Renders the server-specific monitoring page.

    This page is intended to display real-time information or logs for the
    specified Bedrock server. Authentication is required.

    Args:
        request (Request): The incoming FastAPI request object.
        server_name (str): The name of the server to monitor, validated by
                           `validate_server_exists`. Injected by FastAPI.
        current_user (Dict[str, Any]): The authenticated user object, injected by
                                       `get_current_user`.

    Returns:
        HTMLResponse: Renders the `monitor.html` template, passing the server name
                      and current user information to the template.
    """
    username = current_user.get("username")
    logger.info(f"User '{username}' accessed monitor page for server '{server_name}'.")
    return templates.TemplateResponse(
        "monitor.html",
        {"request": request, "server_name": server_name, "current_user": current_user},
    )

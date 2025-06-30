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

router = APIRouter(
    tags=["main"],
)


# --- Route: Main Dashboard ---
@router.get("/", response_class=HTMLResponse, name="index")
async def index(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """
    Renders the main dashboard page.
    If user is not authenticated, they will be redirected by get_current_user_optional logic
    or the template can handle the None user.
    For this migration, we'll make it behave like auth_required by using get_current_user.
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
@router.get("/server/{server_name}/scheduler", name="task_scheduler")
async def task_scheduler_route(
    server_name: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
    "/server/{server_name}/monitor", response_class=HTMLResponse, name="monitor_server"
)
async def monitor_server_route(
    request: Request,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):

    username = current_user.get("username")
    logger.info(f"User '{username}' accessed monitor page for server '{server_name}'.")
    return templates.TemplateResponse(
        "monitor.html",
        {"request": request, "server_name": server_name, "current_user": current_user},
    )

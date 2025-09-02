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

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..dependencies import get_templates, get_app_context, validate_server_exists
from ..auth_utils import (
    get_current_user,
    get_current_user_optional,
    get_admin_user,
)
from ..schemas import User
from ...plugins.plugin_manager import PluginManager
from ...context import AppContext

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Route: Main Dashboard ---
@router.get("/", response_class=HTMLResponse, name="index", include_in_schema=False)
async def index(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
    app_context: AppContext = Depends(get_app_context),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Renders the main dashboard page (index).
    """
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=302)

    logger.info(
        f"Dashboard route accessed by user '{current_user.username}'. Rendering server list."
    )

    try:
        plugin_manager: PluginManager = app_context.plugin_manager
        plugin_html_pages = plugin_manager.get_html_render_routes()
    except Exception as e:
        logger.error(f"Error getting plugin HTML pages: {e}", exc_info=True)
        plugin_html_pages = []

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "current_user": current_user,
            "plugin_html_pages": plugin_html_pages,
        },
    )


@router.get(
    "/server/{server_name}/monitor",
    response_class=HTMLResponse,
    name="monitor_server",
    include_in_schema=False,
)
async def monitor_server_route(
    request: Request,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_current_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Renders the server-specific monitoring page.

    This page is intended to display real-time information or logs for the
    specified Bedrock server. Authentication is required.
    """
    username = current_user.username
    logger.info(f"User '{username}' accessed monitor page for server '{server_name}'.")
    return templates.TemplateResponse(
        request,
        "monitor.html",
        {"server_name": server_name, "current_user": current_user},
    )


@router.get(
    "/servers/{server_name}/settings",
    response_class=HTMLResponse,
    name="server_settings_page",
    include_in_schema=False,
)
async def server_settings_page_route(
    request: Request,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_admin_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the HTML page for managing server-specific settings.
    """
    identity = current_user.username
    logger.info(f"User '{identity}' accessed settings page for server '{server_name}'.")
    return templates.TemplateResponse(
        request,
        "server_settings.html",
        {"server_name": server_name, "current_user": current_user},
    )

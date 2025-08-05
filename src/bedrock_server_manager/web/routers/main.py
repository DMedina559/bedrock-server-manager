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

from ..templating import get_templates
from ..auth_utils import (
    get_current_user,
    get_current_user_optional,
)
from ..schemas import User
from ..dependencies import validate_server_exists

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Route: Main Dashboard ---
@router.get("/", response_class=HTMLResponse, name="index", include_in_schema=False)
async def index(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Renders the main dashboard page (index).

    This page typically displays a list of manageable Bedrock servers.
    Authentication is required; if the user is not authenticated, they are
    redirected to the login page.

    Args:
        request (Request): The incoming FastAPI request object.
        current_user (Optional[User]): The authenticated user object,
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
        f"Dashboard route '/' accessed by user '{current_user.username}'. Rendering server list."
    )

    # --- Dynamically get HTML rendering plugin routes ---
    plugin_html_pages = []
    try:
        # Import the shared plugin_manager from the main web app module
        from ...web.main import global_api_plugin_manager

        if global_api_plugin_manager and hasattr(
            global_api_plugin_manager, "get_html_render_routes"
        ):
            plugin_html_pages = global_api_plugin_manager.get_html_render_routes()
            logger.debug(
                f"Retrieved {len(plugin_html_pages)} plugin HTML pages for the dashboard."
            )
        elif global_api_plugin_manager:
            logger.warning(
                "global_api_plugin_manager does not have 'get_html_render_routes' method."
            )
        else:
            logger.warning(
                "global_api_plugin_manager is not available in web.routers.main."
            )
    except ImportError:
        logger.error(
            "Could not import global_api_plugin_manager in web.routers.main.",
            exc_info=True,
        )
    except Exception as e:
        logger.error(f"Error getting plugin HTML pages: {e}", exc_info=True)

    return get_templates().TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
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
):
    """
    Renders the server-specific monitoring page.

    This page is intended to display real-time information or logs for the
    specified Bedrock server. Authentication is required.

    Args:
        request (Request): The incoming FastAPI request object.
        server_name (str): The name of the server to monitor, validated by
                           `validate_server_exists`. Injected by FastAPI.
        current_user (User): The authenticated user object, injected by
                                       `get_current_user`.

    Returns:
        HTMLResponse: Renders the `monitor.html` template, passing the server name
                      and current user information to the template.
    """
    username = current_user.username
    logger.info(f"User '{username}' accessed monitor page for server '{server_name}'.")
    return get_templates().TemplateResponse(
        request,
        "monitor.html",
        {"request": request, "server_name": server_name, "current_user": current_user},
    )

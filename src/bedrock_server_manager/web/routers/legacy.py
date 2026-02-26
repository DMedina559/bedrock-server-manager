# bedrock_server_manager/web/routers/legacy.py
"""
Legacy UI Router.

This module consolidates all HTML routes from the legacy web application,
serving them under the /legacy prefix.
"""

import logging
import os
import platform
from typing import List, Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ...api import backup_restore as backup_restore_api
from ...context import AppContext
from ...db.models import AuditLog
from ...db.models import User as UserModel
from ...plugins.plugin_manager import PluginManager
from ..auth_utils import (
    get_admin_user,
    get_current_user,
    get_current_user_optional,
    get_moderator_user,
)
from ..dependencies import get_app_context, get_templates, validate_server_exists
from ..schemas import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/legacy",
    tags=["Legacy UI"],
)


# --- From main.py ---


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
        plugin_html_pages = plugin_manager.get_html_render_routes(include_native=False)
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


# --- From server_install_config.py ---


@router.get(
    "/install",
    response_class=HTMLResponse,
    name="install_server_page",
    include_in_schema=False,
)
async def install_server_page(
    request: Request,
    current_user: User = Depends(get_admin_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the HTML page for installing a new Bedrock server.
    """
    identity = current_user.username
    logger.info(f"User '{identity}' accessed new server install page.")
    return templates.TemplateResponse(
        request, "install.html", {"current_user": current_user}
    )


@router.get(
    "/server/{server_name}/configure_properties",
    response_class=HTMLResponse,
    name="configure_properties_page",
    include_in_schema=False,
)
async def configure_properties_page(
    request: Request,
    new_install: bool = False,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the HTML page for configuring a server's ``server.properties`` file.
    """
    identity = current_user.username
    logger.info(
        f"User '{identity}' accessed configure properties for server '{server_name}'. New install: {new_install}"
    )
    return templates.TemplateResponse(
        request,
        "configure_properties.html",
        {
            "current_user": current_user,
            "server_name": server_name,
            "new_install": new_install,
        },
    )


@router.get(
    "/server/{server_name}/configure_allowlist",
    response_class=HTMLResponse,
    name="configure_allowlist_page",
    include_in_schema=False,
)
async def configure_allowlist_page(
    request: Request,
    new_install: bool = False,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the HTML page for configuring a server's ``allowlist.json`` file.
    """
    identity = current_user.username
    logger.info(
        f"User '{identity}' accessed configure allowlist for server '{server_name}'. New install: {new_install}"
    )
    return templates.TemplateResponse(
        request,
        "configure_allowlist.html",
        {
            "current_user": current_user,
            "server_name": server_name,
            "new_install": new_install,
        },
    )


@router.get(
    "/server/{server_name}/configure_permissions",
    response_class=HTMLResponse,
    name="configure_permissions_page",
    include_in_schema=False,
)
async def configure_permissions_page(
    request: Request,
    new_install: bool = False,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the HTML page for configuring player permissions (``permissions.json``).
    """
    identity = current_user.username
    logger.info(
        f"User '{identity}' accessed configure permissions for server '{server_name}'. New install: {new_install}"
    )
    return templates.TemplateResponse(
        request,
        "configure_permissions.html",
        {
            "current_user": current_user,
            "server_name": server_name,
            "new_install": new_install,
        },
    )


@router.get(
    "/server/{server_name}/configure_service",
    response_class=HTMLResponse,
    name="configure_service_page",
    include_in_schema=False,
)
async def configure_service_page(
    request: Request,
    new_install: bool = False,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_admin_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """Serves the HTML page for configuring server-specific service settings (autoupdate/autostart)."""
    identity = current_user.username
    logger.info(
        f"User '{identity}' accessed configure service page for server '{server_name}'. New install: {new_install}"
    )

    template_data = {
        "current_user": current_user,
        "server_name": server_name,
        "os": platform.system(),
        "new_install": new_install,
        "service_exists": False,
        "autostart_enabled": False,
        "autoupdate_enabled": False,
    }
    return templates.TemplateResponse(request, "configure_service.html", template_data)


# --- From settings.py ---


@router.get(
    "/settings",
    response_class=HTMLResponse,
    name="manage_settings_page",
    include_in_schema=False,
)
async def manage_settings_page_route(
    request: Request,
    current_user: User = Depends(get_admin_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the HTML page for managing global application settings.
    """
    identity = current_user.username
    logger.info(f"User '{identity}' accessed global settings page.")
    return templates.TemplateResponse(
        request,
        "manage_settings.html",
        {"current_user": current_user},
    )


# --- From users.py ---


@router.get("/users", response_class=HTMLResponse, include_in_schema=False)
async def users_page(
    request: Request,
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the user management page.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        users = db.query(UserModel).all()
    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": users, "current_user": current_user},
    )


# --- From plugin.py ---


@router.get(
    "/plugins",
    response_class=HTMLResponse,
    name="manage_plugins_page",
    include_in_schema=False,
)
async def manage_plugins_page_route(
    request: Request,
    current_user: User = Depends(get_admin_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the HTML page for managing installed plugins.
    """
    identity = current_user.username
    logger.info(f"User '{identity}' accessed plugin management page.")
    return templates.TemplateResponse(
        request,
        "manage_plugins.html",
        {"current_user": current_user},
    )


# --- From audit_log.py ---


@router.get("/audit-log", response_class=HTMLResponse, include_in_schema=False)
async def audit_log_page(
    request: Request,
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the audit log page.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    return templates.TemplateResponse(
        request,
        "audit_log.html",
        {"logs": logs, "current_user": current_user},
    )


# --- From backup_restore.py ---


@router.get(
    "/server/{server_name}/backup",
    response_class=HTMLResponse,
    name="backup_menu_page",
    include_in_schema=False,
)
async def backup_menu_page(
    request: Request,
    server_name: str,
    current_user: User = Depends(get_moderator_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Displays the backup menu page for a specific server.
    """
    identity = current_user.username
    logger.info(f"User '{identity}' accessed backup menu for server '{server_name}'.")
    return templates.TemplateResponse(
        request,
        "backup_menu.html",
        {"current_user": current_user, "server_name": server_name},
    )


@router.get(
    "/server/{server_name}/backup/select",
    response_class=HTMLResponse,
    name="backup_config_select_page",
    include_in_schema=False,
)
async def backup_config_select_page(
    request: Request,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Displays the page for selecting specific configuration files to back up.
    """
    identity = current_user.username
    logger.info(
        f"User '{identity}' accessed config backup selection page for server '{server_name}'."
    )

    return templates.TemplateResponse(
        request,
        "backup_config_options.html",
        {"current_user": current_user, "server_name": server_name},
    )


@router.get(
    "/server/{server_name}/restore",
    response_class=HTMLResponse,
    name="restore_menu_page",
    include_in_schema=False,
)
async def restore_menu_page(
    request: Request,
    server_name: str,
    current_user: User = Depends(get_moderator_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Displays the restore menu page for a specific server.
    """
    identity = current_user.username
    logger.info(f"User '{identity}' accessed restore menu for server '{server_name}'.")
    return templates.TemplateResponse(
        request,
        "restore_menu.html",
        {"current_user": current_user, "server_name": server_name},
    )


@router.get(
    "/server/{server_name}/restore/{restore_type}/select_file",
    response_class=HTMLResponse,
    name="select_backup_file_page",
    include_in_schema=False,
)
async def show_select_backup_file_page(
    request: Request,
    restore_type: str,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Displays the page for selecting a specific backup file for restoration.
    """
    identity = current_user.username
    logger.info(
        f"User '{identity}' viewing selection page for '{restore_type}' backups for server '{server_name}'."
    )

    valid_types = ["world", "properties", "allowlist", "permissions"]
    if restore_type.lower() not in valid_types:
        redirect_url = request.url_for(
            "restore_menu_page", server_name=server_name
        ).include_query_params(
            message=f"Invalid restore type '{restore_type}' specified.",
            category="warning",
        )
        return RedirectResponse(
            url=str(redirect_url), status_code=status.HTTP_302_FOUND
        )

    app_context = request.app.state.app_context
    try:
        api_result = backup_restore_api.list_backup_files(
            server_name=server_name,
            backup_type=restore_type,
            app_context=app_context,
        )
        if api_result.get("status") == "success":
            full_paths = api_result.get("backups", [])
            if not full_paths:
                redirect_url = request.url_for(
                    "restore_menu_page", server_name=server_name
                ).include_query_params(
                    message=f"No '{restore_type}' backups found for server '{server_name}'.",
                    category="info",
                )
                return RedirectResponse(
                    url=str(redirect_url), status_code=status.HTTP_302_FOUND
                )

            backups_for_template = [
                {
                    "name": os.path.basename(p),
                    "path": os.path.basename(p),
                }
                for p in full_paths
            ]
            return templates.TemplateResponse(
                request,
                "restore_select_backup.html",
                {
                    "current_user": current_user,
                    "server_name": server_name,
                    "restore_type": restore_type,
                    "backups": backups_for_template,
                },
            )
        else:
            error_msg = api_result.get("message", "Unknown error listing backups.")
            logger.error(
                f"Error listing backups for '{server_name}' ({restore_type}): {error_msg}"
            )
            redirect_url = request.url_for(
                "restore_menu_page", server_name=server_name
            ).include_query_params(
                message=f"Error listing backups: {error_msg}", category="error"
            )
            return RedirectResponse(
                url=str(redirect_url), status_code=status.HTTP_302_FOUND
            )
    except Exception as e:
        logger.error(
            f"Unexpected error on backup selection page for '{server_name}' ({restore_type}): {e}",
            exc_info=True,
        )
        redirect_url = request.url_for(
            "restore_menu_page", server_name=server_name
        ).include_query_params(
            message="An unexpected error occurred while preparing backup selection.",
            category="error",
        )
        return RedirectResponse(
            url=str(redirect_url), status_code=status.HTTP_302_FOUND
        )


# --- From setup.py ---


@router.get("/setup", response_class=HTMLResponse, include_in_schema=False)
async def setup_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional),
    app_context: AppContext = Depends(get_app_context),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the setup page if no users exist in the database.
    """
    with app_context.db.session_manager() as db:  # type: ignore
        if db.query(UserModel).first():
            # If a user already exists, redirect to home page, as setup is complete
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request, "setup.html", {"current_user": current_user}
    )


# --- From content.py ---


@router.get(
    "/server/{server_name}/install_world",
    response_class=HTMLResponse,
    name="install_world_page",
    include_in_schema=False,
)
async def install_world_page(
    request: Request,
    server_name: str,
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the HTML page for selecting a world file to install on a server.
    """
    from ...api import application as app_api

    identity = current_user.username
    logger.info(
        f"User '{identity}' accessed world install selection page for server '{server_name}'."
    )

    world_files: List[str] = []
    error_message: Optional[str] = None
    try:
        list_result = app_api.list_available_worlds_api(app_context=app_context)
        if list_result.get("status") == "success":
            full_paths = list_result.get("files", [])
            world_files = [os.path.basename(p) for p in full_paths]
        else:
            error_message = list_result.get(
                "message", "Unknown error listing world files."
            )
            logger.error(
                f"Error listing world files for {server_name} page: {error_message}"
            )
    except Exception as e:
        logger.error(
            f"Unexpected error listing worlds for {server_name} page: {e}",
            exc_info=True,
        )
        error_message = "An unexpected server error occurred while listing worlds."

    return templates.TemplateResponse(
        request,
        "select_world.html",
        {
            "current_user": current_user,
            "server_name": server_name,
            "world_files": world_files,
            "error_message": error_message,
        },
    )


@router.get(
    "/server/{server_name}/install_addon",
    response_class=HTMLResponse,
    name="install_addon_page",
    include_in_schema=False,
)
async def install_addon_page(
    request: Request,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
    templates: Jinja2Templates = Depends(get_templates),
):
    """
    Serves the HTML page for selecting an addon file to install on a server.
    """
    from ...api import application as app_api

    identity = current_user.username
    logger.info(
        f"User '{identity}' accessed addon install selection page for server '{server_name}'."
    )

    addon_files: List[str] = []
    error_message: Optional[str] = None
    try:
        list_result = app_api.list_available_addons_api(app_context=app_context)
        if list_result.get("status") == "success":
            full_paths = list_result.get("files", [])
            addon_files = [os.path.basename(p) for p in full_paths]
        else:
            error_message = list_result.get(
                "message", "Unknown error listing addon files."
            )
            logger.error(
                f"Error listing addon files for {server_name} page: {error_message}"
            )
    except Exception as e:
        logger.error(
            f"Unexpected error listing addons for {server_name} page: {e}",
            exc_info=True,
        )
        error_message = "An unexpected server error occurred while listing addons."

    return templates.TemplateResponse(
        request,
        "select_addon.html",
        {
            "current_user": current_user,
            "server_name": server_name,
            "addon_files": addon_files,
            "error_message": error_message,
        },
    )

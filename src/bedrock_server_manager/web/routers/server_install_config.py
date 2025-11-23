# bedrock_server_manager/web/routers/server_install_config.py
"""
FastAPI router for server installation, updates, and detailed configurations.

This module defines API endpoints and HTML page routes related to:
- Installation of new Bedrock server instances.
- Configuration of server properties (``server.properties``).
- Management of player allowlists (``allowlist.json``).
- Management of player permissions (``permissions.json``).
- Configuration of server-specific service settings like autoupdate and autostart.

It provides both an API for programmatic interaction and routes for serving
HTML configuration pages to the user. Authentication is required for these
operations, and server existence is typically validated for server-specific routes.
"""
import logging
import platform
import os
from typing import Dict, Any, List, Optional
import uuid

from fastapi import (
    APIRouter,
    Request,
    Depends,
    HTTPException,
    status,
    Body,
    Path,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
)
from pydantic import BaseModel, Field
from fastapi.templating import Jinja2Templates

from ..dependencies import get_templates, get_app_context, validate_server_exists
from ..auth_utils import get_current_user
from ..auth_utils import get_admin_user, get_moderator_user
from ..schemas import User
from ...api import (
    server_install_config,
    server as server_api,
    system as system_api,
    utils as utils_api,
)
from ...error import BSMError, UserInputError
from ...context import AppContext

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Pydantic Models ---
class InstallServerPayload(BaseModel):
    """Request model for installing a new server."""

    server_name: str = Field(
        ..., min_length=1, max_length=50, description="Name for the new server."
    )
    server_version: str = Field(
        default="LATEST",
        description="Version to install (e.g., 'LATEST', '1.20.10.01', 'CUSTOM').",
    )
    server_zip_path: Optional[str] = Field(
        default=None,
        description="Absolute path to a custom server ZIP file. Required if server_version is 'CUSTOM'.",
    )
    overwrite: bool = Field(
        default=False,
        description="If true, delete existing server data if server_name conflicts.",
    )


class InstallServerResponse(BaseModel):
    """Response model for server installation requests."""

    status: str = Field(
        ...,
        description="Status of the installation ('success', 'confirm_needed', 'pending').",
    )
    message: str = Field(..., description="Descriptive message about the operation.")
    next_step_url: Optional[str] = Field(
        default=None, description="URL for the next configuration step on success."
    )
    server_name: Optional[str] = Field(
        default=None,
        description="Name of the server, especially if confirmation is needed.",
    )
    task_id: Optional[str] = Field(
        default=None, description="ID of the background installation task."
    )


class PropertiesPayload(BaseModel):
    """Request model for updating server.properties."""

    properties: Dict[str, Any] = Field(
        ..., description="Dictionary of properties to set."
    )


class AllowlistPlayer(BaseModel):
    """Represents a player entry for the allowlist."""

    name: str = Field(..., description="Player's gamertag.")
    ignoresPlayerLimit: bool = Field(
        default=False,
        description="Whether this player ignores the server's player limit.",
    )


class AllowlistAddPayload(BaseModel):
    """Request model for adding players to the allowlist."""

    players: List[str] = Field(..., description="List of player gamertags to add.")
    ignoresPlayerLimit: bool = Field(
        default=False, description="Set 'ignoresPlayerLimit' for these players."
    )


class AllowlistRemovePayload(BaseModel):
    """Request model for removing players from the allowlist."""

    players: List[str] = Field(..., description="List of player gamertags to remove.")


class PlayerPermissionItem(BaseModel):
    """Represents a single player's permission data sent from the client."""

    xuid: str
    name: str
    permission_level: str


class PermissionsSetPayload(BaseModel):
    """Request model for setting multiple player permissions."""

    permissions: List[PlayerPermissionItem] = Field(
        ..., description="List of player permission entries."
    )


class ServiceUpdatePayload(BaseModel):
    """Request model for updating server-specific service settings."""

    autoupdate: Optional[bool] = Field(
        default=None, description="Enable/disable automatic updates for the server."
    )
    autostart: Optional[bool] = Field(
        default=None, description="Enable/disable service autostart for the server."
    )


# --- API Route: /api/downloads/list ---
@router.get(
    "/api/downloads/list",
    tags=["Server Installation API"],
)
async def get_custom_zips(
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves a list of available custom server ZIP files.
    """
    try:
        download_dir = app_context.settings.get("paths.downloads")
        custom_dir = os.path.join(download_dir, "custom")
        if not os.path.isdir(custom_dir):
            return {"status": "success", "custom_zips": []}

        custom_zips = [f for f in os.listdir(custom_dir) if f.endswith(".zip")]
        return {"status": "success", "custom_zips": custom_zips}
    except Exception as e:
        logger.error(f"Failed to get custom zips: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve custom zips.",
        )


# --- HTML Route: /install ---
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


# --- API Route: /api/server/install ---
@router.post(
    "/api/server/install",
    response_model=InstallServerResponse,
    tags=["Server Installation API"],
)
async def install_server_api_route(
    payload: InstallServerPayload,
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Handles the installation of a new Bedrock server instance.

    Validates the server name format, checks for existing servers (if not overwriting),
    deletes existing data if overwrite is true, and then calls a background thread.
    """
    identity = current_user.username
    logger.info(
        f"API: New server install request from user '{identity}' for server '{payload.server_name}'."
    )
    validation_result = utils_api.validate_server_name_format(payload.server_name)
    if validation_result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_result.get("message"),
        )

    try:
        server_exists_result = utils_api.validate_server_exist(
            payload.server_name, app_context=app_context
        )
        server_exists = server_exists_result.get("status") == "success"

        if not payload.overwrite and server_exists:
            logger.info(
                f"Server '{payload.server_name}' already exists. Confirmation needed."
            )

            return InstallServerResponse(
                status="confirm_needed",
                message=f"Server '{payload.server_name}' already exists. Overwrite?",
                server_name=payload.server_name,
            )

        if payload.overwrite and server_exists:
            logger.info(
                f"Overwrite flag set for existing server '{payload.server_name}'. Deleting first."
            )
            delete_result = server_api.delete_server_data(
                server_name=payload.server_name, app_context=app_context
            )
            if delete_result.get("status") == "error":
                logger.error(
                    f"Failed to delete existing server '{payload.server_name}': {delete_result['message']}"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete existing server: {delete_result['message']}",
                )
            logger.info(
                f"Successfully deleted existing server '{payload.server_name}' for overwrite."
            )

        server_zip_path = None
        if payload.server_version.upper() == "CUSTOM":
            if not payload.server_zip_path:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="server_zip_path is required for CUSTOM version.",
                )
            download_dir = app_context.settings.get("paths.downloads")
            custom_dir = os.path.join(download_dir, "custom")
            server_zip_path = os.path.abspath(
                os.path.join(custom_dir, payload.server_zip_path)
            )

        task_id = app_context.task_manager.run_task(
            server_install_config.install_new_server,
            username=current_user.username,
            server_name=payload.server_name,
            target_version=payload.server_version,
            server_zip_path=server_zip_path,
            app_context=app_context,
        )

        return InstallServerResponse(
            status="pending",
            message="Server installation has started.",
            task_id=task_id,
            server_name=payload.server_name,
        )

    except UserInputError as e:
        logger.warning(
            f"API Install Server '{payload.server_name}': UserInputError. {e}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Install Server '{payload.server_name}': BSMError. {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Install Server '{payload.server_name}': Unexpected error. {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during server installation.",
        )


# --- HTML Route: /server/{server_name}/configure_properties ---
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


# --- HTML Route: /server/{server_name}/configure_allowlist ---
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


# --- HTML Route: /server/{server_name}/configure_permissions ---
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


# --- HTML Route: /server/{server_name}/configure_service ---
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


# --- API Route: /api/server/{server_name}/properties/set ---
@router.post(
    "/api/server/{server_name}/properties/set",
    status_code=status.HTTP_200_OK,
    tags=["Server Configuration API"],
)
async def configure_properties_api_route(
    payload: PropertiesPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Modifies properties in the server.properties file for a specific server.
    """
    identity = current_user.username
    logger.info(
        f"API: Configure properties request for '{server_name}' by user '{identity}'."
    )
    properties_data = payload.properties
    if not isinstance(properties_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or missing JSON object body for properties.",
        )

    try:
        result = server_install_config.modify_server_properties(
            server_name=server_name,
            properties_to_update=properties_data,
            app_context=app_context,
        )
        if result.get("status") == "success":
            return result
        else:
            if (
                "not found" in result.get("message", "").lower()
                or "invalid server" in result.get("message", "").lower()
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message")
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Modify Properties '{server_name}': BSMError. {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Modify Properties '{server_name}': Unexpected error. {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


# --- API Route: /api/server/{server_name}/properties/get ---
@router.get(
    "/api/server/{server_name}/properties/get", tags=["Server Configuration API"]
)
async def get_server_properties_api_route(
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves the server.properties for a specific server as a dictionary.
    """
    identity = current_user.username
    logger.info(
        f"API: Get properties request for '{server_name}' by user '{identity}'."
    )
    result = server_install_config.get_server_properties_api(
        server_name=server_name, app_context=app_context
    )

    if result.get("status") == "success":
        return result
    elif "not found" in result.get("message", "").lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "Failed to get server properties."),
        )


# --- API Route: /api/server/{server_name}/allowlist/add ---
@router.post(
    "/api/server/{server_name}/allowlist/add",
    status_code=status.HTTP_200_OK,
    tags=["Server Configuration API"],
)
async def add_to_allowlist_api_route(
    payload: AllowlistAddPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Adds one or more players to the server's allowlist.
    """
    identity = current_user.username
    logger.info(
        f"API: Add to allowlist request for '{server_name}' by user '{identity}'. Players: {payload.players}"
    )
    new_players_data = [
        {"name": player_name, "ignoresPlayerLimit": payload.ignoresPlayerLimit}
        for player_name in payload.players
    ]

    try:
        result = server_install_config.add_players_to_allowlist_api(
            server_name=server_name,
            new_players_data=new_players_data,
            app_context=app_context,
        )
        if result.get("status") == "success":
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Failed to add players to allowlist."),
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(f"API Add Allowlist '{server_name}': BSMError. {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Add Allowlist '{server_name}': Unexpected error. {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )


# --- API Route: /api/server/{server_name}/allowlist/get ---
@router.get(
    "/api/server/{server_name}/allowlist/get", tags=["Server Configuration API"]
)
async def get_allowlist_api_route(
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves the allowlist for a specific server.
    """
    identity = current_user.username
    logger.info(f"API: Get allowlist request for '{server_name}' by user '{identity}'.")
    result = server_install_config.get_server_allowlist_api(
        server_name=server_name, app_context=app_context
    )

    if result.get("status") == "success":
        return result
    elif "not found" in result.get("message", "").lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "Failed to get server allowlist."),
        )


# --- API Route: /api/server/{server_name}/allowlist/remove ---
@router.delete(
    "/api/server/{server_name}/allowlist/remove",
    status_code=status.HTTP_200_OK,
    tags=["Server Configuration API"],
)
async def remove_allowlist_players_api_route(
    payload: AllowlistRemovePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Removes one or more players from the server's allowlist by name.
    """
    identity = current_user.username
    logger.info(
        f"API: Remove from allowlist request for '{server_name}' by user '{identity}'. Players: {payload.players}"
    )
    try:
        result = server_install_config.remove_players_from_allowlist(
            server_name=server_name,
            player_names=payload.players,
            app_context=app_context,
        )
        if result.get("status") == "success":
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get(
                    "message", "Failed to remove players from allowlist."
                ),
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Remove Allowlist Players '{server_name}': BSMError. {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Remove Allowlist Players '{server_name}': Unexpected error. {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred.",
        )


# --- API Route: /api/server/{server_name}/permissions/set ---
@router.put(
    "/api/server/{server_name}/permissions/set",
    status_code=status.HTTP_200_OK,
    tags=["Server Configuration API"],
)
async def configure_permissions_api_route(
    payload: PermissionsSetPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Sets permission levels for multiple players on a specific server.
    """
    identity = current_user.username
    logger.info(
        f"API: Configure permissions request for '{server_name}' by user '{identity}'."
    )
    permission_entries = payload.permissions
    errors: Dict[str, str] = {}  # Store errors by XUID
    success_count = 0

    for item in permission_entries:
        try:
            # Pass item.name to the underlying function
            result = server_install_config.configure_player_permission(
                server_name=server_name,
                xuid=item.xuid,
                player_name=item.name,
                permission=item.permission_level,
                app_context=app_context,
            )
            if result.get("status") == "success":
                success_count += 1
            else:
                errors[item.xuid] = result.get(
                    "message", "Unknown error setting permission."
                )
        except UserInputError as e:
            errors[item.xuid] = str(e)
        except BSMError as e:
            logger.error(
                f"API Permissions Update for '{server_name}', XUID '{item.xuid}': BSMError. {e}",
                exc_info=True,
            )
            errors[item.xuid] = str(e)
        except Exception as e:
            logger.error(
                f"API Permissions Update for '{server_name}', XUID '{item.xuid}': Unexpected error. {e}",
                exc_info=True,
            )
            errors[item.xuid] = "An unexpected server error occurred."

    if not errors:
        return {
            "status": "success",
            "message": f"Permissions updated for {success_count} player(s).",
        }
    else:
        final_status_code = (
            status.HTTP_400_BAD_REQUEST
        )  # Default for client-side type errors

        has_server_error = any(
            not isinstance(e, UserInputError) and isinstance(e, BSMError)
            for xuid_key in errors
            if (
                e := getattr(errors[xuid_key], "__cause__", None)
            )  # Trying to get original exception if wrapped
        )

        if any("not found" in err_msg.lower() for err_msg in errors.values()):
            final_status_code = status.HTTP_404_NOT_FOUND

        is_internal_server_error = False
        for xuid_key in errors:
            msg = errors[xuid_key].lower()
            if "unexpected server error" in msg or (
                "bsmerror" in msg and "userinputerror" not in msg
            ):
                is_internal_server_error = True
                break

        if is_internal_server_error:
            final_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        elif any("not found" in err_msg.lower() for err_msg in errors.values()):
            final_status_code = status.HTTP_404_NOT_FOUND
        # else defaults to HTTP_400_BAD_REQUEST if errors exist

        return JSONResponse(
            status_code=final_status_code,
            content={
                "status": "error",
                "message": "One or more errors occurred while setting permissions.",
                "errors": errors,  # This is Dict[str, str]
            },
        )


# --- API Route: /api/server/{server_name}/permissions/get ---
@router.get(
    "/api/server/{server_name}/permissions/get", tags=["Server Configuration API"]
)
async def get_server_permissions_api_route(
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves processed and formatted permissions data for a specific server.
    """
    identity = current_user.username
    logger.info(
        f"API: Get permissions request for '{server_name}' by user '{identity}'."
    )
    result = server_install_config.get_server_permissions_api(
        server_name=server_name, app_context=app_context
    )

    if result.get("status") == "success":
        return result
    elif "not found" in result.get("message", "").lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "Failed to get server permissions."),
        )


# --- API Route: /api/server/{server_name}/service/update ---
@router.post(
    "/api/server/{server_name}/service/update",
    status_code=status.HTTP_200_OK,
    tags=["Server Configuration API"],
)
async def configure_service_api_route(
    server_name: str = Depends(validate_server_exists),
    payload: ServiceUpdatePayload = Body(...),
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Updates server-specific service settings like autoupdate and autostart.
    """
    identity = current_user.username
    logger.info(
        f"API: Configure service request for '{server_name}' by user '{identity}'. Payload: {payload.model_dump_json(exclude_none=True)}"
    )
    current_os = platform.system()

    if payload.autoupdate is None and payload.autostart is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No options provided (autoupdate or autostart must be present).",
        )

    messages = []
    warnings = []

    try:
        # Handle autoupdate first
        if payload.autoupdate is not None:
            result_autoupdate = system_api.set_autoupdate(
                server_name=server_name,
                autoupdate_value=str(payload.autoupdate).lower(),
                app_context=app_context,
            )
            if result_autoupdate.get("status") == "success":
                messages.append("Autoupdate setting applied successfully.")
            else:
                # Raise to be caught by the generic error handlers below
                raise BSMError(
                    f"Failed to set autoupdate: {result_autoupdate.get('message')}"
                )

        # Handle autostart
        if payload.autostart is not None:
            result_autostart = system_api.set_autostart(
                server_name=server_name,
                autostart_value=str(payload.autostart).lower(),
                app_context=app_context,
            )
            if result_autostart.get("status") == "success":
                messages.append("autostart setting applied successfully.")
            else:
                # Raise to be caught by the generic error handlers below
                raise BSMError(
                    f"Failed to set autostart: {result_autostart.get('message')}"
                )

        # Combine messages and warnings for the final response
        final_message = " ".join(messages)
        if warnings:
            final_message += " " + " ".join(warnings)

        return {
            "status": "success_with_warning" if warnings else "success",
            "message": final_message or "No configuration changes were made.",
        }

    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Configure Service '{server_name}': BSMError. {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Configure Service '{server_name}': Unexpected error. {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred while configuring service.",
        )

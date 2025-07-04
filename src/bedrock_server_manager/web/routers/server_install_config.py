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
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status, Body, Path
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
)
from pydantic import BaseModel, Field

from bedrock_server_manager.web.templating import templates
from bedrock_server_manager.web.auth_utils import get_current_user
from ..dependencies import validate_server_exists
from bedrock_server_manager.api import (
    server_install_config,
    server as server_api,
    system as system_api,
    utils as utils_api,
)
from bedrock_server_manager.error import BSMError, UserInputError, AppFileNotFoundError

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
        description="Version to install (e.g., 'LATEST', '1.20.10.01').",
    )
    overwrite: bool = Field(
        default=False,
        description="If true, delete existing server data if server_name conflicts.",
    )


class InstallServerResponse(BaseModel):
    """Response model for server installation requests."""

    status: str = Field(
        ..., description="Status of the installation ('success', 'confirm_needed')."
    )
    message: str = Field(..., description="Descriptive message about the operation.")
    next_step_url: Optional[str] = Field(
        default=None, description="URL for the next configuration step on success."
    )
    server_name: Optional[str] = Field(
        default=None,
        description="Name of the server, especially if confirmation is needed.",
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


class PermissionsSetPayload(BaseModel):
    """Request model for setting multiple player permissions.

    The dictionary should map XUIDs (str) to permission levels (str, e.g., "operator").
    """

    permissions: Dict[str, str] = Field(
        ..., description="Player XUID to permission level mapping."
    )


class ServiceUpdatePayload(BaseModel):
    """Request model for updating server-specific service settings."""

    autoupdate: Optional[bool] = Field(
        default=None, description="Enable/disable automatic updates for the server."
    )
    autostart: Optional[bool] = Field(
        default=None, description="Enable/disable service autostart for the server."
    )


# --- HTML Route: /install ---
@router.get(
    "/install",
    response_class=HTMLResponse,
    name="install_server_page",
    include_in_schema=False,
)
async def install_server_page(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Serves the HTML page for installing a new Bedrock server."""
    identity = current_user.get("username", "Unknown")
    logger.info(f"User '{identity}' accessed new server install page.")
    return templates.TemplateResponse(
        "install.html", {"request": request, "current_user": current_user}
    )


# --- API Route: /api/server/install ---
@router.post(
    "/api/server/install",
    response_model=InstallServerResponse,
    tags=["Server Installation API"],
)
async def install_server_api_route(
    payload: InstallServerPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Handles the installation of a new Bedrock server instance.

    Validates the server name format, checks for existing servers (if not overwriting),
    deletes existing data if overwrite is true, and then calls
    :func:`~bedrock_server_manager.api.server_install_config.install_new_server`.

    - **Request body**: Expects an :class:`.InstallServerPayload`.
    - Requires authentication.
    - Returns :class:`.InstallServerResponse` which may indicate success,
      a need for overwrite confirmation, or an error.
    """
    identity = current_user.get("username", "Unknown")
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
        server_exists_result = utils_api.validate_server_exist(payload.server_name)
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
            delete_result = server_api.delete_server_data(payload.server_name)
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

        install_result = server_install_config.install_new_server(
            payload.server_name, payload.server_version
        )

        if install_result.get("status") == "success":
            logger.info(f"Server '{payload.server_name}' installed successfully.")
            next_url = (
                f"/server/{payload.server_name}/configure_properties?new_install=true"
            )
            return InstallServerResponse(
                status="success",
                message=install_result.get("message", "Server installed successfully."),
                next_step_url=next_url,
                server_name=payload.server_name,
            )
        else:
            logger.error(
                f"Server installation failed for '{payload.server_name}': {install_result.get('message')}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=install_result.get("message", "Server installation failed."),
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Serves the HTML page for configuring server.properties.

    Args:
        request (:class:`fastapi.Request`): FastAPI request object.
        new_install (bool, optional): Flag indicating if this is part of a new server setup flow.
        server_name (str): Name of the server (validated by dependency).
        current_user (Dict[str, Any]): Authenticated user (from dependency).
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"User '{identity}' accessed configure properties for server '{server_name}'. New install: {new_install}"
    )
    return templates.TemplateResponse(
        "configure_properties.html",
        {
            "request": request,
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Serves the HTML page for configuring the server's allowlist.

    Args:
        request (:class:`fastapi.Request`): FastAPI request object.
        new_install (bool, optional): Flag indicating if this is part of a new server setup flow.
        server_name (str): Name of the server (validated by dependency).
        current_user (Dict[str, Any]): Authenticated user (from dependency).
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"User '{identity}' accessed configure allowlist for server '{server_name}'. New install: {new_install}"
    )
    return templates.TemplateResponse(
        "configure_allowlist.html",
        {
            "request": request,
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Serves the HTML page for configuring player permissions (permissions.json).

    Args:
        request (:class:`fastapi.Request`): FastAPI request object.
        new_install (bool, optional): Flag indicating if this is part of a new server setup flow.
        server_name (str): Name of the server (validated by dependency).
        current_user (Dict[str, Any]): Authenticated user (from dependency).
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"User '{identity}' accessed configure permissions for server '{server_name}'. New install: {new_install}"
    )
    return templates.TemplateResponse(
        "configure_permissions.html",
        {
            "request": request,
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Serves the HTML page for configuring server-specific service settings (autoupdate/autostart).

    Passes OS type to the template for conditional rendering.
    Initial service status flags (exists, autostart, autoupdate) are placeholders
    and typically updated by client-side JavaScript calls to other API endpoints.

    Args:
        request (:class:`fastapi.Request`): FastAPI request object.
        new_install (bool, optional): Flag indicating if this is part of a new server setup flow.
        server_name (str): Name of the server (validated by dependency).
        current_user (Dict[str, Any]): Authenticated user (from dependency).
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"User '{identity}' accessed configure service page for server '{server_name}'. New install: {new_install}"
    )

    template_data = {
        "request": request,
        "current_user": current_user,
        "server_name": server_name,
        "os": platform.system(),
        "new_install": new_install,
        "service_exists": False,
        "autostart_enabled": False,
        "autoupdate_enabled": False,
    }
    return templates.TemplateResponse("configure_service.html", template_data)


# --- API Route: /api/server/{server_name}/properties/set ---
@router.post(
    "/api/server/{server_name}/properties/set",
    status_code=status.HTTP_200_OK,
    tags=["Server Configuration API"],
)
async def configure_properties_api_route(
    payload: PropertiesPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Modifies properties in the server.properties file for a specific server.

    Calls :func:`~bedrock_server_manager.api.server_install_config.modify_server_properties`.
    The server may be restarted if changes are made (default behavior of the API call).

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - **Request body**: Expects a :class:`.PropertiesPayload`.
    - Requires authentication.
    - Returns the result from the API call, typically ``{"status": "success", ...}`` or an error.
    """
    identity = current_user.get("username", "Unknown")
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
            server_name, properties_data
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieves the server.properties for a specific server as a dictionary.

    Calls :func:`~bedrock_server_manager.api.server_install_config.get_server_properties_api`.

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - Requires authentication.
    - Returns a dictionary containing the properties on success.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Get properties request for '{server_name}' by user '{identity}'."
    )

    result = server_install_config.get_server_properties_api(server_name)

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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Adds one or more players to the server's allowlist.

    Calls :func:`~bedrock_server_manager.api.server_install_config.add_players_to_allowlist_api`.

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - **Request body**: Expects an :class:`.AllowlistAddPayload`.
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Add to allowlist request for '{server_name}' by user '{identity}'. Players: {payload.players}"
    )

    new_players_data = [
        {"name": player_name, "ignoresPlayerLimit": payload.ignoresPlayerLimit}
        for player_name in payload.players
    ]

    try:
        result = server_install_config.add_players_to_allowlist_api(
            server_name, new_players_data
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieves the allowlist for a specific server.

    Calls :func:`~bedrock_server_manager.api.server_install_config.get_server_allowlist_api`.

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - Requires authentication.
    - Returns a list of player objects on the allowlist.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Get allowlist request for '{server_name}' by user '{identity}'.")

    result = server_install_config.get_server_allowlist_api(server_name)

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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Removes one or more players from the server's allowlist by name.

    Calls :func:`~bedrock_server_manager.api.server_install_config.remove_players_from_allowlist`.

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - **Request body**: Expects an :class:`.AllowlistRemovePayload`.
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Remove from allowlist request for '{server_name}' by user '{identity}'. Players: {payload.players}"
    )

    try:
        result = server_install_config.remove_players_from_allowlist(
            server_name, payload.players
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Sets permission levels for multiple players on a specific server.

    Calls :func:`~bedrock_server_manager.api.server_install_config.configure_player_permission`
    iteratively for each player in the payload.

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - **Request body**: Expects a :class:`.PermissionsSetPayload`.
    - Requires authentication.
    - Returns a summary of successes and errors.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Configure permissions request for '{server_name}' by user '{identity}'."
    )

    permissions_map = payload.permissions
    errors: Dict[str, str] = {}
    success_count = 0

    for xuid, level in permissions_map.items():
        try:
            result = server_install_config.configure_player_permission(
                server_name, xuid, None, level
            )
            if result.get("status") == "success":
                success_count += 1
            else:
                errors[xuid] = result.get(
                    "message", "Unknown error setting permission."
                )
        except UserInputError as e:
            errors[xuid] = str(e)
        except BSMError as e:
            logger.error(
                f"API Permissions Update for '{server_name}', XUID '{xuid}': BSMError. {e}",
                exc_info=True,
            )
            errors[xuid] = str(e)
        except Exception as e:
            logger.error(
                f"API Permissions Update for '{server_name}', XUID '{xuid}': Unexpected error. {e}",
                exc_info=True,
            )
            errors[xuid] = "An unexpected server error occurred."

    if not errors:
        return {
            "status": "success",
            "message": f"Permissions updated for {success_count} player(s).",
        }
    else:
        final_status_code = status.HTTP_400_BAD_REQUEST
        if any("not found" in err_msg.lower() for err_msg in errors.values()):
            final_status_code = status.HTTP_404_NOT_FOUND
        elif any(
            err_type not in [UserInputError.__name__, AppFileNotFoundError.__name__]
            for err_type in [
                type(e).__name__ for e in errors.values() if isinstance(e, Exception)
            ]
        ):
            final_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        return JSONResponse(
            status_code=final_status_code,
            content={
                "status": "error",
                "message": "One or more errors occurred while setting permissions.",
                "errors": errors,
            },
        )


# --- API Route: /api/server/{server_name}/permissions/get ---
@router.get(
    "/api/server/{server_name}/permissions/get", tags=["Server Configuration API"]
)
async def get_server_permissions_api_route(
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieves processed and formatted permissions data for a specific server.

    Calls :func:`~bedrock_server_manager.api.server_install_config.get_server_permissions_api`
    which reads ``permissions.json`` and enriches entries with player names.
    The list of permissions is sorted by player name.

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - Requires authentication.
    - Returns a dictionary containing the formatted permissions list on success.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Get permissions request for '{server_name}' by user '{identity}'."
    )

    result = server_install_config.get_server_permissions_api(server_name)

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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Updates server-specific service settings like autoupdate and autostart.

    Calls :func:`~bedrock_server_manager.api.system.set_autoupdate` for the
    autoupdate flag and
    :func:`~bedrock_server_manager.api.system.create_server_service` for the
    autostart flag (which implicitly handles service creation/enable/disable).

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - **Request body**: Expects a :class:`.ServiceUpdatePayload`.
    - Requires authentication.
    - At least one of `autoupdate` or `autostart` must be provided in the payload.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Configure service request for '{server_name}' by user '{identity}'. Payload: {payload.model_dump_json(exclude_none=True)}"
    )

    current_os = platform.system()

    if payload.autoupdate is None and payload.autostart is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No options provided (autoupdate or autostart must be present).",
        )

    try:
        if payload.autoupdate is not None:
            result_autoupdate = system_api.set_autoupdate(
                server_name, str(payload.autoupdate).lower()
            )
            if result_autoupdate.get("status") != "success":
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to set autoupdate: {result_autoupdate.get('message')}",
                )

        if payload.autostart is not None:
            if current_os in ["Linux", "Windows"]:
                result_autostart = system_api.create_server_service(
                    server_name, payload.autostart
                )
                if result_autostart.get("status") != "success":
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to set autostart: {result_autostart.get('message')}",
                    )
            else:
                logger.warning(
                    f"API: 'autostart' configuration ignored for '{server_name}': unsupported OS ({current_os})."
                )
                if payload.autoupdate is None:
                    return {
                        "status": "success",
                        "message": "Autoupdate not specified. Autostart configuration ignored on unsupported OS.",
                    }

        return {
            "status": "success",
            "message": "Service configuration applied successfully.",
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

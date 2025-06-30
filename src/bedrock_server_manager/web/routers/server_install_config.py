import logging
import platform
from typing import Dict, Any, List, Optional

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
from bedrock_server_manager.error import BSMError, UserInputError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Server Installation & Configuration"])


# --- Pydantic Models ---
class InstallServerPayload(BaseModel):
    server_name: str = Field(..., min_length=1, max_length=50)
    server_version: str = Field(default="LATEST")
    overwrite: bool = False


class InstallServerResponse(BaseModel):
    status: str
    message: str
    next_step_url: Optional[str] = None
    server_name: Optional[str] = None


class PropertiesPayload(BaseModel):

    properties: Dict[str, Any]


class AllowlistPlayer(BaseModel):
    name: str
    ignoresPlayerLimit: bool = False


class AllowlistAddPayload(BaseModel):
    players: List[str]
    ignoresPlayerLimit: bool = False


class AllowlistRemovePayload(BaseModel):
    players: List[str]


class PermissionsSetPayload(BaseModel):
    permissions: Dict[str, str]


class ServiceUpdatePayload(BaseModel):
    autoupdate: Optional[bool] = None
    autostart: Optional[bool] = None


# --- HTML Route: /install ---
@router.get("/install", response_class=HTMLResponse, name="install_server_page")
async def install_server_page(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user)
):
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
        server_exists = utils_api.validate_server_exist(payload.server_name)

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
)
async def configure_properties_page(
    request: Request,
    new_install: bool = False,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
)
async def configure_allowlist_page(
    request: Request,
    new_install: bool = False,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
)
async def configure_permissions_page(
    request: Request,
    new_install: bool = False,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
)
async def configure_service_page(
    request: Request,
    new_install: bool = False,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Configure properties request for '{server_name}' by user '{identity}'."
    )

    # The payload.properties directly gives the dictionary
    properties_data = payload.properties
    if not isinstance(properties_data, dict):
        # This check might be redundant due to Pydantic validation but kept for safety.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or missing JSON object body for properties.",
        )

    try:
        result = server_install_config.modify_server_properties(
            server_name, properties_data
        )
        if result.get("status") == "success":
            return result  # FastAPI will serialize this dict to JSON
        else:
            # Check if the error is due to server not found or other input error
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
    except (
        UserInputError
    ) as e:  # Catches issues from modify_server_properties if it raises this
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:  # Catch other BSM specific errors
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
async def get_server_properties_api_route(  # Renamed from get_server_properties_route to avoid conflict if it was a typo
    server_name: str = Depends(validate_server_exists),  # Apply dependency
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Configure permissions request for '{server_name}' by user '{identity}'."
    )

    permissions_map = payload.permissions
    errors: Dict[str, str] = {}
    success_count = 0

    if not utils_api.validate_server_exist(server_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found.",
        )

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

        all_user_input_errors = all(
            isinstance(
                server_install_config.get_player_xuid(xuid_or_gamertag=xuid),
                UserInputError,
            )
            for xuid in errors.keys()
        )
        final_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if all(
            any(
                msg_keyword in err_msg.lower()
                for msg_keyword in ["invalid xuid", "invalid level"]
            )
            for err_msg in errors.values()
        ):
            final_status_code = status.HTTP_400_BAD_REQUEST

        return JSONResponse(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
                if any(e not in UserInputError.__name__ for e in errors.values())
                else status.HTTP_400_BAD_REQUEST
            ),
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
    server_name: str,
    payload: ServiceUpdatePayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
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
        # Validate server existence
        if not utils_api.validate_server_exist(server_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        if payload.autoupdate is not None:
            if not isinstance(
                payload.autoupdate, bool
            ):  # Should be caught by Pydantic, but defensive
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="'autoupdate' must be a boolean.",
                )

            result_autoupdate = system_api.set_autoupdate(
                server_name, str(payload.autoupdate)
            )
            if result_autoupdate.get("status") != "success":

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to set autoupdate: {result_autoupdate.get('message')}",
                )

        if payload.autostart is not None:
            if not isinstance(payload.autostart, bool):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="'autostart' must be a boolean.",
                )

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

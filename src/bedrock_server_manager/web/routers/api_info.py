import logging
import os
from typing import Dict, Any, List, Optional

import logging
import os
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bedrock_server_manager.web.auth_utils import get_current_user
from ..dependencies import validate_server_exists
from bedrock_server_manager.api import info as info_api
from bedrock_server_manager.api import player as player_api
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.api import system as system_api
from bedrock_server_manager.api import utils as utils_api
from bedrock_server_manager.api import (
    application as app_api,
)
from bedrock_server_manager.api import misc as misc_api
from bedrock_server_manager.error import BSMError, UserInputError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["API Information"])


# --- Pydantic Models ---
class GeneralApiResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    servers: Optional[List[Dict[str, Any]]] = None
    info: Optional[Dict[str, Any]] = None
    players: Optional[List[Dict[str, Any]]] = None
    files_deleted: Optional[int] = None
    files_kept: Optional[int] = None


class PruneDownloadsPayload(BaseModel):
    directory: str = Field(..., min_length=1)
    keep: Optional[int] = Field(default=None, ge=0)


class AddPlayersPayload(BaseModel):
    players: List[str]


# --- Server Info Endpoints ---
@router.get(
    "/api/server/{server_name}/status",
    response_model=GeneralApiResponse,
    tags=["Server Info API"],
)
async def get_server_running_status_api_route(
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Request for running status for server '{server_name}' by user '{identity}'."
    )
    try:
        result = info_api.get_server_running_status(server_name)
        if result.get("status") == "success":
            return GeneralApiResponse(
                status="success",
                data={"running": result.get("running")},
                message=result.get("message"),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to get server running status."),
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Running Status '{server_name}': BSMError: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Running Status '{server_name}': Unexpected error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error checking running status.",
        )


@router.get(
    "/api/server/{server_name}/config_status",
    response_model=GeneralApiResponse,
    tags=["Server Info API"],
)
async def get_server_config_status_api_route(
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Request for config status for server '{server_name}' by user '{identity}'."
    )
    try:
        result = info_api.get_server_config_status(server_name)
        if result.get("status") == "success":
            return GeneralApiResponse(
                status="success",
                data={"config_status": result.get("config_status")},
                message=result.get("message"),
            )
        else:
            if "not found" in result.get("message", "").lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to get server config status."),
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(f"API Config Status '{server_name}': BSMError: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Config Status '{server_name}': Unexpected error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error getting config status.",
        )


@router.get(
    "/api/server/{server_name}/version",
    response_model=GeneralApiResponse,
    tags=["Server Info API"],
)
async def get_server_version_api_route(
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Request for installed version for server '{server_name}' by user '{identity}'."
    )
    try:
        result = info_api.get_server_installed_version(server_name)
        if result.get("status") == "success":
            return GeneralApiResponse(
                status="success",
                data={"version": result.get("version")},
                message=result.get("message"),
            )
        else:
            if "not found" in result.get("message", "").lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to get server version."),
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Installed Version '{server_name}': BSMError: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Installed Version '{server_name}': Unexpected error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error getting installed version.",
        )


@router.get(
    "/api/server/{server_name}/validate",
    response_model=GeneralApiResponse,
    tags=["Server Info API"],
)
async def validate_server_api_route(
    server_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Request to validate server '{server_name}' by user '{identity}'."
    )
    try:
        result = utils_api.validate_server_exist(server_name)
        if result.get("status") == "success":
            return GeneralApiResponse(status="success", message=result.get("message"))
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message")
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Validate Server '{server_name}': BSMError: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Validate Server '{server_name}': Unexpected error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error validating server.",
        )


@router.get(
    "/api/server/{server_name}/process_info",
    response_model=GeneralApiResponse,
    tags=["Server Info API"],
)
async def server_process_info_api_route(
    server_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    identity = current_user.get("username", "Unknown")
    logger.debug(f"API: Process info request for '{server_name}' by user '{identity}'.")
    try:
        result = system_api.get_bedrock_process_info(server_name)

        if result.get("status") == "success":
            return GeneralApiResponse(
                status="success",
                data={"process_info": result.get("process_info")},
                message=result.get("message"),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to get process info."),
            )

    except UserInputError as e:
        logger.warning(f"API Process Info '{server_name}': Input error. {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(f"API Process Info '{server_name}': BSMError: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Process Info '{server_name}': Unexpected error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error getting process info.",
        )


# --- Global Action Endpoints ---
@router.post(
    "/api/players/scan", response_model=GeneralApiResponse, tags=["Global Actions API"]
)
async def scan_players_api_route(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Request to scan logs for players by user '{identity}'.")
    try:
        result = player_api.scan_and_update_player_db_api()
        if result.get("status") == "success":
            return GeneralApiResponse(status="success", message=result.get("message"))
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to scan player logs."),
            )
    except BSMError as e:
        logger.error(f"API Scan Players: BSMError: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"API Scan Players: Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error scanning player logs.",
        )


@router.post(
    "/api/downloads/prune",
    response_model=GeneralApiResponse,
    tags=["Global Actions API"],
)
async def prune_downloads_api_route(
    payload: PruneDownloadsPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Request to prune downloads by user '{identity}'. Payload: {payload.model_dump_json(exclude_none=True)}"
    )

    try:
        download_cache_base_dir = settings.get("paths.downloads")
        if not download_cache_base_dir:
            raise BSMError("DOWNLOAD_DIR setting is missing or empty in configuration.")

        full_download_dir_path = os.path.normpath(
            os.path.join(download_cache_base_dir, payload.directory)
        )

        if not os.path.abspath(full_download_dir_path).startswith(
            os.path.abspath(download_cache_base_dir) + os.sep
        ):
            logger.error(
                f"API Prune Downloads: Security violation - Invalid directory path '{payload.directory}'."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid directory path: Path is outside the allowed download cache base directory.",
            )

        if not os.path.isdir(full_download_dir_path):
            logger.warning(
                f"API Prune Downloads: Target cache directory not found: {full_download_dir_path} (from relative: '{payload.directory}')"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target cache directory not found.",
            )

        result = misc_api.prune_download_cache(full_download_dir_path, payload.keep)

        if result.get("status") == "success":
            return GeneralApiResponse(
                status="success",
                message=result.get(
                    "message", "Pruning operation completed successfully."
                ),
                files_deleted=result.get("files_deleted"),
                files_kept=result.get("files_kept"),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Unknown error during prune operation."),
            )

    except UserInputError as e:
        logger.warning(f"API Prune Downloads: UserInputError: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.warning(f"API Prune Downloads: Application error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Prune Downloads: Unexpected error for relative_dir '{payload.directory}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the pruning process.",
        )


@router.get("/api/servers", response_model=GeneralApiResponse, tags=["Global Info API"])
async def get_servers_list_api_route(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.debug(f"API: Request for all servers list by user '{identity}'.")
    try:
        result = app_api.get_all_servers_data()
        if result.get("status") == "success":
            return GeneralApiResponse(status="success", servers=result.get("servers"))
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to retrieve server list."),
            )
    except Exception as e:
        logger.error(f"API Get Servers List: Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred retrieving the server list.",
        )


@router.get("/api/info", response_model=GeneralApiResponse, tags=["Global Info API"])
async def get_system_info_api_route():
    logger.debug("API: Request for system and app info.")
    try:
        result = utils_api.get_system_and_app_info()
        if result.get("status") == "success":
            return GeneralApiResponse(status="success", info=result.get("info"))
        else:

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "Failed to retrieve system info."),
            )
    except Exception as e:
        logger.error(f"API Get System Info: Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred retrieving system info.",
        )


@router.post(
    "/api/players/add", response_model=GeneralApiResponse, tags=["Player Info API"]
)
async def add_players_api_route(
    payload: AddPlayersPayload, current_user: Dict[str, Any] = Depends(get_current_user)
):
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Request to add players by user '{identity}'. Payload: {payload.players}"
    )

    try:

        result = player_api.add_players_manually_api(player_strings=payload.players)

        if result.get("status") == "success":
            return GeneralApiResponse(status="success", message=result.get("message"))
        else:

            msg_lower = result.get("message", "").lower()
            status_code = (
                status.HTTP_400_BAD_REQUEST
                if "invalid" in msg_lower or "format" in msg_lower
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            raise HTTPException(
                status_code=status_code,
                detail=result.get("message", "Failed to add players."),
            )

    except (
        TypeError,
        UserInputError,
        BSMError,
    ) as e:
        logger.warning(f"API Add Players: Client or application error: {e}")
        status_code = (
            status.HTTP_400_BAD_REQUEST
            if isinstance(e, (TypeError, UserInputError))
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger.error(
            f"API Add Players: Unexpected critical error in route: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A critical unexpected server error occurred while adding players.",
        )

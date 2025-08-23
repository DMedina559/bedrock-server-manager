# bedrock_server_manager/web/routers/api_info.py
"""
FastAPI router for retrieving various informational data about servers and the application.

This module defines API endpoints that provide read-only access to:
- Specific server details: running status, configured status, installed version,
  process information, and validation of existence.
- Global application data: list of all servers, general application info (version, OS, paths).
- Player database information.
- Global actions like scanning for players or pruning download caches.

Endpoints typically require authentication and often use path parameters to specify
a server. Responses are generally structured using the :class:`.GeneralApiResponse` model.
"""
import logging
import os
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field

from ..schemas import BaseApiResponse, User
from ..auth_utils import get_current_user, get_admin_user, get_moderator_user
from ..dependencies import validate_server_exists, get_app_context
from ...api import (
    application as app_api,
    utils as utils_api,
    system as system_api,
    player as player_api,
    info as info_api,
)
from ...api import misc as misc_api
from ...error import BSMError, UserInputError
from ...context import AppContext

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Pydantic Models ---
class ServerSchema(BaseModel):
    name: str
    status: str
    version: str
    player_count: int


class GeneralApiResponse(BaseApiResponse):
    """A general-purpose API response model."""

    # status: str -> Inherited
    # message: Optional[str] = None -> Inherited
    data: Optional[Dict[str, Any]] = None  # Often for single item details
    servers: Optional[List[ServerSchema]] = None  # For lists of server data
    info: Optional[Dict[str, Any]] = None  # For app/system info
    players: Optional[List[Dict[str, Any]]] = None  # For player lists
    files_deleted: Optional[int] = None  # For prune operations
    files_kept: Optional[int] = None  # For prune operations


class PruneDownloadsPayload(BaseModel):
    """Request model for pruning the download cache."""

    directory: str = Field(
        ...,
        min_length=1,
        description="The subdirectory within the main download cache to prune (e.g., 'stable' or 'preview').",
    )
    keep: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of recent archives to keep. Uses global setting if None.",
    )


class AddPlayersPayload(BaseModel):
    """Request model for manually adding players to the database.

    Each string in the 'players' list should be in the format "gamertag:xuid".
    """

    players: List[str] = Field(
        ...,
        description='List of player strings, e.g., ["PlayerOne:123xuid", "PlayerTwo:456xuid"]',
    )


# --- Server Info Endpoints ---
@router.get(
    "/api/server/{server_name}/status",
    response_model=GeneralApiResponse,
    tags=["Server Info API"],
)
async def get_server_running_status_api_route(
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Checks if a specific server's process is currently running.
    """
    identity = current_user.username
    logger.info(
        f"API: Request for running status for server '{server_name}' by user '{identity}'."
    )
    try:
        result = info_api.get_server_running_status(
            server_name=server_name, app_context=app_context
        )
        if result.get("status") == "success":
            return GeneralApiResponse(
                status="success",
                data={"running": result.get("is_running")},
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
    current_user: User = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves the last known status from a server's configuration file.
    """
    identity = current_user.username
    logger.info(
        f"API: Request for config status for server '{server_name}' by user '{identity}'."
    )
    try:
        result = info_api.get_server_config_status(
            server_name=server_name, app_context=app_context
        )
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
    current_user: User = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves the installed version of a specific server.
    """
    identity = current_user.username
    logger.info(
        f"API: Request for installed version for server '{server_name}' by user '{identity}'."
    )
    try:
        result = info_api.get_server_installed_version(
            server_name=server_name, app_context=app_context
        )
        if result.get("status") == "success":
            return GeneralApiResponse(
                status="success",
                data={"version": result.get("installed_version")},
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
    server_name: str,
    current_user: User = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Validates if a server installation exists and is minimally correct.
    """
    identity = current_user.username
    logger.info(
        f"API: Request to validate server '{server_name}' by user '{identity}'."
    )
    try:
        result = utils_api.validate_server_exist(
            server_name=server_name, app_context=app_context
        )
        if result.get("status") == "success":
            return GeneralApiResponse(status="success", message=result.get("message"))
        else:
            # This case handles when the underlying API returns an error status
            # without raising an exception itself.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get(
                    "message", f"Server '{server_name}' not found or is invalid."
                ),
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"API Validate Server '{server_name}': Unexpected error in route: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while validating the server.",
        )


@router.get(
    "/api/server/{server_name}/process_info",
    response_model=GeneralApiResponse,
    tags=["Server Info API"],
)
async def server_process_info_api_route(
    server_name: str,
    current_user: User = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves resource usage information for a running server process.
    """
    identity = current_user.username
    logger.debug(f"API: Process info request for '{server_name}' by user '{identity}'.")
    try:
        result = system_api.get_bedrock_process_info(
            server_name=server_name, app_context=app_context
        )

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
    "/api/players/scan", response_model=GeneralApiResponse, tags=["Global Players API"]
)
async def scan_players_api_route(
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Scans all server logs to discover and update the central player database.
    """
    identity = current_user.username
    logger.info(f"API: Request to scan logs for players by user '{identity}'.")
    try:
        result = player_api.scan_and_update_player_db_api(app_context=app_context)
        if result.get("status") == "success":
            return GeneralApiResponse(
                status="success",
                message=result.get("message"),
                data=result.get("details"),
            )
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


@router.get(
    "/api/players/get", response_model=GeneralApiResponse, tags=["Global Players API"]
)
async def get_all_players_api_route(
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves the list of all known players from the central player database.
    """
    identity = current_user.username
    logger.info(f"API: Request to retrieve all players by user '{identity}'.")
    try:
        result_dict = player_api.get_all_known_players_api(app_context=app_context)

        if result_dict.get("status") == "success":
            logger.debug(
                f"API Get All Players: Successfully retrieved {len(result_dict.get('players', []))} players. "
                f"Message: {result_dict.get('message', 'N/A')}"
            )
            return GeneralApiResponse(
                status="success",
                players=result_dict.get("players"),
                message=result_dict.get("message"),
            )
        else:  # status == "error"
            logger.warning(
                f"API Get All Players: Handler returned error: {result_dict.get('message')}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result_dict.get(
                    "message", "Error retrieving player list from API."
                ),
            )

    except BSMError as e:  # Catch specific application errors if needed
        logger.error(
            f"API Get All Players: BSMError occurred: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"A server error occurred while fetching players: {str(e)}",
        )
    except Exception as e:
        logger.error(
            f"API Get All Players: Unexpected critical error in route: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A critical unexpected server error occurred while fetching players.",
        )


@router.post(
    "/api/downloads/prune",
    response_model=GeneralApiResponse,
    tags=["Global Actions API"],
)
async def prune_downloads_api_route(
    payload: PruneDownloadsPayload,
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Prunes old downloaded server archives from a specified cache subdirectory.
    """
    identity = current_user.username
    logger.info(
        f"API: Request to prune downloads by user '{identity}'. Payload: {payload.model_dump_json(exclude_none=True)}"
    )
    try:
        download_cache_base_dir = app_context.settings.get("paths.downloads")
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

        result = misc_api.prune_download_cache(
            full_download_dir_path, payload.keep, app_context=app_context
        )

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
    current_user: User = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves a list of all detected server instances with their status and version.
    """
    identity = current_user.username
    logger.debug(f"API: Request for all servers list by user '{identity}'.")
    try:
        result = app_api.get_all_servers_data(app_context=app_context)
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
async def get_system_info_api_route(
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves general system and application information.
    """
    logger.debug("API: Request for system and app info.")
    try:
        result = utils_api.get_system_and_app_info(app_context=app_context)
        if result.get("status") == "success":
            return GeneralApiResponse(status="success", info=result.get("data"))
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
    "/api/players/add", response_model=GeneralApiResponse, tags=["Global Players API"]
)
async def add_players_api_route(
    payload: AddPlayersPayload,
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Manually adds or updates player entries in the central player database.
    """
    identity = current_user.username
    logger.info(
        f"API: Request to add players by user '{identity}'. Payload: {payload.players}"
    )
    try:

        result = player_api.add_players_manually_api(
            player_strings=payload.players, app_context=app_context
        )

        if result.get("status") == "success":
            return GeneralApiResponse(
                status="success",
                message=result.get("message"),
                data={"count": result.get("count")},
            )
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

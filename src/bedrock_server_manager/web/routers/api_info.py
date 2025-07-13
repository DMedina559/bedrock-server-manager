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

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..schemas import BaseApiResponse
from ..auth_utils import get_current_user
from ..dependencies import validate_server_exists
from ...config import settings
from ...api import (
    application as app_api,
    utils as utils_api,
    system as system_api,
    player as player_api,
    info as info_api,
)
from ...api import misc as misc_api
from ...error import BSMError, UserInputError

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Pydantic Models ---
class GeneralApiResponse(BaseApiResponse):
    """A general-purpose API response model.

    Used by various informational endpoints to provide a consistent
    response structure, including a status, an optional message, and
    various optional data fields depending on the specific endpoint.
    """

    # status: str -> Inherited
    # message: Optional[str] = None -> Inherited
    data: Optional[Dict[str, Any]] = None  # Often for single item details
    servers: Optional[List[Dict[str, Any]]] = None  # For lists of server data
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Checks if a specific server's process is currently running.

    Calls :func:`~bedrock_server_manager.api.info.get_server_running_status`
    to determine the live process state.

    Args:
        server_name (str): The name of the server to check. Validated by dependency.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        GeneralApiResponse:
            - ``status``: "success"
            - ``data``: {"running": True/False}
            - ``message``: (Optional) Confirmation message.

    Example Response (Server Running):
    .. code-block:: json

        {
            "status": "success",
            "message": "Server 'MyServer' process is running.",
            "data": {
                "running": true
            },
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }

    Example Response (Server Not Running):
    .. code-block:: json

        {
            "status": "success",
            "message": "Server 'MyServer' process is not running.",
            "data": {
                "running": false
            },
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }
    """
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
    """
    Retrieves the last known status from a server's configuration file.

    This status (e.g., "RUNNING", "STOPPED") reflects the state recorded in
    the server's JSON config and may not be the live process status.
    Calls :func:`~bedrock_server_manager.api.info.get_server_config_status`.

    Args:
        server_name (str): The name of the server. Validated by dependency.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        GeneralApiResponse:
            - ``status``: "success"
            - ``data``: {"config_status": "RUNNING" | "STOPPED" | "UNKNOWN"}
            - ``message``: (Optional) Confirmation message.

    Example Response:
    .. code-block:: json

        {
            "status": "success",
            "message": "Configuration status for 'MyServer' is 'RUNNING'.",
            "data": {
                "config_status": "RUNNING"
            },
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }
    """
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
    """
    Retrieves the installed version of a specific server.

    The version is read from the server's JSON configuration file via
    :func:`~bedrock_server_manager.api.info.get_server_installed_version`.
    Returns "UNKNOWN" if not found.

    Args:
        server_name (str): The name of the server. Validated by dependency.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        GeneralApiResponse:
            - ``status``: "success"
            - ``data``: {"version": "1.20.50.01"} or {"version": "UNKNOWN"}
            - ``message``: (Optional) Confirmation message.

    Example Response:
    .. code-block:: json

        {
            "status": "success",
            "message": "Installed version for 'MyServer' is '1.20.50.01'.",
            "data": {
                "version": "1.20.50.01"
            },
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }
    """
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
    """
    Validates if a server installation exists and is minimally correct.

    Calls :func:`~bedrock_server_manager.api.utils.validate_server_exist`.
    This checks for the server directory and executable.

    Args:
        server_name (str): The name of the server to validate.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        GeneralApiResponse:
            - ``status``: "success" or "error"
            - ``message``: Detailed message about validation outcome.

    Example Response (Success):
    .. code-block:: json

        {
            "status": "success",
            "message": "Server 'MyServer' exists and is valid.",
            "data": null,
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }

    Example Response (Error):
    .. code-block:: json

        {
            "status": "error",
            "message": "Server 'NonExistentServer' is not installed or the installation is invalid.",
            "data": null,
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }
    """
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
    """
    Retrieves resource usage information for a running server process.

    Calls :func:`~bedrock_server_manager.api.system.get_bedrock_process_info`.
    Returns details like PID, CPU usage, memory, and uptime if the server
    process is found and running. Returns `null` for `process_info` if not running.

    - **server_name**: Path parameter indicating the server to query.
      It's implicitly validated by the underlying API call which will error
      if the server config/directory doesn't exist for PID lookup.
    - Requires authentication.

    Args:
        server_name (str): The name of the server.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        GeneralApiResponse:
            - ``status``: "success"
            - ``data``: {"process_info": ProcessInfoDict} or {"process_info": null}
            - ``message``: (Optional) Confirmation or status message.
              ProcessInfoDict contains "pid", "cpu_percent", "memory_mb", "uptime".

    Example Response (Process Found):
    .. code-block:: json

        {
            "status": "success",
            "message": "Process information retrieved for MyServer.",
            "data": {
                "process_info": {
                    "pid": 12345,
                    "cpu_percent": 10.5,
                    "memory_mb": 256.5,
                    "uptime": "2 days, 4:30:15"
                }
            },
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }

    Example Response (Process Not Found):
    .. code-block:: json

        {
            "status": "success",
            "message": "Server process 'MyServer' not found or is inaccessible.",
            "data": {
                "process_info": null
            },
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }
    """
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
    "/api/players/scan", response_model=GeneralApiResponse, tags=["Global Players API"]
)
async def scan_players_api_route(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Scans all server logs to discover and update the central player database.

    Calls :func:`~bedrock_server_manager.api.player.scan_and_update_player_db_api`.
    This is a global action not tied to a specific server.

    Args:
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        GeneralApiResponse:
            - ``status``: "success" or "error"
            - ``message``: Summary of the scan operation.
            - ``data``: (On success) Contains detailed scan results, including counts
              of entries found, unique players, saved players, and any scan errors.
              The structure of `data` would be the `details` field from the
              `scan_and_update_player_db_api` response.

    Example Response (Success):
    .. code-block:: json

        {
            "status": "success",
            "message": "Player DB update complete. Entries found: 10. Unique: 5. Saved: 2.",
            "data": {
                "total_entries_in_logs": 10,
                "unique_players_submitted_for_saving": 5,
                "actually_saved_or_updated_in_db": 2,
                "scan_errors": []
            },
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Request to scan logs for players by user '{identity}'.")
    try:
        result = player_api.scan_and_update_player_db_api()
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieves the list of all known players from the central player database.

    Calls :func:`~bedrock_server_manager.api.player.get_all_known_players_api`.
    The player data is read from the application's main `players.json` file.

        - Requires authentication.
        - Returns a list of player objects (in the `players` field of the response),
          each typically containing "name" and "xuid".
        - If `players.json` is not found or empty, "players" will be an empty list.

    Args:
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        GeneralApiResponse:
            - ``status``: "success" or "error"
            - ``players``: List of player dictionaries (e.g., `[{"name": "Player1", "xuid": "123"}, ...]`)
            - ``message``: (Optional) Confirmation or status message.

    Example Response:
    .. code-block:: json

        {
            "status": "success",
            "message": "Retrieved 2 known players.",
            "data": null,
            "servers": null,
            "info": null,
            "players": [
                {
                    "name": "PlayerOne",
                    "xuid": "1234567890123456"
                },
                {
                    "name": "PlayerTwo",
                    "xuid": "9876543210987654"
                }
            ],
            "files_deleted": null,
            "files_kept": null
        }
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Request to retrieve all players by user '{identity}'.")

    try:
        result_dict = player_api.get_all_known_players_api()

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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Prunes old downloaded server archives from a specified cache subdirectory.

    Calls :func:`~bedrock_server_manager.api.misc.prune_download_cache`.
    The target directory is relative to the main download cache path.

    - **Request body**: Expects a :class:`.PruneDownloadsPayload` specifying the
      `directory` (e.g., "stable", "preview") and an optional `keep` count.
    - Requires authentication.

    Args:
        payload (PruneDownloadsPayload): Specifies directory and keep count.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        GeneralApiResponse:
            - ``status``: "success", "error", or "skipped"
            - ``message``: Outcome of the prune operation.
            - ``files_deleted``: (Optional) Number of files deleted.
            - ``files_kept``: (Optional) Number of files kept.

    Example Request Body:
    .. code-block:: json

        {
            "directory": "stable",
            "keep": 2
        }

    Example Response (Success):
    .. code-block:: json

        {
            "status": "success",
            "message": "Download cache pruned successfully for 'stable'.",
            "data": null,
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": 5,
            "files_kept": 2
        }
    """
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
    """
    Retrieves a list of all detected server instances with their status and version.

    Calls :func:`~bedrock_server_manager.api.application.get_all_servers_data`.
    This provides a summary for each managed server.

    Args:
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        GeneralApiResponse:
            - ``status``: "success" or "error"
            - ``servers``: List of server data dictionaries. Each dict contains
              "name", "status", "version", etc.
            - ``message``: (Optional) Message, especially if errors occurred during scan.

    Example Response:
    .. code-block:: json

        {
            "status": "success",
            "message": null,
            "data": null,
            "servers": [
                {
                    "name": "MyServer1",
                    "status": "RUNNING",
                    "version": "1.20.50.01",
                    "description": "Main survival server"
                },
                {
                    "name": "CreativeBuild",
                    "status": "STOPPED",
                    "version": "1.20.50.01",
                    "description": "Creative mode server"
                }
            ],
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }
    """
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
    """
    Retrieves general system and application information.

    Calls :func:`~bedrock_server_manager.api.utils.get_system_and_app_info`.
    This includes OS type, application version, and key directory paths.
    This endpoint does not require authentication.

    Returns:
        GeneralApiResponse:
            - ``status``: "success" or "error"
            - ``info``: Dictionary containing system and app info.
            - ``message``: (Optional) Message.

    Example Response:
    .. code-block:: json

        {
            "status": "success",
            "message": null,
            "data": null,
            "servers": null,
            "info": {
                "application_name": "Bedrock Server Manager",
                "version": "1.0.0",
                "os_type": "Linux",
                "base_directory": "/opt/bsm/servers",
                "content_directory": "/opt/bsm/content",
                "config_directory": "/opt/bsm/config"
            },
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }
    """
    logger.debug("API: Request for system and app info.")
    try:
        result = utils_api.get_system_and_app_info()
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
    payload: AddPlayersPayload, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Manually adds or updates player entries in the central player database.

    Calls :func:`~bedrock_server_manager.api.player.add_players_manually_api`.
    Each player string in the payload should be in "gamertag:xuid" format.

    - **Request body**: Expects an :class:`.AddPlayersPayload` containing a list
      of player strings.
    - Requires authentication.

    Args:
        payload (AddPlayersPayload): List of player strings to add.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        GeneralApiResponse:
            - ``status``: "success" or "error"
            - ``message``: Outcome of the add operation.
            - ``data``: (On success) Contains "count" of players processed.

    Example Request Body:
    .. code-block:: json

        {
            "players": ["PlayerThree:1122334455667788", "PlayerFour:2233445566778899"]
        }

    Example Response (Success):
    .. code-block:: json

        {
            "status": "success",
            "message": "2 player entries processed and saved/updated.",
            "data": {"count": 2},
            "servers": null,
            "info": null,
            "players": null,
            "files_deleted": null,
            "files_kept": null
        }
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Request to add players by user '{identity}'. Payload: {payload.players}"
    )

    try:

        result = player_api.add_players_manually_api(player_strings=payload.players)

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

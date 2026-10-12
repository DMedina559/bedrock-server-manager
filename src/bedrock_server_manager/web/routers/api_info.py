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
a server. Responses are generally structured using the :class:`.BaseApiResponse` model.
"""

import asyncio
import logging
import os

import aiofiles.ospath
from fastapi import APIRouter, Depends, HTTPException, status

from bedrock_server_manager.api.models import (
    AddPlayersManuallyRequest,
    GetAllKnownPlayersRequest,
    GetAllServersDataRequest,
    GetBedrockProcessInfoRequest,
    GetServerRunningStatusRequest,
    GetSystemAndAppInfoRequest,
    PruneDownloadCacheRequest,
    ScanAndUpdatePlayerDbRequest,
)

from ...api import application as app_api
from ...api import misc as misc_api
from ...api import player as player_api
from ...api import system as system_api
from ...api.models.health import (
    GetApplicationHealthRequest,
    GetApplicationHealthResponse,
)
from ...api.models.metrics import (
    GetApplicationMetricsRequest,
    GetApplicationMetricsResponse,
)
from ...context import AppContext
from ...error import BSMError
from ..deps import (
    get_admin_user,
    get_app_context,
    get_current_user,
    get_moderator_user,
    validate_server_exists,
)
from ..schemas import (
    AddPlayersPayload,
    AddPlayersResponse,
    AppInfoResponse,
    BaseApiResponse,
    PlayerListResponse,
    PruneDownloadsPayload,
    PruneDownloadsResponse,
    ServerProcessInfoResponse,
    ServerRunningStatusResponse,
    ServersListResponse,
    ThemeListResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Server Info Endpoints ---
@router.get(
    "/api/server/{server_name}/status",
    operation_id="get_server_status",
    tags=["Server Processes"],
    response_model=ServerRunningStatusResponse,
)
async def get_server_running_status(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> ServerRunningStatusResponse:
    """
    Checks if a specific server's process is currently running.
    """
    identity = current_user.username
    logger.debug(
        "Request for running status for server '%s' by user '%s'.",
        server_name,
        identity,
    )
    result = await system_api.get_server_running_status(
        request=GetServerRunningStatusRequest(server_name=server_name),
        app_context=app_context,
    )
    return ServerRunningStatusResponse(
        status="success",
        running=bool(result.is_running),
        epoch=result.epoch,
        revision=result.revision,
        message=result.message,
    )


@router.get(
    "/api/server/{server_name}/validate",
    operation_id="validate_server",
    tags=["Server Management"],
    response_model=BaseApiResponse,
)
async def get_validate_server(
    server_name: str,
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    """
    Validates if a server installation exists and is minimally correct.
    """
    identity = current_user.username
    logger.debug("Request to validate server '%s' by user '%s'.", server_name, identity)
    from ...utils.server import validate_server

    if await validate_server(server_name=server_name, app_context=app_context):
        return BaseApiResponse(
            status="success", message=f"Server '{server_name}' exists and is valid."
        )
    else:
        # This case handles when the underlying API returns an error status
        # without raising an exception itself.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' is not installed or the installation is invalid.",
        )


@router.get(
    "/api/server/{server_name}/process_info",
    operation_id="get_server_process_info",
    tags=["Server Processes"],
    response_model=ServerProcessInfoResponse,
)
async def get_server_process_info(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> ServerProcessInfoResponse:
    """
    Retrieves resource usage information for a running server process.
    """
    identity = current_user.username
    logger.debug("Process info request for '%s' by user '%s'.", server_name, identity)
    result = await system_api.get_bedrock_process_info(
        request=GetBedrockProcessInfoRequest(server_name=server_name),
        app_context=app_context,
    )

    return ServerProcessInfoResponse(
        status="success",
        process_info=result.process_info,
        epoch=result.epoch,
        revision=result.revision,
        message=result.message,
    )


@router.put(
    "/api/players/scan",
    operation_id="scan_players",
    tags=["Player Management"],
    response_model=AddPlayersResponse,
)
async def put_scan_players(
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> AddPlayersResponse:
    """
    Scans all server logs to discover and update the central player database.
    """
    identity = current_user.username
    logger.info("Request to scan logs for players by user '%s'.", identity)
    result = await player_api.scan_and_update_player_db(
        request=ScanAndUpdatePlayerDbRequest(), app_context=app_context
    )
    return AddPlayersResponse(
        status="success",
        message=result.message,
        details=result.details,
    )


@router.get(
    "/api/players/get",
    operation_id="list_players",
    tags=["Player Management"],
    response_model=PlayerListResponse,
)
async def get_all_players(
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> PlayerListResponse:
    """
    Retrieves the list of all known players from the central player database.
    """
    identity = current_user.username
    logger.debug("Request to retrieve all players by user '%s'.", identity)
    result_dict = await player_api.get_all_known_players(
        request=GetAllKnownPlayersRequest(), app_context=app_context
    )

    logger.debug(
        "API Get All Players: Successfully retrieved %s players. Message: %s",
        len(result_dict.players),
        result_dict.message,
    )
    return PlayerListResponse(
        status="success",
        players=result_dict.players,
        message=result_dict.message,
    )


@router.put(
    "/api/downloads/prune",
    operation_id="prune_downloads",
    tags=["Downloads"],
    response_model=PruneDownloadsResponse,
)
async def put_prune_downloads(
    payload: PruneDownloadsPayload,
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> PruneDownloadsResponse:
    """
    Prunes old downloaded server archives from a specified cache subdirectory.
    """
    identity = current_user.username
    logger.info("Download cache cleanup requested by user '%s'.", identity)
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
            "API Prune Downloads: Security violation - Invalid directory path '%s'.",
            payload.directory,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid directory path: Path is outside the allowed download cache base directory.",
        )

    if not await aiofiles.ospath.isdir(full_download_dir_path):
        logger.warning(
            "API Prune Downloads: Target cache directory not found: %s (from relative: '%s')",
            full_download_dir_path,
            payload.directory,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target cache directory not found.",
        )

    result = await misc_api.prune_download_cache(
        request=PruneDownloadCacheRequest(
            download_dir=full_download_dir_path, keep_count=payload.keep
        ),
        app_context=app_context,
    )

    return PruneDownloadsResponse(
        status=result.status,
        message=result.message,
        files_deleted=len(result.result.deleted),
        files_kept=len(result.result.retained),
        failures=result.result.failures,
    )


@router.get(
    "/api/servers",
    operation_id="list_servers",
    tags=["Server Management"],
    response_model=ServersListResponse,
)
async def get_servers_list(
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> ServersListResponse:
    """
    Retrieves a list of all detected server instances with their status and version.
    """
    identity = current_user.username
    logger.debug("Request for all servers list by user '%s'.", identity)
    result = await app_api.get_all_servers_data(
        request=GetAllServersDataRequest(), app_context=app_context
    )
    return ServersListResponse(
        status=result.status,
        errors=result.errors,
        message=result.message,
        servers=result.servers,
        epoch=result.epoch,
        revision=result.revision,
    )


@router.get(
    "/api/info",
    operation_id="get_system_info",
    tags=["Application"],
    response_model=AppInfoResponse,
)
async def get_system_info(
    app_context: AppContext = Depends(get_app_context),
) -> AppInfoResponse:
    """
    Retrieves general system and application information.
    """
    logger.debug("Request for system and app info.")
    from ...api.application import get_system_and_app_info

    result = get_system_and_app_info(
        request=GetSystemAndAppInfoRequest(), app_context=app_context
    ).model_dump(mode="python")
    if result.get("status") == "success":
        # the dictionary is already flattened, pass the entire result minus the status
        return AppInfoResponse(
            status="success",
            info={k: v for k, v in result.items() if k != "status"},
        )
    else:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "Failed to retrieve system info."),
        )


@router.get(
    "/api/info/themes",
    operation_id="list_themes",
    tags=["Appearance"],
    response_model=ThemeListResponse,
)
async def get_themes(
    app_context: AppContext = Depends(get_app_context),
) -> ThemeListResponse:
    """
    Retrieves a list of available themes (standard and custom).
    """
    logger.debug("Request for available themes.")
    STANDARD_THEMES = [
        "default",
        "light",
        "gradient",
        "black",
        "red",
        "green",
        "blue",
        "yellow",
        "pink",
    ]
    themes = set(STANDARD_THEMES)
    themes_path = app_context.settings.get("paths.themes")

    if themes_path and await aiofiles.ospath.isdir(themes_path):

        def list_themes():
            return os.listdir(themes_path)

        filenames = await asyncio.to_thread(list_themes)
        for filename in filenames:
            if filename.endswith(".css"):
                themes.add(filename[:-4])  # Remove .css extension

    # Sort the themes: default first, then alphabetically
    sorted_themes = sorted(list(themes))
    if "default" in sorted_themes:
        sorted_themes.remove("default")
        sorted_themes.insert(0, "default")

    return ThemeListResponse(status="success", themes=sorted_themes)


@router.post(
    "/api/players/add",
    operation_id="add_players",
    tags=["Player Management"],
    response_model=AddPlayersResponse,
)
async def post_add_players(
    payload: AddPlayersPayload,
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> AddPlayersResponse:
    """
    Manually adds or updates player entries in the central player database.
    """
    identity = current_user.username
    logger.info(
        "Player registration requested by user '%s' (%s entries).",
        identity,
        len(payload.players),
    )
    result = await player_api.add_players_manually(
        request=AddPlayersManuallyRequest(player_strings=payload.players),
        app_context=app_context,
    )

    return AddPlayersResponse(
        status="success",
        message=result.message,
        count=result.count,
        submitted_count=result.submitted_count,
        parsed_count=result.parsed_count,
        unique_count=result.unique_count,
    )


@router.get(
    "/api/metrics",
    operation_id="get_application_metrics",
    tags=["Application"],
    response_model=GetApplicationMetricsResponse,
)
async def get_application_metrics(
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> GetApplicationMetricsResponse:
    """Authenticated application and host performance observations."""
    return await system_api.get_application_metrics(
        GetApplicationMetricsRequest(), app_context=app_context
    )


@router.get(
    "/api/health",
    operation_id="get_application_health",
    tags=["Application"],
    response_model=GetApplicationHealthResponse,
)
async def get_application_health(
    current_user: UserResponse = Depends(get_current_user),
    app_context: AppContext = Depends(get_app_context),
) -> GetApplicationHealthResponse:
    """Dependency readiness. A degraded response remains HTTP 200 for UI clients."""
    return await system_api.get_application_health(
        GetApplicationHealthRequest(), app_context=app_context
    )

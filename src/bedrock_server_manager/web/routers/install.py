import logging
import os

import aiofiles.ospath
from fastapi import APIRouter, Depends, HTTPException, status

from bedrock_server_manager.api.models import (
    DeleteServerDataRequest,
    InstallNewServerRequest,
    PruneDownloadCacheRequest,
)

from ...api import install as install_api
from ...api import misc as misc_api
from ...api import server as server_api
from ...context import AppContext
from ...core.system import find_files
from ...error import BSMError
from ..deps import get_admin_user, get_app_context, get_moderator_user
from ..schemas import (
    CustomZipsResponse,
    InstallationAcceptedResponse,
    InstallConfirmationResponse,
    InstallServerPayload,
    InstallServerResponse,
    PruneDownloadsPayload,
    PruneDownloadsResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/api/downloads/list",
    operation_id="list_downloads",
    tags=["Downloads"],
    response_model=CustomZipsResponse,
)
async def get_custom_zips(
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> CustomZipsResponse:
    download_dir = app_context.settings.get("paths.downloads")

    custom_dir = os.path.join(download_dir, "custom")
    if not await aiofiles.ospath.isdir(custom_dir):
        return CustomZipsResponse(status="success", custom_zips=[])

    custom_zips_paths = await find_files(custom_dir, "*.zip")
    custom_zips = [os.path.basename(str(p)) for p in custom_zips_paths]
    return CustomZipsResponse(status="success", custom_zips=custom_zips)


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


@router.post(
    "/api/server/install",
    operation_id="install_server",
    tags=["Server Management"],
    response_model=InstallServerResponse,
)
async def post_install_server(  # noqa: C901
    payload: InstallServerPayload,
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> InstallServerResponse:
    identity = current_user.username
    logger.info(
        "New server install request from user '%s' for server '%s'.",
        identity,
        payload.server_name,
    )
    from ...utils.server import core_validate_server_name_format, validate_server

    core_validate_server_name_format(payload.server_name)

    server_zip_path = None
    if payload.server_version.upper() == "CUSTOM":
        if not payload.server_zip_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="server_zip_path is required for CUSTOM version.",
            )
        if (
            os.path.basename(payload.server_zip_path) != payload.server_zip_path
            or "\\" in payload.server_zip_path
        ):
            raise HTTPException(
                status_code=400,
                detail="Select a ZIP filename from the custom downloads directory.",
            )
        download_dir = app_context.settings.get("paths.downloads")
        custom_dir = os.path.join(download_dir, "custom")
        custom_dir = os.path.realpath(custom_dir)
        server_zip_path = os.path.realpath(
            os.path.join(custom_dir, payload.server_zip_path)
        )
        if os.path.commonpath([custom_dir, server_zip_path]) != custom_dir:
            raise HTTPException(
                status_code=400,
                detail="Custom ZIP must be inside the downloads directory.",
            )
        if not await aiofiles.ospath.isfile(server_zip_path):
            raise HTTPException(status_code=404, detail="Custom ZIP file not found.")

    server_exists = await validate_server(payload.server_name, app_context=app_context)

    if not payload.overwrite and server_exists:
        logger.debug(
            "Server '%s' already exists. Confirmation needed.", payload.server_name
        )

        return InstallConfirmationResponse(
            status="confirm_needed",
            message=f"Server '{payload.server_name}' already exists. Overwrite?",
            server_name=payload.server_name,
        )

    if payload.overwrite and server_exists:
        logger.info(
            "Overwrite flag set for existing server '%s'. Deleting first.",
            payload.server_name,
        )
        await server_api.delete_server_data(
            request=DeleteServerDataRequest(server_name=payload.server_name),
            app_context=app_context,
        )
        logger.debug(
            "Successfully deleted existing server '%s' for overwrite.",
            payload.server_name,
        )

    task_id = await app_context.task_manager.run_task(
        install_api.install_new_server,
        username=current_user.username,
        app_context=app_context,
        request=InstallNewServerRequest(
            server_name=payload.server_name,
            target_version=payload.server_version,
            server_zip_path=server_zip_path,
        ),
    )

    return InstallationAcceptedResponse(
        status="accepted",
        message="Server installation has started.",
        task_id=task_id,
        server_name=payload.server_name,
    )

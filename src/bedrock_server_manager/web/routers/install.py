import logging
import os

import aiofiles.ospath
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    DeleteServerDataRequest,
    InstallNewServerRequest,
)

from ...api import install as install_api
from ...api import server as server_api
from ...context import AppContext
from ...core.system import find_files
from ...error import AppFileNotFoundError, BSMError, UserInputError
from ...logging import log_operation_error
from ..deps import get_admin_user, get_app_context, get_moderator_user
from ..schemas import (
    CustomZipsResponse,
    InstallServerPayload,
    InstallServerResponse,
    UserResponse,
)
from ..schemas.install import InstallationAcceptedResponse, InstallConfirmationResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/api/downloads/list",
    operation_id="list_downloads",
    response_model=CustomZipsResponse,
    tags=["Application", "Downloads"],
)
async def get_custom_zips(
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> CustomZipsResponse:
    try:
        download_dir = app_context.settings.get("paths.downloads")

        custom_dir = os.path.join(download_dir, "custom")
        if not await aiofiles.ospath.isdir(custom_dir):
            return CustomZipsResponse(status="success", custom_zips=[])

        custom_zips_paths = await find_files(custom_dir, "*.zip")
        custom_zips = [os.path.basename(str(p)) for p in custom_zips_paths]
        return CustomZipsResponse(status="success", custom_zips=custom_zips)
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(logger, "Failed to get custom zips: %s", e, error=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve custom zips.",
        )


@router.post(
    "/api/server/install",
    operation_id="install_server",
    response_model=InstallServerResponse,
    tags=["Server Installation"],
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

    try:
        core_validate_server_name_format(payload.server_name)
    except UserInputError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    try:
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
                raise HTTPException(
                    status_code=404, detail="Custom ZIP file not found."
                )

        server_exists = await validate_server(
            payload.server_name, app_context=app_context
        )

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

    except UserInputError as e:
        logger.debug(
            "API Install Server '%s': UserInputError. %s", payload.server_name, e
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except AppFileNotFoundError:
        raise
    except BSMError as e:
        logger.debug(
            "API Install Server '%s': BSMError. %s",
            payload.server_name,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "API Install Server '%s': Unexpected error. %s",
            payload.server_name,
            e,
            error=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during server installation.",
        )

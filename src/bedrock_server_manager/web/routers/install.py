import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status

from ...api import install as install_api
from ...api import server as server_api
from ...context import AppContext
from ...core.system import find_files
from ...error import BSMError, UserInputError
from ..auth_utils import get_admin_user, get_moderator_user
from ..dependencies import get_app_context
from ..schemas import (
    CustomZipsResponse,
    InstallServerPayload,
    InstallServerResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/api/downloads/list",
    response_model=CustomZipsResponse,
    tags=["Application", "Downloads"],
)
async def get_custom_zips(
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    try:
        download_dir = app_context.settings.get("paths.downloads")
        custom_dir = os.path.join(download_dir, "custom")
        if not os.path.isdir(custom_dir):
            return CustomZipsResponse(status="success", custom_zips=[])

        custom_zips_paths = find_files(custom_dir, "*.zip")
        custom_zips = [os.path.basename(str(p)) for p in custom_zips_paths]
        return CustomZipsResponse(status="success", custom_zips=custom_zips)
    except Exception as e:
        logger.error(f"Failed to get custom zips: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve custom zips.",
        )


@router.post(
    "/api/server/install",
    response_model=InstallServerResponse,
    tags=["Server Installation"],
)
async def post_install_server(  # noqa: C901
    payload: InstallServerPayload,
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    identity = current_user.username
    logger.info(
        f"API: New server install request from user '{identity}' for server '{payload.server_name}'."
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
        server_exists = validate_server(payload.server_name, app_context=app_context)

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
            install_api.install_new_server,
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

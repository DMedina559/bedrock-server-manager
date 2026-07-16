import logging
import os

import bsm_frontend
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from ...api import application as app_api
from ...api import world as world_api
from ...context import AppContext
from ...error import (
    AppFileNotFoundError,
    BSMError,
    InvalidServerNameError,
    UserInputError,
)
from ..deps import (
    get_admin_user,
    get_app_context,
    get_moderator_user,
    validate_server_exists,
)
from ..schemas import ActionResponse, ContentListResponse, FileNamePayload, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["World Management"],
)

STATIC_DIR = bsm_frontend.get_static_dir()


@router.get(
    "/api/content/worlds",
    response_model=ContentListResponse,
    tags=["Content Management"],
)
async def get_worlds_list(
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves a list of available .mcworld template files.
    """
    identity = current_user.username
    logger.info(f"API: List available worlds request by user '{identity}'.")
    try:
        api_result = app_api.list_available_worlds_api(app_context=app_context)
        if api_result.get("status") == "success":
            full_paths = api_result.get("files", [])
            basenames = [os.path.basename(p) for p in full_paths]
            return ContentListResponse(
                status="success", files=basenames, message=api_result.get("message")
            )
        else:
            logger.warning(f"API: Error listing worlds: {api_result.get('message')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=api_result.get("message", "Failed to list worlds."),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected critical error listing worlds: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A critical server error occurred while listing worlds.",
        )


@router.post(
    "/api/server/{server_name}/world/install",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content Management"],
)
async def post_world_install(
    payload: FileNamePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to install a world from a .mcworld file to a server.
    """
    identity = current_user.username
    selected_filename = payload.filename
    logger.info(
        f"API: World install of '{selected_filename}' for '{server_name}' by user '{identity}'."
    )
    from ...utils.server import validate_server

    try:
        if not validate_server(server_name=server_name, app_context=app_context):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        content_base_dir = os.path.join(
            app_context.settings.get("paths.content"), "worlds"
        )
        full_world_file_path = os.path.normpath(
            os.path.join(content_base_dir, selected_filename)
        )

        if not os.path.abspath(full_world_file_path).startswith(
            os.path.abspath(content_base_dir) + os.sep
        ):
            logger.error(
                f"API Install World '{server_name}': Security violation - Invalid path '{selected_filename}'."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path (security check failed).",
            )

        if not os.path.isfile(full_world_file_path):
            logger.warning(
                f"API Install World '{server_name}': World file '{selected_filename}' not found at '{full_world_file_path}'."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"World file '{selected_filename}' not found for import.",
            )

        task_id = app_context.task_manager.run_task(
            world_api.import_world,
            username=current_user.username,
            server_name=server_name,
            selected_file_path=full_world_file_path,
            app_context=app_context,
        )

        return ActionResponse(
            status="pending",
            message=f"World install from '{selected_filename}' for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except HTTPException:
        raise
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Install World '{server_name}': Pre-check BSMError: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"API Install World '{server_name}': Pre-check error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error during pre-check: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/world/export",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content Management"],
)
async def post_world_export(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to export the active world of a server to a .mcworld file.
    """
    identity = current_user.username
    logger.info(
        f"API: World export requested for '{server_name}' by user '{identity}'."
    )
    from ...utils.server import validate_server

    try:
        if not validate_server(server_name=server_name, app_context=app_context):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        task_id = app_context.task_manager.run_task(
            world_api.export_world,
            username=current_user.username,
            server_name=server_name,
            app_context=app_context,
        )

        return ActionResponse(
            status="pending",
            message=f"World export for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except HTTPException:
        raise
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"API Export World '{server_name}': Pre-check error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error during pre-check: {str(e)}",
        )


@router.delete(
    "/api/server/{server_name}/world/reset",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Server Management"],
)
async def delete_world_reset(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to reset a server's world.
    """
    identity = current_user.username
    logger.info(f"API: World reset requested for '{server_name}' by user '{identity}'.")
    from ...utils.server import validate_server

    try:
        if not validate_server(server_name=server_name, app_context=app_context):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        task_id = app_context.task_manager.run_task(
            world_api.reset_world,
            username=current_user.username,
            server_name=server_name,
            app_context=app_context,
        )

        return ActionResponse(
            status="pending",
            message=f"World reset for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except HTTPException:
        raise
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"API Reset World '{server_name}': Pre-check error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error during pre-check: {str(e)}",
        )


@router.get(
    "/api/server/{server_name}/world/icon",
    response_class=FileResponse,
)
async def get_world_icon(
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
):
    """Serves the `world_icon.jpeg` for a server, or a default icon if not found."""
    logger.debug(f"Request to serve world icon for server '{server_name}'.")
    try:
        server = app_context.get_server(server_name)
        icon_path = server.world_icon_filesystem_path

        if server.has_world_icon() and icon_path and os.path.isfile(icon_path):
            logger.debug(f"Serving world icon from path: {icon_path}")
            return FileResponse(icon_path, media_type="image/jpeg")
        else:

            logger.info(
                f"World icon for '{server_name}' not found at '{icon_path}'. Serving default."
            )
            raise AppFileNotFoundError(str(icon_path), "World icon")

    except (
        AppFileNotFoundError,
        InvalidServerNameError,
        BSMError,
    ) as e:
        if not isinstance(e, AppFileNotFoundError):
            logger.error(
                f"Error preparing to serve world icon for '{server_name}': {e}",
                exc_info=True,
            )

        default_icon_path = os.path.join(STATIC_DIR, "image", "icon", "favicon.ico")
        if os.path.isfile(default_icon_path):
            logger.debug(
                f"Serving default world icon (favicon.ico) from: {default_icon_path}"
            )
            return FileResponse(
                default_icon_path, media_type="image/vnd.microsoft.icon"
            )
        else:
            logger.error(
                f"Default world icon (favicon.ico) not found at {default_icon_path}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default world icon not found.",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error serving world icon for '{server_name}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error serving icon.",
        )

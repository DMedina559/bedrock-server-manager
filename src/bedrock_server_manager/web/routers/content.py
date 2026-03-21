# src/bedrock_server_manager/web/routers/content.py
"""
API routes for content management.

This module provides endpoints for listing, installing, and managing content
such as worlds (.mcworld) and addons (.mcaddon, .mcpack) for Bedrock servers.
It includes both HTML view routes and JSON API routes.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status

from ...api import addon as addon_api
from ...api import application as app_api
from ...api import utils as utils_api
from ...api import world as world_api
from ...context import AppContext
from ...error import BSMError, UserInputError
from ..auth_utils import get_admin_user, get_moderator_user
from ..dependencies import get_app_context, validate_server_exists
from ..schemas import ActionResponse, ContentListResponse, FileNamePayload, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# --- API Routes ---
@router.get(
    "/api/content/worlds",
    response_model=ContentListResponse,
    tags=["Content API"],
)
async def list_worlds_api_route(
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
    except Exception as e:
        logger.error(
            f"API: Unexpected critical error listing worlds: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A critical server error occurred while listing worlds.",
        )


@router.get(
    "/api/content/addons",
    response_model=ContentListResponse,
    tags=["Content API"],
)
async def list_addons_api_route(
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves a list of available .mcaddon or .mcpack template files.
    """
    identity = current_user.username
    logger.info(f"API: List available addons request by user '{identity}'.")
    try:
        api_result = app_api.list_available_addons_api(app_context=app_context)
        if api_result.get("status") == "success":
            full_paths = api_result.get("files", [])
            basenames = [os.path.basename(p) for p in full_paths]
            return ContentListResponse(
                status="success", files=basenames, message=api_result.get("message")
            )
        else:
            logger.warning(f"API: Error listing addons: {api_result.get('message')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=api_result.get("message", "Failed to list addons."),
            )
    except Exception as e:
        logger.error(
            f"API: Unexpected critical error listing addons: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A critical server error occurred while listing addons.",
        )


@router.post(
    "/api/server/{server_name}/world/install",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def install_world_api_route(
    payload: FileNamePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to install a world from a .mcworld file to a server.

    The selected world file must exist in the application's content/worlds directory.
    The server will be stopped before import and restarted after if the operation is successful.
    """
    identity = current_user.username
    selected_filename = payload.filename
    logger.info(
        f"API: World install of '{selected_filename}' for '{server_name}' by user '{identity}'."
    )
    try:
        if not utils_api.validate_server_exist(
            server_name=server_name, app_context=app_context
        ):
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
    tags=["Content API"],
)
async def export_world_api_route(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to export the active world of a server to a .mcworld file.

    The exported file will be saved in the application's content/worlds directory.
    The server will be stopped before export and restarted after.
    """
    identity = current_user.username
    logger.info(
        f"API: World export requested for '{server_name}' by user '{identity}'."
    )
    try:
        if not utils_api.validate_server_exist(
            server_name=server_name, app_context=app_context
        ):
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
    except HTTPException:  # Re-raise HTTPExceptions directly
        raise
    except UserInputError as e:  # From validate_server_exist
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:  # Catch any other pre-check errors
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
    tags=["Content API"],
)
async def reset_world_api_route(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to reset a server's world.

    This is a destructive operation: the current active world directory is deleted.
    The server will be stopped before the reset and restarted afterwards, which
    will trigger the generation of a new world based on server properties.
    """
    identity = current_user.username
    logger.info(f"API: World reset requested for '{server_name}' by user '{identity}'.")
    try:
        # Validate server existence before queueing task
        if not utils_api.validate_server_exist(
            server_name=server_name, app_context=app_context
        ):
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
    except HTTPException:  # Re-raise HTTPExceptions directly
        raise
    except UserInputError as e:  # From validate_server_exist
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:  # Catch any other pre-check errors
        logger.error(
            f"API Reset World '{server_name}': Pre-check error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error during pre-check: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/install",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def install_addon_api_route(
    payload: FileNamePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to install an addon from a .mcaddon or .mcpack file to a server.

    The selected addon file must exist in the application's content/addons directory.
    The server will be stopped before installation and restarted after if the operation is successful.
    """
    identity = current_user.username
    selected_filename = payload.filename
    logger.info(
        f"API: Addon install of '{selected_filename}' for '{server_name}' by user '{identity}'."
    )
    try:
        if not utils_api.validate_server_exist(
            server_name=server_name, app_context=app_context
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        content_base_dir = os.path.join(
            app_context.settings.get("paths.content"), "addons"
        )
        full_addon_file_path = os.path.normpath(
            os.path.join(content_base_dir, selected_filename)
        )

        if not os.path.abspath(full_addon_file_path).startswith(
            os.path.abspath(content_base_dir) + os.sep
        ):
            logger.error(
                f"API Install Addon '{server_name}': Security violation - Invalid path '{selected_filename}'."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path (security check failed).",
            )

        if not os.path.isfile(full_addon_file_path):
            logger.warning(
                f"API Install Addon '{server_name}': Addon file '{selected_filename}' not found at '{full_addon_file_path}'."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Addon file '{selected_filename}' not found for import.",
            )

        task_id = app_context.task_manager.run_task(
            addon_api.import_addon,
            username=current_user.username,
            server_name=server_name,
            addon_file_path=full_addon_file_path,
            app_context=app_context,
        )

        return ActionResponse(
            status="pending",
            message=f"Addon install from '{selected_filename}' for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except HTTPException:  # Re-raise HTTPExceptions directly
        raise
    except UserInputError as e:  # From validate_server_exist or other pre-checks
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Install Addon '{server_name}': Pre-check BSMError: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:  # Catch any other pre-check errors
        logger.error(
            f"API Install Addon '{server_name}': Pre-check error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error during pre-check: {str(e)}",
        )

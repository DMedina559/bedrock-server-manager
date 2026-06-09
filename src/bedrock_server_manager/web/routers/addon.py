"""
Router for addon-related endpoints.
"""

import logging
import os

import bsm_frontend
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from ...api import addon as addon_api
from ...context import AppContext
from ...error import AppFileNotFoundError, BSMError, UserInputError
from ..auth_utils import get_admin_user, get_moderator_user
from ..dependencies import get_app_context, validate_server_exists
from ..schemas.addon import (
    AddonActionPayload,
    AddonListResponse,
    AddonReorderPayload,
    AddonSubpackPayload,
)
from ..schemas.base import ActionResponse
from ..schemas.system import FileNamePayload
from ..schemas.users import UserResponse

logger = logging.getLogger(__name__)
router = APIRouter()
STATIC_DIR = bsm_frontend.get_static_dir()


@router.get(
    "/api/content/addons",
    response_model=dict,
    tags=["Content API"],
)
async def get_addons(
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves a list of available .mcaddon or .mcpack template files.
    """
    identity = current_user.username
    logger.info(f"API: List available addons request by user '{identity}'.")
    try:
        api_result = addon_api.list_available_addons(app_context=app_context)

        if api_result.get("status") == "success":
            # Extract just the filenames
            basenames = [os.path.basename(f) for f in api_result.get("files", [])]
            return {"status": "success", "files": basenames}
        else:
            logger.warning(f"API: Error listing addons: {api_result.get('message')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=api_result.get("message", "Failed to list addons."),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected critical error listing addons: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A critical server error occurred while listing addons.",
        )


@router.get(
    "/api/server/{server_name}/addons",
    response_model=AddonListResponse,
    tags=["Content API"],
)
async def get_server_addons(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Retrieves a list of addons installed on a server's active world.
    """
    identity = current_user.username
    logger.info(
        f"API: List world addons for '{server_name}' requested by user '{identity}'."
    )
    try:
        result = addon_api.list_world_addons(server_name, app_context)
        return AddonListResponse(status="success", addons=result.get("addons"))
    except Exception as e:
        logger.error(
            f"API List Server Addons '{server_name}': Error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/enable",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def post_enable_addon(
    payload: AddonActionPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to enable an addon on a server.
    """
    identity = current_user.username
    logger.info(
        f"API: Enable addon for '{server_name}' requested by user '{identity}'."
    )
    try:
        task_id = app_context.task_manager.run_task(
            addon_api.enable_addon,
            username=current_user.username,
            server_name=server_name,
            pack_uuid=payload.pack_uuid,
            pack_type=payload.pack_type,
            app_context=app_context,
        )
        return ActionResponse(
            status="pending",
            message=f"Addon enable for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except Exception as e:
        logger.error(
            f"API Enable Server Addon '{server_name}': Error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/disable",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def post_disable_addon(
    payload: AddonActionPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to disable an addon on a server.
    """
    identity = current_user.username
    logger.info(
        f"API: Disable addon for '{server_name}' requested by user '{identity}'."
    )
    try:
        task_id = app_context.task_manager.run_task(
            addon_api.disable_addon,
            username=current_user.username,
            server_name=server_name,
            pack_uuid=payload.pack_uuid,
            pack_type=payload.pack_type,
            app_context=app_context,
        )
        return ActionResponse(
            status="pending",
            message=f"Addon disable for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except Exception as e:
        logger.error(
            f"API Disable Server Addon '{server_name}': Error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/subpack",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def post_update_addon_subpack(
    payload: AddonSubpackPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to update an addon's active subpack.
    """
    identity = current_user.username
    logger.info(
        f"API: Update addon subpack for '{server_name}' requested by user '{identity}'."
    )
    try:
        subpack_name = payload.subpack_name
        if not subpack_name:
            # Fallback for dynamic keys
            payload_dict = payload.model_dump(exclude_unset=True)
            dynamic_key = f"subpack_{payload.pack_uuid}"
            if dynamic_key in payload_dict:
                subpack_name = payload_dict[dynamic_key]

        task_id = app_context.task_manager.run_task(
            addon_api.update_addon_subpack,
            username=current_user.username,
            server_name=server_name,
            pack_uuid=payload.pack_uuid,
            pack_type=payload.pack_type,
            subpack_name=subpack_name,
            app_context=app_context,
        )
        return ActionResponse(
            status="pending",
            message=f"Addon subpack update for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except Exception as e:
        logger.error(
            f"API Update Server Addon Subpack '{server_name}': Error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.delete(
    "/api/server/{server_name}/addon/uninstall",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def delete_uninstall_addon(
    payload: AddonActionPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to uninstall an addon on a server.
    """
    identity = current_user.username
    logger.info(
        f"API: Uninstall addon for '{server_name}' requested by user '{identity}'."
    )
    try:
        task_id = app_context.task_manager.run_task(
            addon_api.uninstall_addon,
            username=current_user.username,
            server_name=server_name,
            pack_uuid=payload.pack_uuid,
            pack_type=payload.pack_type,
            app_context=app_context,
        )
        return ActionResponse(
            status="pending",
            message=f"Addon uninstall for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except Exception as e:
        logger.error(
            f"API Uninstall Server Addon '{server_name}': Error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/reorder",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def post_reorder_addons(
    payload: AddonReorderPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to reorder active addons on a server.
    """
    identity = current_user.username
    logger.info(
        f"API: Reorder addons for '{server_name}' requested by user '{identity}'."
    )
    try:
        task_id = app_context.task_manager.run_task(
            addon_api.reorder_addons,
            username=current_user.username,
            server_name=server_name,
            uuids=payload.uuids,
            pack_type=payload.pack_type,
            app_context=app_context,
        )
        return ActionResponse(
            status="pending",
            message=f"Addon reorder for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except Exception as e:
        logger.error(
            f"API Reorder Server Addons '{server_name}': Error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/install",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def post_install_addon(
    payload: FileNamePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates a background task to install an addon from a .mcaddon or .mcpack file to a server.
    """
    identity = current_user.username
    selected_filename = payload.filename
    logger.info(
        f"API: Addon install of '{selected_filename}' for '{server_name}' by user '{identity}'."
    )
    from ...utils.server import validate_server

    try:
        if not validate_server(server_name=server_name, app_context=app_context):
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
    except HTTPException:
        raise
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API Install Addon '{server_name}': Pre-check BSMError: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Install Addon '{server_name}': Pre-check error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error during pre-check: {str(e)}",
        )


@router.get(
    "/api/server/{server_name}/addon/icon",
    tags=["Server Info API"],
)
async def get_server_addon_icon(
    server_name: str = Depends(validate_server_exists),
    pack_type: str = Query(...),
    uuid: str = Query(...),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Serves the pack_icon.png image file for a specified addon, or a default icon if not found.
    """
    logger.debug(f"API: Get addon icon for '{server_name}' requested.")

    try:
        result = addon_api.list_world_addons(server_name, app_context)

        # Determine the key to search in based on pack_type
        pack_key = f"{pack_type}_packs"
        addons_data = result.get("addons", {})
        packs = addons_data.get(pack_key, [])

        icon_path = None
        for pack in packs:
            if pack.get("uuid") == uuid and pack.get("icon"):
                icon_path = pack.get("icon")
                break

        if icon_path and os.path.exists(icon_path):
            return FileResponse(icon_path, media_type="image/png")

        logger.info(
            f"Addon icon not found for uuid '{uuid}'. Serving default world icon."
        )
        raise AppFileNotFoundError("Addon Icon not found", "Addon Icon")

    except (AppFileNotFoundError, HTTPException):
        # Fallback to the default world icon
        default_icon_path = os.path.join(STATIC_DIR, "image", "icon", "favicon.ico")
        if os.path.isfile(default_icon_path):
            return FileResponse(
                default_icon_path, media_type="image/vnd.microsoft.icon"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default icon not found.",
            )
    except Exception as e:
        logger.error(
            f"API Get Server Addon Icon '{server_name}': Error: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )

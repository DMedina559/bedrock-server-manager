"""
Router for addon-related endpoints.
"""

import logging
import os

import aiofiles.ospath
import bsm_frontend
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    DisableAddonRequest,
    EnableAddonRequest,
    ImportAddonRequest,
    ListAvailableAddonsRequest,
    ListAvailableAddonsResponse,
    ListInstalledAddonsRequest,
    ReorderAddonsRequest,
    UninstallAddonRequest,
    UpdateSubpackRequest,
)

from ...api import addon as addon_api
from ...context import AppContext
from ...error import AppFileNotFoundError, BSMError, UserInputError
from ...logging import log_operation_error
from ..deps import (
    get_admin_user,
    get_app_context,
    get_moderator_user,
    validate_server_exists,
)
from ..schemas.addon import (
    AddonActionPayload,
    AddonListResponse,
    AddonReorderPayload,
    AddonSubpackPayload,
)
from ..schemas.base import TaskAcceptedResponse
from ..schemas.system import FileNamePayload
from ..schemas.users import UserResponse

logger = logging.getLogger(__name__)
router = APIRouter(
    tags=["Addon Management", "Content Management"],
)
STATIC_DIR = bsm_frontend.get_static_dir()


@router.get(
    "/api/content/addons",
    operation_id="list_available_addons",
    response_model=ListAvailableAddonsResponse,
)
async def get_addons(
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> ListAvailableAddonsResponse:
    """
    Retrieves a list of available .mcaddon or .mcpack template files.
    """
    identity = current_user.username
    logger.debug("List available addons request by user '%s'.", identity)
    try:
        api_result = await addon_api.list_available_addons(
            request=ListAvailableAddonsRequest(), app_context=app_context
        )

        basenames = [os.path.basename(f) for f in api_result.files]
        return ListAvailableAddonsResponse(files=basenames)
    except HTTPException:
        raise
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected critical error listing addons: %s", e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A critical server error occurred while listing addons.",
        )


@router.get(
    "/api/server/{server_name}/addons",
    operation_id="list_server_addons",
    response_model=AddonListResponse,
)
async def get_server_addons(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> AddonListResponse:
    """
    Retrieves a list of addons installed on a server's active world.
    """
    identity = current_user.username
    logger.debug(
        "List world addons for '%s' requested by user '%s'.", server_name, identity
    )
    try:
        result = await addon_api.list_installed_addons(
            request=ListInstalledAddonsRequest.model_validate(
                {"server_name": server_name}
            ),
            app_context=app_context,
        )
        return AddonListResponse(status="success", addons=result.addons)
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "API List Server Addons '%s': Error: %s", server_name, e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/enable",
    operation_id="enable_addon",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_enable_addon(
    payload: AddonActionPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to enable an addon on a server.
    """
    identity = current_user.username
    logger.info("Enable addon for '%s' requested by user '%s'.", server_name, identity)
    try:
        task_id = await app_context.task_manager.run_task(
            addon_api.enable_addon,
            username=current_user.username,
            app_context=app_context,
            request=EnableAddonRequest.model_validate(
                {
                    "server_name": server_name,
                    "pack_uuid": payload.pack_uuid,
                    "pack_type": payload.pack_type,
                }
            ),
        )
        return TaskAcceptedResponse(
            status="accepted",
            message=f"Addon enable for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "API Enable Server Addon '%s': Error: %s", server_name, e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/disable",
    operation_id="disable_addon",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_disable_addon(
    payload: AddonActionPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to disable an addon on a server.
    """
    identity = current_user.username
    logger.info("Disable addon for '%s' requested by user '%s'.", server_name, identity)
    try:
        task_id = await app_context.task_manager.run_task(
            addon_api.disable_addon,
            username=current_user.username,
            app_context=app_context,
            request=DisableAddonRequest.model_validate(
                {
                    "server_name": server_name,
                    "pack_uuid": payload.pack_uuid,
                    "pack_type": payload.pack_type,
                }
            ),
        )
        return TaskAcceptedResponse(
            status="accepted",
            message=f"Addon disable for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "API Disable Server Addon '%s': Error: %s", server_name, e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/subpack",
    operation_id="update_addon_subpack",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_update_subpack(
    payload: AddonSubpackPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to update an addon's active subpack.
    """
    identity = current_user.username
    logger.info(
        "Update addon subpack for '%s' requested by user '%s'.", server_name, identity
    )
    try:
        subpack_name = payload.subpack_name
        task_id = await app_context.task_manager.run_task(
            addon_api.update_subpack,
            username=current_user.username,
            app_context=app_context,
            request=UpdateSubpackRequest.model_validate(
                {
                    "server_name": server_name,
                    "pack_uuid": payload.pack_uuid,
                    "pack_type": payload.pack_type,
                    "subpack_name": subpack_name,
                }
            ),
        )
        return TaskAcceptedResponse(
            status="accepted",
            message=f"Addon subpack update for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "API Update Server Addon Subpack '%s': Error: %s",
            server_name,
            e,
            error=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.delete(
    "/api/server/{server_name}/addon/uninstall",
    operation_id="uninstall_addon",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_uninstall_addon(
    payload: AddonActionPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to uninstall an addon on a server.
    """
    identity = current_user.username
    logger.info(
        "Uninstall addon for '%s' requested by user '%s'.", server_name, identity
    )
    try:
        task_id = await app_context.task_manager.run_task(
            addon_api.uninstall_addon,
            username=current_user.username,
            app_context=app_context,
            request=UninstallAddonRequest.model_validate(
                {
                    "server_name": server_name,
                    "pack_uuid": payload.pack_uuid,
                    "pack_type": payload.pack_type,
                }
            ),
        )
        return TaskAcceptedResponse(
            status="accepted",
            message=f"Addon uninstall for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "API Uninstall Server Addon '%s': Error: %s",
            server_name,
            e,
            error=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/reorder",
    operation_id="reorder_addons",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_reorder_addons(
    payload: AddonReorderPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to reorder active addons on a server.
    """
    identity = current_user.username
    logger.info(
        "Reorder addons for '%s' requested by user '%s'.", server_name, identity
    )
    try:
        task_id = await app_context.task_manager.run_task(
            addon_api.reorder_addons,
            username=current_user.username,
            app_context=app_context,
            request=ReorderAddonsRequest.model_validate(
                {
                    "server_name": server_name,
                    "uuids": payload.uuids,
                    "pack_type": payload.pack_type,
                }
            ),
        )
        return TaskAcceptedResponse(
            status="accepted",
            message=f"Addon reorder for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "API Reorder Server Addons '%s': Error: %s", server_name, e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/addon/install",
    operation_id="install_addon",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_install_addon(
    payload: FileNamePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to install an addon from a .mcaddon or .mcpack file to a server.
    """
    identity = current_user.username
    selected_filename = payload.filename
    logger.info(
        "Addon install of '%s' for '%s' by user '%s'.",
        selected_filename,
        server_name,
        identity,
    )
    from ...utils.server import validate_server

    try:
        if not await validate_server(server_name=server_name, app_context=app_context):
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
                "API Install Addon '%s': Security violation - Invalid path '%s'.",
                server_name,
                selected_filename,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path (security check failed).",
            )

        if not await aiofiles.ospath.isfile(full_addon_file_path):
            logger.warning(
                "API Install Addon '%s': Addon file '%s' not found at '%s'.",
                server_name,
                selected_filename,
                full_addon_file_path,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Addon file '{selected_filename}' not found for import.",
            )

        task_id = await app_context.task_manager.run_task(
            addon_api.import_addon,
            username=current_user.username,
            app_context=app_context,
            request=ImportAddonRequest.model_validate(
                {"server_name": server_name, "addon_file_path": full_addon_file_path}
            ),
        )

        return TaskAcceptedResponse(
            status="accepted",
            message=f"Addon install from '{selected_filename}' for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except HTTPException:
        raise
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AppFileNotFoundError:
        raise
    except BSMError as e:
        logger.debug(
            "API Install Addon '%s': Pre-check BSMError: %s",
            server_name,
            e,
            exc_info=False,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "API Install Addon '%s': Pre-check error: %s",
            server_name,
            e,
            error=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error during pre-check: {str(e)}",
        )


@router.get(
    "/api/server/{server_name}/addon/icon",
    operation_id="get_server_addon_icon",
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
    logger.debug("Get addon icon for '%s' requested.", server_name)

    try:
        result = await addon_api.list_installed_addons(
            request=ListInstalledAddonsRequest.model_validate(
                {"server_name": server_name}
            ),
            app_context=app_context,
        )

        # Determine the key to search in based on pack_type
        addons_data = result.addons
        packs = (
            addons_data.behavior_packs
            if pack_type == "behavior"
            else addons_data.resource_packs
        )

        icon_path = None
        for pack in packs:
            if pack.uuid == uuid and pack.icon:
                icon_path = pack.icon
                break

        if icon_path and await aiofiles.ospath.exists(icon_path):
            return FileResponse(icon_path, media_type="image/png")

        logger.debug(
            "Addon icon not found for uuid '%s'. Serving default world icon.", uuid
        )
        raise AppFileNotFoundError("Addon Icon not found", "Addon Icon")

    except (AppFileNotFoundError, HTTPException):
        # Fallback to the default world icon
        default_icon_path = os.path.join(STATIC_DIR, "image", "icon", "favicon.ico")
        if await aiofiles.ospath.isfile(default_icon_path):
            return FileResponse(
                default_icon_path, media_type="image/vnd.microsoft.icon"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default icon not found.",
            )
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "API Get Server Addon Icon '%s': Error: %s", server_name, e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}",
        )

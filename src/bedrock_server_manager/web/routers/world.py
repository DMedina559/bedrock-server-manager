import logging
import os

import aiofiles.ospath
import bsm_frontend
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    ExportWorldRequest,
    ImportWorldRequest,
    ListAvailableWorldsRequest,
    ResetWorldRequest,
)

from ...api import application as app_api
from ...api import world as world_api
from ...context import AppContext
from ...error import (
    AppFileNotFoundError,
    BSMError,
    InvalidServerNameError,
    UserInputError,
)
from ...logging import log_operation_error
from ..deps import (
    get_admin_user,
    get_app_context,
    get_moderator_user,
    validate_server_exists,
)
from ..schemas import ContentListResponse, FileNamePayload, UserResponse
from ..schemas.base import TaskAcceptedResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["World Management"],
)

STATIC_DIR = bsm_frontend.get_static_dir()


@router.get(
    "/api/content/worlds",
    operation_id="list_available_worlds",
    response_model=ContentListResponse,
    tags=["Content Management"],
)
async def get_worlds_list(
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> ContentListResponse:
    """
    Retrieves a list of available .mcworld template files.
    """
    identity = current_user.username
    logger.debug("List available worlds request by user '%s'.", identity)
    try:
        api_result = await app_api.list_available_worlds(
            request=ListAvailableWorldsRequest(), app_context=app_context
        )
        full_paths = api_result.files
        basenames = [os.path.basename(p) for p in full_paths]
        return ContentListResponse(
            status="success", files=basenames, message=api_result.message
        )
    except HTTPException:
        raise
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected critical error listing worlds: %s", e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A critical server error occurred while listing worlds.",
        )


@router.post(
    "/api/server/{server_name}/world/install",
    operation_id="install_world",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content Management"],
)
async def post_world_install(
    payload: FileNamePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to install a world from a .mcworld file to a server.
    """
    identity = current_user.username
    selected_filename = payload.filename
    logger.info(
        "World install of '%s' for '%s' by user '%s'.",
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
            app_context.settings.get("paths.content"), "worlds"
        )
        full_world_file_path = os.path.normpath(
            os.path.join(content_base_dir, selected_filename)
        )

        if not os.path.abspath(full_world_file_path).startswith(
            os.path.abspath(content_base_dir) + os.sep
        ):
            logger.error(
                "API Install World '%s': Security violation - Invalid path '%s'.",
                server_name,
                selected_filename,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path (security check failed).",
            )

        if not await aiofiles.ospath.isfile(full_world_file_path):
            logger.warning(
                "API Install World '%s': World file '%s' not found at '%s'.",
                server_name,
                selected_filename,
                full_world_file_path,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"World file '{selected_filename}' not found for import.",
            )

        task_id = await app_context.task_manager.run_task(
            world_api.import_world,
            username=current_user.username,
            app_context=app_context,
            request=ImportWorldRequest(
                server_name=server_name, selected_file_path=full_world_file_path
            ),
        )

        return TaskAcceptedResponse(
            status="accepted",
            message=f"World install from '{selected_filename}' for server '{server_name}' initiated in background.",
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
            "API Install World '%s': Pre-check BSMError: %s",
            server_name,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except HTTPException:
        raise
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "API Install World '%s': Pre-check error: %s",
            server_name,
            e,
            error=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error during pre-check: {str(e)}",
        )


@router.post(
    "/api/server/{server_name}/world/export",
    operation_id="export_world",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content Management"],
)
async def post_world_export(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to export the active world of a server to a .mcworld file.
    """
    identity = current_user.username
    logger.info("World export requested for '%s' by user '%s'.", server_name, identity)
    from ...utils.server import validate_server

    try:
        if not await validate_server(server_name=server_name, app_context=app_context):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        task_id = await app_context.task_manager.run_task(
            world_api.export_world,
            username=current_user.username,
            app_context=app_context,
            request=ExportWorldRequest(server_name=server_name),
        )

        return TaskAcceptedResponse(
            status="accepted",
            message=f"World export for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except HTTPException:
        raise
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "API Export World '%s': Pre-check error: %s",
            server_name,
            e,
            error=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error during pre-check: {str(e)}",
        )


@router.delete(
    "/api/server/{server_name}/world/reset",
    operation_id="reset_world",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Server Management"],
)
async def delete_world_reset(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to reset a server's world.
    """
    identity = current_user.username
    logger.info("World reset requested for '%s' by user '%s'.", server_name, identity)
    from ...utils.server import validate_server

    try:
        if not await validate_server(server_name=server_name, app_context=app_context):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        task_id = await app_context.task_manager.run_task(
            world_api.reset_world,
            username=current_user.username,
            app_context=app_context,
            request=ResetWorldRequest(server_name=server_name),
        )

        return TaskAcceptedResponse(
            status="accepted",
            message=f"World reset for server '{server_name}' initiated in background.",
            task_id=task_id,
        )
    except HTTPException:
        raise
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger, "API Reset World '%s': Pre-check error: %s", server_name, e, error=e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error during pre-check: {str(e)}",
        )


@router.get(
    "/api/server/{server_name}/world/icon",
    operation_id="get_world_icon",
    response_class=FileResponse,
)
async def get_world_icon(
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
):
    """Serves the `world_icon.jpeg` for a server, or a default icon if not found."""
    logger.debug("Request to serve world icon for server '%s'.", server_name)
    try:
        server = app_context.get_server(server_name)
        icon_path = await server.worlds.get_world_icon_filesystem_path()

        import aiofiles.ospath

        if (
            await server.worlds.has_world_icon()
            and icon_path
            and await aiofiles.ospath.isfile(icon_path)
        ):
            logger.debug("Serving world icon from path: %s", icon_path)
            return FileResponse(icon_path, media_type="image/jpeg")
        else:

            logger.debug(
                "World icon for '%s' not found at '%s'. Serving default.",
                server_name,
                icon_path,
            )
            raise AppFileNotFoundError(str(icon_path), "World icon")

    except (
        AppFileNotFoundError,
        InvalidServerNameError,
        BSMError,
    ) as e:
        if not isinstance(e, AppFileNotFoundError):
            log_operation_error(
                logger,
                "Error preparing to serve world icon for '%s': %s",
                server_name,
                e,
                error=e,
            )

        default_icon_path = os.path.join(STATIC_DIR, "image", "icon", "favicon.ico")
        if os.path.isfile(default_icon_path):
            logger.debug(
                "Serving default world icon (favicon.ico) from: %s", default_icon_path
            )
            return FileResponse(
                default_icon_path, media_type="image/vnd.microsoft.icon"
            )
        else:
            log_operation_error(
                logger,
                "Default world icon (favicon.ico) not found at %s",
                default_icon_path,
                error=e,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default world icon not found.",
            )

    except HTTPException:
        raise
    except ValidationError:
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error serving world icon for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error serving icon.",
        )

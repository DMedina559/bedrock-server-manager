import logging
import os

import aiofiles.ospath
import bsm_frontend
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.responses import FileResponse

from bedrock_server_manager.api.models import (
    ExportWorldRequest,
    ImportWorldRequest,
    ListAvailableWorldsRequest,
    ListAvailableWorldsResponse,
    ResetWorldRequest,
)

from ...api import application as app_api
from ...api import world as world_api
from ...context import AppContext
from ...error import (
    AppFileNotFoundError,
)
from ...logging import log_operation_error
from ..access_policy import Permission
from ..deps import get_app_context, validate_server_exists
from ..deps.auth import require_permissions
from ..schemas import FileNamePayload, UserResponse
from ..schemas.base import TaskAcceptedResponse
from .content import resolve_content_file

logger = logging.getLogger(__name__)

router = APIRouter(tags=["World Management"])

STATIC_DIR = bsm_frontend.get_static_dir()


@router.get(
    "/api/content/worlds",
    operation_id="list_available_worlds",
    response_model=ListAvailableWorldsResponse,
)
async def get_worlds_list(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.CONTENT_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> ListAvailableWorldsResponse:
    """Return a list of available .mcworld template files."""
    identity = current_user.username
    logger.debug("List available worlds request by user '%s'.", identity)
    api_result = await app_api.list_available_worlds(
        request=ListAvailableWorldsRequest(), app_context=app_context
    )
    full_paths = api_result.files
    basenames = [os.path.basename(p) for p in full_paths]
    return ListAvailableWorldsResponse(
        status="success", files=basenames, message=api_result.message
    )


@router.post(
    "/api/server/{server_name}/world/install",
    operation_id="install_world",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_world_install(
    payload: FileNamePayload,
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.WORLDS_MANAGE]
    ),
    server_name: str = Depends(validate_server_exists),
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

    full_world_file_path = str(
        await resolve_content_file(app_context, "worlds", selected_filename)
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


@router.post(
    "/api/server/{server_name}/world/export",
    operation_id="export_world",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_world_export(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.WORLDS_MANAGE]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to export the active world of a server to a .mcworld file.
    """
    identity = current_user.username
    logger.info("World export requested for '%s' by user '%s'.", server_name, identity)

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


@router.delete(
    "/api/server/{server_name}/world/reset",
    operation_id="reset_world",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_world_reset(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.WORLDS_RESET]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates a background task to reset a server's world.
    """
    identity = current_user.username
    logger.info("World reset requested for '%s' by user '%s'.", server_name, identity)

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


@router.get(
    "/api/server/{server_name}/world/icon",
    operation_id="get_world_icon",
    responses={
        200: {
            "content": {
                media: {"schema": {"type": "string", "format": "binary"}}
                for media in ("image/png", "image/jpeg", "image/vnd.microsoft.icon")
            }
        }
    },
    response_class=FileResponse,
)
async def get_world_icon(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.WORLDS_READ]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
):
    """Serves the ``world_icon.jpeg`` for a server, or a default icon if not found."""
    logger.debug("Request to serve world icon for server '%s'.", server_name)

    try:
        server = app_context.get_server(server_name)
        icon_path = await server.worlds.get_world_icon_filesystem_path()

        if (
            await server.worlds.has_world_icon()
            and icon_path
            and await aiofiles.ospath.isfile(icon_path)
        ):
            logger.debug("Serving world icon from path: %s", icon_path)
            return FileResponse(
                icon_path,
                media_type="image/jpeg",
                headers={"Cache-Control": "private, no-store"},
            )
        else:

            logger.debug(
                "World icon for '%s' not found at '%s'. Serving default.",
                server_name,
                icon_path,
            )
            raise AppFileNotFoundError(str(icon_path), "World icon")

    except AppFileNotFoundError as e:
        default_icon_path = os.path.join(
            STATIC_DIR, "image", "icon", "web-app-manifest-192x192.png"
        )
        if await aiofiles.ospath.isfile(default_icon_path):
            logger.debug("Serving default world icon from: %s", default_icon_path)
            return FileResponse(
                default_icon_path,
                media_type="image/png",
                headers={"Cache-Control": "private, no-store"},
            )
        else:
            log_operation_error(
                logger,
                "Default world icon not found at %s",
                default_icon_path,
                error=e,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default world icon not found.",
            )

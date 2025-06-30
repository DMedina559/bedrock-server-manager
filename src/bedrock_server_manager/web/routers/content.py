import os
import logging
from typing import Dict, Any, List, Optional

import os
import logging
from typing import Dict, Any, List, Optional

from fastapi import (
    APIRouter,
    Request,
    Depends,
    HTTPException,
    status,
    BackgroundTasks,
    Path,
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field

from bedrock_server_manager.web.templating import templates
from bedrock_server_manager.web.auth_utils import get_current_user
from ..dependencies import validate_server_exists
from bedrock_server_manager.api import (
    world as world_api,
    addon as addon_api,
    application as app_api,
)
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import BSMError, UserInputError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/content",
    tags=["Content Management"],
)


# --- Pydantic Models ---
class FileNamePayload(BaseModel):
    filename: str


class GeneralContentListResponse(BaseModel):
    status: str
    message: Optional[str] = None
    files: Optional[List[str]] = None


class ActionResponse(BaseModel):
    status: str = "success"
    message: str
    details: Optional[Any] = None


# --- HTML Routes ---
@router.get(
    "/server/{server_name}/install_world",
    response_class=HTMLResponse,
    name="install_world_page",
)
async def install_world_page(
    request: Request,
    server_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"User '{identity}' accessed world install selection page for server '{server_name}'."
    )

    world_files: List[str] = []
    error_message: Optional[str] = None
    try:
        list_result = app_api.list_available_worlds_api()
        if list_result.get("status") == "success":
            full_paths = list_result.get("files", [])
            world_files = [os.path.basename(p) for p in full_paths]
        else:
            error_message = list_result.get(
                "message", "Unknown error listing world files."
            )
            logger.error(
                f"Error listing world files for {server_name} page: {error_message}"
            )
    except Exception as e:
        logger.error(
            f"Unexpected error listing worlds for {server_name} page: {e}",
            exc_info=True,
        )
        error_message = "An unexpected server error occurred while listing worlds."

    return templates.TemplateResponse(
        "select_world.html",
        {
            "request": request,
            "current_user": current_user,
            "server_name": server_name,
            "world_files": world_files,
            "error_message": error_message,
        },
    )


@router.get(
    "/server/{server_name}/install_addon",
    response_class=HTMLResponse,
    name="install_addon_page",
)
async def install_addon_page(
    request: Request,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"User '{identity}' accessed addon install selection page for server '{server_name}'."
    )

    addon_files: List[str] = []
    error_message: Optional[str] = None
    try:
        list_result = app_api.list_available_addons_api()
        if list_result.get("status") == "success":
            full_paths = list_result.get("files", [])
            addon_files = [os.path.basename(p) for p in full_paths]
        else:
            error_message = list_result.get(
                "message", "Unknown error listing addon files."
            )
            logger.error(
                f"Error listing addon files for {server_name} page: {error_message}"
            )
    except Exception as e:
        logger.error(
            f"Unexpected error listing addons for {server_name} page: {e}",
            exc_info=True,
        )
        error_message = "An unexpected server error occurred while listing addons."

    return templates.TemplateResponse(
        "select_addon.html",
        {
            "request": request,
            "current_user": current_user,
            "server_name": server_name,
            "addon_files": addon_files,
            "error_message": error_message,
        },
    )


# --- API Routes ---
@router.get(
    "/api/worlds", response_model=GeneralContentListResponse, tags=["Content API"]
)
async def list_worlds_api_route(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: List available worlds request by user '{identity}'.")
    try:
        api_result = app_api.list_available_worlds_api()
        if api_result.get("status") == "success":
            full_paths = api_result.get("files", [])
            basenames = [os.path.basename(p) for p in full_paths]
            return GeneralContentListResponse(status="success", files=basenames)
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
    "/api/addons", response_model=GeneralContentListResponse, tags=["Content API"]
)
async def list_addons_api_route(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: List available addons request by user '{identity}'.")
    try:
        api_result = app_api.list_available_addons_api()
        if api_result.get("status") == "success":
            full_paths = api_result.get("files", [])
            basenames = [os.path.basename(p) for p in full_paths]
            return GeneralContentListResponse(status="success", files=basenames)
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


# --- Background Task Helpers ---
def log_background_task_error(task_name: str, server_name: str, exc: Exception):
    logger.error(
        f"Background task '{task_name}' for server '{server_name}': Unexpected error. {exc}",
        exc_info=True,
    )


def install_world_task(server_name: str, world_file_path: str):
    logger.info(
        f"Background task initiated: Installing world '{os.path.basename(world_file_path)}' to server '{server_name}'."
    )
    try:
        result = world_api.import_world(server_name, world_file_path)
        if result.get("status") == "success":
            logger.info(
                f"Background task 'install_world' for '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            logger.error(
                f"Background task 'install_world' for '{server_name}': Failed. {result.get('message')}"
            )
    except BSMError as e:
        logger.error(
            f"Background task 'install_world' for '{server_name}': Application error. {e}",
            exc_info=True,
        )
    except Exception as e:
        log_background_task_error(
            f"install_world ({os.path.basename(world_file_path)})", server_name, e
        )


@router.post(
    "/api/server/{server_name}/world/install",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def install_world_api_route(
    payload: FileNamePayload,
    tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    selected_filename = payload.filename
    logger.info(
        f"API: World install of '{selected_filename}' for '{server_name}' by user '{identity}'."
    )

    try:

        if not app_api.validate_server_exist(server_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        content_base_dir = os.path.join(settings.get("paths.content"), "worlds")
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

        tasks.add_task(install_world_task, server_name, full_world_file_path)

        return ActionResponse(
            message=f"World install from '{selected_filename}' for server '{server_name}' initiated in background."
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


def export_world_task(server_name: str):
    logger.info(
        f"Background task initiated: Exporting world from server '{server_name}'."
    )
    try:
        result = world_api.export_world(server_name)
        if result.get("status") == "success":
            logger.info(
                f"Background task 'export_world' for '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            logger.error(
                f"Background task 'export_world' for '{server_name}': Failed. {result.get('message')}"
            )
    except BSMError as e:
        logger.error(
            f"Background task 'export_world' for '{server_name}': Application error. {e}",
            exc_info=True,
        )
    except Exception as e:
        log_background_task_error(f"export_world", server_name, e)


@router.post(
    "/api/server/{server_name}/world/export",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def export_world_api_route(
    tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: World export requested for '{server_name}' by user '{identity}'."
    )

    try:

        if not app_api.validate_server_exist(server_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        tasks.add_task(export_world_task, server_name)

        return ActionResponse(
            message=f"World export for server '{server_name}' initiated in background."
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


def reset_world_task(server_name: str):
    logger.info(
        f"Background task initiated: Resetting world for server '{server_name}'."
    )
    try:
        result = world_api.reset_world(server_name)
        if result.get("status") == "success":
            logger.info(
                f"Background task 'reset_world' for '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            logger.error(
                f"Background task 'reset_world' for '{server_name}': Failed. {result.get('message')}"
            )
    except (
        BSMError
    ) as e:  # Original had UserInputError, but reset_world likely BSMError for wider issues
        logger.warning(
            f"Background task 'reset_world' for '{server_name}': Application error. {e}",
            exc_info=True,
        )  # Changed to warning as per original
    except Exception as e:
        log_background_task_error(f"reset_world", server_name, e)


@router.delete(
    "/api/server/{server_name}/world/reset",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def reset_world_api_route(
    tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: World reset requested for '{server_name}' by user '{identity}'.")

    try:
        # Validate server existence before queueing task
        if not app_api.validate_server_exist(server_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        tasks.add_task(reset_world_task, server_name)

        return ActionResponse(
            message=f"World reset for server '{server_name}' initiated in background."
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


def install_addon_task(server_name: str, addon_file_path: str):
    logger.info(
        f"Background task initiated: Installing addon '{os.path.basename(addon_file_path)}' to server '{server_name}'."
    )
    try:
        result = addon_api.import_addon(server_name, addon_file_path)
        if result.get("status") == "success":
            logger.info(
                f"Background task 'install_addon' for '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            logger.error(
                f"Background task 'install_addon' for '{server_name}': Failed. {result.get('message')}"
            )
    except BSMError as e:
        logger.error(
            f"Background task 'install_addon' for '{server_name}': Application error. {e}",
            exc_info=True,
        )
    except Exception as e:
        log_background_task_error(
            f"install_addon ({os.path.basename(addon_file_path)})", server_name, e
        )


@router.post(
    "/api/server/{server_name}/addon/install",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Content API"],
)
async def install_addon_api_route(
    payload: FileNamePayload,
    tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    identity = current_user.get("username", "Unknown")
    selected_filename = payload.filename
    logger.info(
        f"API: Addon install of '{selected_filename}' for '{server_name}' by user '{identity}'."
    )

    try:

        if not app_api.validate_server_exist(server_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server '{server_name}' not found.",
            )

        content_base_dir = os.path.join(settings.get("paths.content"), "addons")
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

        tasks.add_task(install_addon_task, server_name, full_addon_file_path)

        return ActionResponse(
            message=f"Addon install from '{selected_filename}' for server '{server_name}' initiated in background."
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

# bedrock_server_manager/web/routers/backup_restore.py
"""
FastAPI router for server backup, restore, and pruning operations.

This module defines both HTML page-serving routes and API endpoints for
managing backups of Bedrock server instances. Functionalities include:

- Displaying backup and restore menus for a server.
- Allowing users to select specific backup files for restoration.
- Triggering backup operations (full, world-only, specific config file).
- Triggering restore operations (from latest, specific world backup, specific config backup).
- Listing available backups for different components.
- Initiating pruning of old backups based on retention policies.

Most backup and restore actions are performed as background tasks to provide
immediate API responses. Operations are typically authenticated and target a
specific server validated by a dependency. It relies on the underlying
functionality provided by :mod:`~bedrock_server_manager.api.backup_restore`.
"""
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
    Body,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from bedrock_server_manager.web.templating import templates
from bedrock_server_manager.web.auth_utils import get_current_user
from ..dependencies import validate_server_exists
from bedrock_server_manager.api import backup_restore as backup_restore_api
from bedrock_server_manager.config.settings import settings
from bedrock_server_manager.error import BSMError, UserInputError, AppFileNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/backup-restore",
    tags=["Backup & Restore"],
)


# --- Pydantic Models ---
class RestoreTypePayload(BaseModel):
    """Request model for specifying the type of restore operation."""

    restore_type: str = Field(
        ..., description="The type of restore to perform (e.g., 'world', 'properties')."
    )


class BackupActionPayload(BaseModel):
    """Request model for triggering a backup action."""

    backup_type: str = Field(
        ..., description="Type of backup: 'world', 'config', or 'all'."
    )
    file_to_backup: Optional[str] = Field(
        default=None,
        description="Name of config file if backup_type is 'config' (e.g., 'server.properties').",
    )


class RestoreActionPayload(BaseModel):
    """Request model for triggering a restore action."""

    restore_type: str = Field(
        ...,
        description="Type of restore: 'world', 'properties', 'allowlist', 'permissions', or 'all'.",
    )
    backup_file: Optional[str] = Field(
        default=None,
        description="Name of the backup file (basename) to restore from (required if not 'all').",
    )


class GeneralResponse(BaseModel):
    """Generic API response model for backup and restore operations."""

    status: str = Field(
        ...,
        description="Status of the operation (e.g., 'success', 'error', 'skipped').",
    )
    message: str = Field(..., description="Descriptive message about the operation.")
    details: Optional[Any] = Field(
        default=None, description="Optional detailed results or error information."
    )
    redirect_url: Optional[str] = Field(
        default=None, description="Optional URL to redirect to after an action."
    )
    backups: Optional[List[Any]] = Field(
        default=None, description="Optional list of backup files or related data."
    )


# --- HTML Routes ---
@router.get(
    "/server/{server_name}/backup", response_class=HTMLResponse, name="backup_menu_page"
)
async def backup_menu_page(
    request: Request,
    server_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Displays the backup menu page for a specific server.

    Allows users to choose various backup actions like backing up the world,
    configuration files, or all server data.

    Args:
        request (:class:`fastapi.Request`): FastAPI request object.
        server_name (str): The name of the server for which to display backup options.
        current_user (Dict[str, Any]): Authenticated user (from dependency).
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"User '{identity}' accessed backup menu for server '{server_name}'.")
    return templates.TemplateResponse(
        "backup_menu.html",
        {"request": request, "current_user": current_user, "server_name": server_name},
    )


@router.get(
    "/server/{server_name}/backup/select",
    response_class=HTMLResponse,
    name="backup_config_select_page",
)
async def backup_config_select_page(
    request: Request,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Displays the page for selecting specific configuration files to back up.

    Args:
        request (:class:`fastapi.Request`): FastAPI request object.
        server_name (str): Name of the server (validated by dependency).
        current_user (Dict[str, Any]): Authenticated user (from dependency).
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"User '{identity}' accessed config backup selection page for server '{server_name}'."
    )

    return templates.TemplateResponse(
        "backup_config_options.html",
        {"request": request, "current_user": current_user, "server_name": server_name},
    )


@router.get(
    "/server/{server_name}/restore",
    response_class=HTMLResponse,
    name="restore_menu_page",
)
async def restore_menu_page(
    request: Request,
    server_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Displays the restore menu page for a specific server.

    Allows users to choose various restore actions, such as restoring the entire
    server, the world, or specific configuration files from available backups.

    Args:
        request (:class:`fastapi.Request`): FastAPI request object.
        server_name (str): The name of the server for which to display restore options.
        current_user (Dict[str, Any]): Authenticated user (from dependency).
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"User '{identity}' accessed restore menu for server '{server_name}'.")
    return templates.TemplateResponse(
        "restore_menu.html",
        {"request": request, "current_user": current_user, "server_name": server_name},
    )


@router.get(
    "/server/{server_name}/restore/{restore_type}/select_file",
    response_class=HTMLResponse,
    name="select_backup_file_page",
)
async def show_select_backup_file_page(
    request: Request,
    restore_type: str,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Displays the page for selecting a specific backup file for restoration.

    Based on the `restore_type` (e.g., "world", "properties"), this page lists
    the relevant available backup files for the specified server.

    Args:
        request (:class:`fastapi.Request`): FastAPI request object.
        restore_type (str): The type of content to restore (e.g., "world", "properties").
        server_name (str): Name of the server (validated by dependency).
        current_user (Dict[str, Any]): Authenticated user (from dependency).
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"User '{identity}' viewing selection page for '{restore_type}' backups for server '{server_name}'."
    )

    valid_types = ["world", "properties", "allowlist", "permissions"]
    if restore_type.lower() not in valid_types:
        redirect_url = request.url_for(
            "restore_menu_page", server_name=server_name
        ).include_query_params(
            message=f"Invalid restore type '{restore_type}' specified.",
            category="warning",
        )
        return RedirectResponse(
            url=str(redirect_url), status_code=status.HTTP_302_FOUND
        )

    try:
        api_result = backup_restore_api.list_backup_files(server_name, restore_type)
        if api_result.get("status") == "success":
            full_paths = api_result.get("backups", [])
            if not full_paths:
                redirect_url = request.url_for(
                    "restore_menu_page", server_name=server_name
                ).include_query_params(
                    message=f"No '{restore_type}' backups found for server '{server_name}'.",
                    category="info",
                )
                return RedirectResponse(
                    url=str(redirect_url), status_code=status.HTTP_302_FOUND
                )

            backups_for_template = [
                {
                    "name": os.path.basename(p),
                    "path": os.path.basename(p),
                }
                for p in full_paths
            ]
            return templates.TemplateResponse(
                "restore_select_backup.html",
                {
                    "request": request,
                    "current_user": current_user,
                    "server_name": server_name,
                    "restore_type": restore_type,
                    "backups": backups_for_template,
                },
            )
        else:
            error_msg = api_result.get("message", "Unknown error listing backups.")
            logger.error(
                f"Error listing backups for '{server_name}' ({restore_type}): {error_msg}"
            )
            redirect_url = request.url_for(
                "restore_menu_page", server_name=server_name
            ).include_query_params(
                message=f"Error listing backups: {error_msg}", category="error"
            )
            return RedirectResponse(
                url=str(redirect_url), status_code=status.HTTP_302_FOUND
            )
    except Exception as e:
        logger.error(
            f"Unexpected error on backup selection page for '{server_name}' ({restore_type}): {e}",
            exc_info=True,
        )
        redirect_url = request.url_for(
            "restore_menu_page", server_name=server_name
        ).include_query_params(
            message="An unexpected error occurred while preparing backup selection.",
            category="error",
        )
        return RedirectResponse(
            url=str(redirect_url), status_code=status.HTTP_302_FOUND
        )


# --- API Routes ---
@router.post(
    "/api/server/{server_name}/restore/select_backup_type",
    response_model=GeneralResponse,
    tags=["Backup & Restore API"],
)
async def handle_restore_select_backup_type_api(
    request: Request,
    payload: RestoreTypePayload,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Handles the API request for selecting a restore type and redirects to file selection.

    This endpoint is typically called when a user chooses what type of content
    they want to restore (e.g., "world", "properties"). It validates the type
    and then provides a redirect URL to the page where specific backup files
    of that type can be chosen.

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - **Request body**: Expects :class:`.RestoreTypePayload` with `restore_type`.
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    restore_type = payload.restore_type.lower()

    logger.info(
        f"API: User '{identity}' initiated selection of restore_type '{restore_type}' for server '{server_name}'."
    )

    valid_types = ["world", "properties", "allowlist", "permissions"]
    if restore_type not in valid_types:
        logger.warning(
            f"API: Invalid restore_type '{restore_type}' selected by '{identity}' for '{server_name}'."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid restore type '{restore_type}' selected. Must be one of {valid_types}.",
        )

    try:
        redirect_page_url = request.url_for(
            "select_backup_file_page",
            server_name=server_name,
            restore_type=restore_type,
        )
        return GeneralResponse(
            status="success",
            message=f"Proceed to select {restore_type} backup.",
            redirect_url=str(redirect_page_url),
        )
    except Exception as e:
        logger.error(
            f"API: Unexpected error during restore type selection for '{server_name}' by '{identity}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred.",
        )


# --- API Background Task Helper ---
def log_background_task_error(task_name: str, server_name: str, exc: Exception):
    """Logs an error that occurs in a background task related to backup/restore.

    Args:
        task_name (str): The name of the background task (e.g., "prune_backups").
        server_name (str): The name of the server the task was performed on.
        exc (Exception): The exception that occurred.
    """
    logger.error(
        f"Background task '{task_name}' for server '{server_name}': Unexpected error. {exc}",
        exc_info=True,
    )


def prune_backups_task(server_name: str):
    """
    Background task to prune old backups for a given server.

    Calls :func:`~bedrock_server_manager.api.backup_restore.prune_old_backups`.
    Logs the outcome.

    Args:
        server_name (str): The name of the server whose backups are to be pruned.
    """
    logger.info(
        f"Background task initiated: Pruning backups for server '{server_name}'."
    )
    try:
        result = backup_restore_api.prune_old_backups(server_name)
        if result.get("status") == "success":
            logger.info(
                f"Background task 'prune_backups' for '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            logger.error(
                f"Background task 'prune_backups' for '{server_name}': Failed. {result.get('message')}"
            )
    except BSMError as e:
        logger.warning(
            f"Background task 'prune_backups' for '{server_name}': Application error. {e}"
        )
    except Exception as e:
        log_background_task_error("prune_backups", server_name, e)


@router.post(
    "/api/server/{server_name}/backups/prune",
    response_model=GeneralResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Backup & Restore API"],
)
async def prune_backups_api_route(
    tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates a background task to prune old backups for a specific server.

    This action adheres to the retention policies defined in the application settings.

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Request to prune backups for server '{server_name}' by user '{identity}'."
    )
    tasks.add_task(prune_backups_task, server_name)

    return GeneralResponse(
        status="success",
        message=f"Backup pruning for server '{server_name}' initiated in background.",
    )


@router.get(
    "/api/server/{server_name}/backup/list/{backup_type}",
    response_model=GeneralResponse,
    tags=["Backup & Restore API"],
)
async def list_server_backups_api_route(
    backup_type: str,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Lists available backup files for a specific server and backup type.

    Calls :func:`~bedrock_server_manager.api.backup_restore.list_backup_files`.
    Returns a list of backup file basenames for specific types, or a dictionary
    of lists if `backup_type` is "all".

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - **backup_type**: Path parameter, specifying the type of backups to list
      (e.g., "world", "properties", "allowlist", "permissions", "all").
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Request to list '{backup_type}' backups for server '{server_name}' by user '{identity}'."
    )

    try:
        api_result = backup_restore_api.list_backup_files(
            server_name=server_name, backup_type=backup_type
        )
        if api_result.get("status") == "success":
            backup_data = api_result.get("backups", [])

            if backup_type.lower() == "all" and isinstance(backup_data, dict):
                # For 'all', backup_data is Dict[str, List[str (full paths)]]
                # We need to convert full paths to basenames for each list in the dict
                processed_all_backups = {
                    key: [os.path.basename(p) for p in path_list]
                    for key, path_list in backup_data.items()
                }
                return GeneralResponse(
                    status="success",
                    message="All backup types listed successfully.",
                    details={"all_backups": processed_all_backups},
                )
            elif isinstance(backup_data, list):
                basenames = [os.path.basename(p) for p in backup_data]
                return GeneralResponse(
                    status="success",
                    message="Backups listed successfully.",
                    backups=basenames,
                )
            else:
                logger.error(
                    f"API List Backups: Unexpected backup data format for type '{backup_type}': {backup_data}"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Unexpected backup data format.",
                )

        else:
            if (
                "not found" in api_result.get("message", "").lower()
                and "server" in api_result.get("message", "").lower()
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=api_result.get("message"),
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=api_result.get("message", "Failed to list backups."),
            )
    except UserInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:
        logger.error(
            f"API List Backups '{server_name}/{backup_type}': BSMError. {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API List Backups '{server_name}/{backup_type}': Unexpected error. {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A critical server error occurred while listing backups.",
        )


def backup_action_task(
    server_name: str, backup_type: str, file_to_backup: Optional[str]
):
    """
    Background task to perform a backup action (world, config, or all).

    Calls the appropriate backup function from
    :mod:`~bedrock_server_manager.api.backup_restore` based on `backup_type`.
    Logs the outcome.

    Args:
        server_name (str): The name of the server.
        backup_type (str): Type of backup ("world", "config", "all").
        file_to_backup (Optional[str]): Specific file for "config" backup type.
    """
    logger.info(
        f"Background task initiated: Backup action '{backup_type}' for server '{server_name}'."
    )
    try:
        result: Dict[str, Any] = {}
        if backup_type == "world":
            result = backup_restore_api.backup_world(server_name)
        elif backup_type == "config":
            if not file_to_backup:
                logger.error(
                    f"Background task 'backup_action' for '{server_name}': 'file_to_backup' is missing for config type."
                )
                return
            result = backup_restore_api.backup_config_file(
                server_name, file_to_backup.strip()
            )
        elif backup_type == "all":
            result = backup_restore_api.backup_all(server_name)
        else:
            logger.error(
                f"Background task 'backup_action' for '{server_name}': Invalid backup type '{backup_type}'."
            )
            return

        if result.get("status") == "success":
            logger.info(
                f"Background task 'backup_action' ({backup_type}) for '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            logger.error(
                f"Background task 'backup_action' ({backup_type}) for '{server_name}': Failed. {result.get('message')}"
            )
    except BSMError as e:
        logger.error(
            f"Background task 'backup_action' ({backup_type}) for '{server_name}': BSMError. {e}",
            exc_info=True,
        )
    except Exception as e:
        log_background_task_error(f"backup_action ({backup_type})", server_name, e)


@router.post(
    "/api/server/{server_name}/backup/action",
    response_model=GeneralResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Backup & Restore API"],
)
async def backup_action_api_route(
    tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    payload: BackupActionPayload = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates a background task to perform a backup action for a specific server.

    Valid backup types are "world", "config" (requires `file_to_backup` in payload),
    and "all".

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - **Request body**: Expects a :class:`.BackupActionPayload`.
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Backup action '{payload.backup_type}' requested for server '{server_name}' by user '{identity}'."
    )

    valid_types = ["world", "config", "all"]
    if payload.backup_type.lower() not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid 'backup_type'. Must be one of: {valid_types}.",
        )

    if payload.backup_type.lower() == "config" and (
        not payload.file_to_backup or not isinstance(payload.file_to_backup, str)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid 'file_to_backup' for config backup type.",
        )

    tasks.add_task(
        backup_action_task,
        server_name,
        payload.backup_type.lower(),
        payload.file_to_backup,
    )

    return GeneralResponse(
        status="success",
        message=f"Backup action '{payload.backup_type}' for server '{server_name}' initiated in background.",
    )


def restore_action_task(
    server_name: str, restore_type: str, relative_backup_file: Optional[str]
):
    """
    Background task to perform a restore action.

    Calls the appropriate restore function from
    :mod:`~bedrock_server_manager.api.backup_restore` based on `restore_type`.
    Handles path construction and validation for specific file restores.
    Logs the outcome.

    Args:
        server_name (str): The name of the server.
        restore_type (str): Type of restore ("all", "world", "properties", "allowlist", "permissions").
        relative_backup_file (Optional[str]): Basename of the backup file if not restoring "all".
    """
    logger.info(
        f"Background task initiated: Restore action '{restore_type}' for server '{server_name}'."
    )
    try:
        result: Dict[str, Any] = {}

        if restore_type == "all":
            result = backup_restore_api.restore_all(server_name)
        else:
            if not relative_backup_file:
                logger.error(
                    f"Background task 'restore_action' for '{server_name}': 'backup_file' is missing for '{restore_type}'."
                )
                return

            backup_base_dir = settings.get("paths.backups")
            if not backup_base_dir:
                logger.error(
                    "Background task 'restore_action': BACKUP_DIR not configured."
                )
                return

            server_backup_dir = os.path.join(backup_base_dir, server_name)
            full_backup_path = os.path.normpath(
                os.path.join(server_backup_dir, relative_backup_file)
            )

            if not os.path.abspath(full_backup_path).startswith(
                os.path.abspath(server_backup_dir) + os.sep
            ):
                logger.error(
                    f"Background task 'restore_action' for '{server_name}': Security violation - Invalid backup path '{relative_backup_file}'."
                )
                return

            if not os.path.isfile(full_backup_path):
                logger.error(
                    f"Background task 'restore_action' for '{server_name}': Backup file not found: {full_backup_path}"
                )
                return

            if restore_type == "world":
                result = backup_restore_api.restore_world(server_name, full_backup_path)
            elif restore_type in [
                "properties",
                "allowlist",
                "permissions",
            ]:
                result = backup_restore_api.restore_config_file(
                    server_name, full_backup_path
                )
            else:
                logger.error(
                    f"Background task 'restore_action' for '{server_name}': Invalid restore type '{restore_type}'."
                )
                return

        if result.get("status") == "success":
            logger.info(
                f"Background task 'restore_action' ({restore_type}) for '{server_name}': Succeeded. {result.get('message')}"
            )
        else:
            logger.error(
                f"Background task 'restore_action' ({restore_type}) for '{server_name}': Failed. {result.get('message')}"
            )

    except BSMError as e:
        logger.error(
            f"Background task 'restore_action' ({restore_type}) for '{server_name}': BSMError. {e}",
            exc_info=True,
        )
    except Exception as e:
        log_background_task_error(f"restore_action ({restore_type})", server_name, e)


@router.post(
    "/api/server/{server_name}/restore/action",
    response_model=GeneralResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Backup & Restore API"],
)
async def restore_action_api_route(
    payload: RestoreActionPayload,
    tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates a background task to perform a restore action for a specific server.

    Valid restore types include "all", "world", "properties", "allowlist",
    and "permissions". If not restoring "all", a `backup_file` (basename)
    must be provided in the payload.

    - **server_name**: Path parameter, validated by `validate_server_exists`.
    - **Request body**: Expects a :class:`.RestoreActionPayload`.
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Restore action '{payload.restore_type}' requested for server '{server_name}' by user '{identity}'."
    )

    valid_types = ["world", "properties", "allowlist", "permissions", "all"]
    restore_type_lower = payload.restore_type.lower()

    if restore_type_lower not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid 'restore_type'. Must be one of: {valid_types}.",
        )

    if restore_type_lower != "all" and (
        not payload.backup_file or not isinstance(payload.backup_file, str)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid 'backup_file' for this restore type.",
        )

    if payload.backup_file and (
        ".." in payload.backup_file or payload.backup_file.startswith(("/", "\\"))
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 'backup_file' path.",
        )

    tasks.add_task(
        restore_action_task, server_name, restore_type_lower, payload.backup_file
    )

    return GeneralResponse(
        status="success",
        message=f"Restore action '{payload.restore_type}' for server '{server_name}' initiated in background.",
    )

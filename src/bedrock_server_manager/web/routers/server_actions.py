# bedrock_server_manager/web/routers/server_actions.py
"""
FastAPI router for server lifecycle actions and command execution.

This module defines API endpoints for managing the operational state of
Bedrock server instances, including starting, stopping, restarting, updating,
and deleting servers. It also provides an endpoint for sending commands to
a running server.

Most long-running operations (start, stop, restart, update, delete) are
executed as background tasks to provide immediate API responses.
User authentication and server existence are typically verified using
FastAPI dependencies.
"""

import logging
from typing import Dict, Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    Body,
    status,
    Path,
)
from pydantic import BaseModel, Field

from bedrock_server_manager.web.auth_utils import get_current_user
from ..dependencies import validate_server_exists
from bedrock_server_manager.api import server as server_api, server_install_config
from bedrock_server_manager.error import (
    BSMError,
    UserInputError,
    ServerNotRunningError,
    BlockedCommandError,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Server Actions API"])


# --- Pydantic Models ---
class CommandPayload(BaseModel):
    """Request model for sending a command to a server."""

    command: str = Field(
        ..., min_length=1, description="The command to send to the server."
    )


class ActionResponse(BaseModel):
    """Generic response model for actions, indicating status and message."""

    status: str = "success"
    message: str
    details: Optional[Any] = None


# --- Helper for background task logging ---
def log_background_task_result(
    task_name: str, server_name: str, result: Dict[str, Any]
):
    """Logs the outcome of a background server operation.

    Args:
        task_name (str): The name of the background task (e.g., "start_server").
        server_name (str): The name of the server the task was performed on.
        result (Dict[str, Any]): The result dictionary returned by the API function
            called by the background task. Expected to have a "status" key.
    """
    if result.get("status") == "success":
        logger.info(
            f"Background task '{task_name}' for server '{server_name}': Succeeded. {result.get('message')}"
        )
    else:
        logger.error(
            f"Background task '{task_name}' for server '{server_name}': Failed. {result.get('message')}"
        )


def server_start_task(server_name: str):
    """Background task to start a server.

    Calls :func:`bedrock_server_manager.api.server.start_server` in detached mode
    and logs the result using :func:`.log_background_task_result`.
    Catches and logs exceptions during the task execution.

    Args:
        server_name (str): The name of the server to start.
    """
    logger.info(f"Background task initiated: Starting server '{server_name}'.")
    try:
        result = server_api.start_server(server_name, mode="detached")
        log_background_task_result("start_server", server_name, result)
    except UserInputError as e_thread:
        logger.warning(
            f"Background task 'start_server' for '{server_name}': Input error. {e_thread}"
        )
    except BSMError as e_thread:
        logger.error(
            f"Background task 'start_server' for '{server_name}': Application error. {e_thread}"
        )
    except Exception as e_thread:
        logger.error(
            f"Background task 'start_server' for '{server_name}': Unexpected error. {e_thread}",
            exc_info=True,
        )


# --- API Route: Start Server ---
@router.post(
    "/api/server/{server_name}/start",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a server instance",
)
async def start_server_route(
    background_tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates starting a specific Bedrock server instance in the background.

    The server start operation is performed as a background task.
    This endpoint immediately returns a 202 Accepted response indicating
    the task has been queued.

    - **server_name**: Path parameter, validated by `validate_server_exists` dependency.
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Start server request for '{server_name}' by user '{identity}'.")

    background_tasks.add_task(server_start_task, server_name)

    return ActionResponse(
        message=f"Start operation for server '{server_name}' initiated in background."
    )


def server_stop_task(server_name: str):
    """Background task to stop a server.

    Calls :func:`bedrock_server_manager.api.server.stop_server`
    and logs the result using :func:`.log_background_task_result`.
    Catches and logs exceptions during the task execution.

    Args:
        server_name (str): The name of the server to stop.
    """
    logger.info(f"Background task initiated: Stopping server '{server_name}'.")
    try:
        result = server_api.stop_server(server_name)
        log_background_task_result("stop_server", server_name, result)
    except UserInputError as e_thread:
        logger.warning(
            f"Background task 'stop_server' for '{server_name}': Input error. {e_thread}"
        )
    except BSMError as e_thread:
        logger.error(
            f"Background task 'stop_server' for '{server_name}': Application error. {e_thread}"
        )
    except Exception as e_thread:
        logger.error(
            f"Background task 'stop_server' for '{server_name}': Unexpected error. {e_thread}",
            exc_info=True,
        )


@router.post(
    "/api/server/{server_name}/stop",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Stop a running server instance",
)
async def stop_server_route(
    background_tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates stopping a specific Bedrock server instance in the background.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Stop server request for '{server_name}' by user '{identity}'.")

    background_tasks.add_task(server_stop_task, server_name)

    return ActionResponse(
        message=f"Stop operation for server '{server_name}' initiated in background."
    )


def server_restart_task(server_name: str):
    """Background task to restart a server.

    Calls :func:`bedrock_server_manager.api.server.restart_server`
    and logs the result using :func:`.log_background_task_result`.
    Catches and logs exceptions during the task execution.

    Args:
        server_name (str): The name of the server to restart.
    """
    logger.info(f"Background task initiated: Restarting server '{server_name}'.")
    try:
        result = server_api.restart_server(server_name)
        log_background_task_result("restart_server", server_name, result)
    except UserInputError as e_thread:
        logger.warning(
            f"Background task 'restart_server' for '{server_name}': Input error. {e_thread}"
        )
    except BSMError as e_thread:
        logger.error(
            f"Background task 'restart_server' for '{server_name}': Application error. {e_thread}"
        )
    except Exception as e_thread:
        logger.error(
            f"Background task 'restart_server' for '{server_name}': Unexpected error. {e_thread}",
            exc_info=True,
        )


@router.post(
    "/api/server/{server_name}/restart",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Restart a server instance",
)
async def restart_server_route(
    background_tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates restarting a specific Bedrock server instance in the background.

    The server restart operation (stop followed by start) is performed as a
    background task. This endpoint immediately returns a 202 Accepted response.

    - **server_name**: Path parameter, validated by `validate_server_exists` dependency.
    - Requires authentication.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Restart server request for '{server_name}' by user '{identity}'."
    )

    background_tasks.add_task(server_restart_task, server_name)

    return ActionResponse(
        message=f"Restart operation for server '{server_name}' initiated in background."
    )


@router.post(
    "/api/server/{server_name}/send_command",
    response_model=ActionResponse,
    summary="Send a command to a running server instance",
)
async def send_command_route(
    server_name: str,
    payload: CommandPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Sends a command to a specific running Bedrock server instance.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Send command request for '{server_name}' by user '{identity}'. Command: {payload.command}"
    )

    if not payload.command or not payload.command.strip():

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request must contain a non-empty 'command'.",
        )

    try:

        command_result = server_api.send_command(server_name, payload.command.strip())

        if command_result.get("status") == "success":
            logger.info(
                f"API Send Command '{server_name}': Succeeded. Output: {command_result.get('details')}"
            )
            return ActionResponse(
                status="success",
                message=command_result.get("message", "Command processed."),
                details=command_result.get("details"),
            )
        else:
            logger.warning(
                f"API Send Command '{server_name}': Failed. {command_result.get('message')}"
            )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=command_result.get("message", "Failed to execute command."),
            )

    except BlockedCommandError as e:
        logger.warning(
            f"API Send Command '{server_name}': Blocked command attempt. {e}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ServerNotRunningError as e:
        logger.warning(f"API Send Command '{server_name}': Server not running. {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except (
        UserInputError
    ) as e:  # Covers InvalidServerNameError, AppFileNotFoundError from original
        logger.warning(f"API Send Command '{server_name}': Input error. {e}")
        # Determine if it's a 404 or 400 based on error type if possible
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BSMError as e:  # Catch other BSM specific errors
        logger.error(
            f"API Send Command '{server_name}': Application error. {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"API Send Command '{server_name}': Unexpected error. {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while sending the command.",
        )


def server_update_task(server_name: str):
    """Background task to update a server.

    Calls :func:`bedrock_server_manager.api.server_install_config.update_server`
    and logs the result using :func:`.log_background_task_result`.
    Catches and logs exceptions during the task execution.

    Args:
        server_name (str): The name of the server to update.
    """
    logger.info(f"Background task initiated: Updating server '{server_name}'.")
    try:
        result = server_install_config.update_server(server_name)
        log_background_task_result("update_server", server_name, result)
    except UserInputError as e_thread:
        logger.warning(
            f"Background task 'update_server' for '{server_name}': Input error. {e_thread}"
        )
    except BSMError as e_thread:
        logger.error(
            f"Background task 'update_server' for '{server_name}': Application error. {e_thread}"
        )
    except Exception as e_thread:
        logger.error(
            f"Background task 'update_server' for '{server_name}': Unexpected error. {e_thread}",
            exc_info=True,
        )


@router.post(
    "/api/server/{server_name}/update",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Update a server instance to the latest version",
)
async def update_server_route(
    server_name: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates updating a specific Bedrock server instance in the background.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Update server request for '{server_name}' by user '{identity}'.")

    background_tasks.add_task(server_update_task, server_name)

    return ActionResponse(
        message=f"Update operation for server '{server_name}' initiated in background."
    )


def server_delete_task(server_name: str):
    """Background task to delete a server's data.

    Calls :func:`bedrock_server_manager.api.server.delete_server_data`
    and logs the result using :func:`.log_background_task_result`.
    Catches and logs exceptions during the task execution.

    Args:
        server_name (str): The name of the server whose data is to be deleted.
    """
    logger.info(f"Background task initiated: Deleting server data for '{server_name}'.")
    try:
        result = server_api.delete_server_data(server_name)
        log_background_task_result("delete_server_data", server_name, result)
    except UserInputError as e_thread:
        logger.warning(
            f"Background task 'delete_server_data' for '{server_name}': Input error. {e_thread}"
        )
    except BSMError as e_thread:
        logger.error(
            f"Background task 'delete_server_data' for '{server_name}': Application error. {e_thread}"
        )
    except Exception as e_thread:
        logger.error(
            f"Background task 'delete_server_data' for '{server_name}': Unexpected error. {e_thread}",
            exc_info=True,
        )


@router.delete(
    "/api/server/{server_name}/delete",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete a server instance and its data",
)
async def delete_server_route(
    server_name: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates deleting a specific Bedrock server instance and its data in the background.
    """
    identity = current_user.get("username", "Unknown")
    logger.warning(
        f"API: DELETE server data request for '{server_name}' by user '{identity}'. This is a destructive operation."
    )

    background_tasks.add_task(server_delete_task, server_name)

    return ActionResponse(
        message=f"Delete operation for server '{server_name}' initiated in background."
    )

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
from typing import Dict, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    status,
)
from pydantic import BaseModel, Field

from ..schemas import ActionResponse
from ..auth_utils import get_current_user
from ..dependencies import validate_server_exists
from ...api import server as server_api, server_install_config
from ...error import (
    BSMError,
    UserInputError,
    ServerNotRunningError,
    BlockedCommandError,
)
from .. import tasks

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Pydantic Models ---
class CommandPayload(BaseModel):
    """Request model for sending a command to a server."""

    command: str = Field(
        ..., min_length=1, description="The command to send to the server."
    )


# --- API Route: Start Server ---
@router.post(
    "/api/server/{server_name}/start",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a server instance",
    tags=["Server Actions API"],
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

    Args:
        background_tasks (BackgroundTasks): FastAPI background tasks utility.
        server_name (str): The name of the server to start. Validated by dependency.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        ActionResponse: Confirmation that the start operation has been initiated.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Start server request for '{server_name}' by user '{identity}'.")
    task_id = tasks.create_task()
    background_tasks.add_task(
        tasks.run_task,
        task_id,
        server_api.start_server,
        server_name,
        mode="detached",
    )

    return ActionResponse(
        status="pending",
        message=f"Start operation for server '{server_name}' initiated in background.",
        task_id=task_id,
    )


@router.post(
    "/api/server/{server_name}/stop",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Stop a running server instance",
    tags=["Server Actions API"],
)
async def stop_server_route(
    background_tasks: BackgroundTasks,
    server_name: str = Depends(validate_server_exists),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates stopping a specific Bedrock server instance in the background.

    The server stop operation is performed as a background task.
    This endpoint immediately returns a 202 Accepted response.

    Args:
        background_tasks (BackgroundTasks): FastAPI background tasks utility.
        server_name (str): The name of the server to stop. Validated by dependency.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        ActionResponse: Confirmation that the stop operation has been initiated.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Stop server request for '{server_name}' by user '{identity}'.")
    task_id = tasks.create_task()
    background_tasks.add_task(
        tasks.run_task,
        task_id,
        server_api.stop_server,
        server_name,
    )

    return ActionResponse(
        status="pending",
        message=f"Stop operation for server '{server_name}' initiated in background.",
        task_id=task_id,
    )


@router.post(
    "/api/server/{server_name}/restart",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Restart a server instance",
    tags=["Server Actions API"],
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

    Args:
        background_tasks (BackgroundTasks): FastAPI background tasks utility.
        server_name (str): The name of the server to restart. Validated by dependency.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        ActionResponse: Confirmation that the restart operation has been initiated.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(
        f"API: Restart server request for '{server_name}' by user '{identity}'."
    )
    task_id = tasks.create_task()
    background_tasks.add_task(
        tasks.run_task,
        task_id,
        server_api.restart_server,
        server_name,
    )

    return ActionResponse(
        status="pending",
        message=f"Restart operation for server '{server_name}' initiated in background.",
        task_id=task_id,
    )


@router.post(
    "/api/server/{server_name}/send_command",
    response_model=ActionResponse,
    summary="Send a command to a running server instance",
    tags=["Server Actions API"],
)
async def send_command_route(
    server_name: str,
    payload: CommandPayload,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Sends a command to a specific running Bedrock server instance.

    The underlying API call (:func:`~bedrock_server_manager.api.server.send_command`)
    checks the command against a blacklist.

    Args:
        server_name (str): The name of the server to send the command to.
        payload (CommandPayload): Contains the ``command`` string.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        ActionResponse:
            - ``status``: "success" or "error" (if HTTPExceptions are not raised first for specific errors)
            - ``message``: Outcome of the command execution.
            - ``details``: (Optional) Any output or details from the command if successful.

    Raises:
        HTTPException:
            - 400 (Bad Request): If command is empty or underlying API call fails.
            - 403 (Forbidden): If the command is blocked.
            - 404 (Not Found): If the server name is invalid.
            - 409 (Conflict): If the server is not running.
            - 500 (Internal Server Error): For other unexpected errors.

    Example Request Body:
    .. code-block:: json

        {
            "command": "list"
        }

    Example Response (Success):
    .. code-block:: json

        {
            "status": "success",
            "message": "Command 'list' sent successfully.",
            "details": "There are 0/10 players online:\\n"
        }
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


@router.post(
    "/api/server/{server_name}/update",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Update a server instance to the latest version",
    tags=["Server Actions API"],
)
async def update_server_route(
    server_name: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates updating a specific Bedrock server instance in the background.

    The server update operation is performed as a background task.
    This endpoint immediately returns a 202 Accepted response.

    Args:
        server_name (str): The name of the server to update.
        background_tasks (BackgroundTasks): FastAPI background tasks utility.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        ActionResponse: Confirmation that the update operation has been initiated.
    """
    identity = current_user.get("username", "Unknown")
    logger.info(f"API: Update server request for '{server_name}' by user '{identity}'.")
    task_id = tasks.create_task()
    background_tasks.add_task(
        tasks.run_task,
        task_id,
        server_install_config.update_server,
        server_name,
    )

    return ActionResponse(
        status="pending",
        message=f"Update operation for server '{server_name}' initiated in background.",
        task_id=task_id,
    )


@router.delete(
    "/api/server/{server_name}/delete",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete a server instance and its data",
    tags=["Server Actions API"],
)
async def delete_server_route(
    server_name: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Initiates deleting a specific Bedrock server instance and its data in the background.

    This is a **DESTRUCTIVE** operation. The deletion is performed as a background task.
    This endpoint immediately returns a 202 Accepted response.

    Args:
        server_name (str): The name of the server to delete.
        background_tasks (BackgroundTasks): FastAPI background tasks utility.
        current_user (Dict[str, Any]): Authenticated user object.

    Returns:
        ActionResponse: Confirmation that the delete operation has been initiated.
    """
    identity = current_user.get("username", "Unknown")
    logger.warning(
        f"API: DELETE server data request for '{server_name}' by user '{identity}'. This is a destructive operation."
    )
    task_id = tasks.create_task()
    background_tasks.add_task(
        tasks.run_task,
        task_id,
        server_api.delete_server_data,
        server_name,
    )

    return ActionResponse(
        status="pending",
        message=f"Delete operation for server '{server_name}' initiated in background.",
        task_id=task_id,
    )

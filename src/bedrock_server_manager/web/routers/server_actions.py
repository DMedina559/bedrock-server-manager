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
    status,
    Request,
)
from pydantic import BaseModel, Field

from ..schemas import ActionResponse, User
from ..auth_utils import get_current_user
from ..dependencies import validate_server_exists, get_app_context
from ..auth_utils import get_admin_user, get_moderator_user
from ...api import server as server_api, server_install_config
from ...error import (
    BSMError,
    UserInputError,
    ServerNotRunningError,
    BlockedCommandError,
)
from ...context import AppContext

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
    status_code=status.HTTP_200_OK,
    summary="Start a server instance",
    tags=["Server Actions API"],
)
async def start_server_route(
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Starts a specific Bedrock server instance.
    """
    identity = current_user.username
    logger.info(f"API: Start server request for '{server_name}' by user '{identity}'.")

    try:
        result = server_api.start_server(
            server_name=server_name, app_context=app_context
        )
        if result.get("status") == "success":
            return ActionResponse(
                message=result.get("message") or "Server started successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message"),
            )
    except BSMError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/api/server/{server_name}/stop",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Stop a running server instance",
    tags=["Server Actions API"],
)
async def stop_server_route(
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates stopping a specific Bedrock server instance in the background.

    The server stop operation is performed as a background task.
    This endpoint immediately returns a 202 Accepted response.
    """
    identity = current_user.username
    logger.info(f"API: Stop server request for '{server_name}' by user '{identity}'.")
    task_id = app_context.task_manager.run_task(
        server_api.stop_server,
        username=current_user.username,
        server_name=server_name,
        app_context=app_context,
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
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates restarting a specific Bedrock server instance in the background.

    The server restart operation (stop followed by start) is performed as a
    background task. This endpoint immediately returns a 202 Accepted response.
    """
    identity = current_user.username
    logger.info(
        f"API: Restart server request for '{server_name}' by user '{identity}'."
    )
    task_id = app_context.task_manager.run_task(
        server_api.restart_server,
        username=current_user.username,
        server_name=server_name,
        app_context=app_context,
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
    payload: CommandPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: User = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Sends a command to a specific running Bedrock server instance.
    """
    identity = current_user.username
    logger.info(
        f"API: Send command request for '{server_name}' by user '{identity}'. Command: {payload.command}"
    )

    if not payload.command or not payload.command.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request must contain a non-empty 'command'.",
        )

    try:
        command_result = server_api.send_command(
            server_name=server_name,
            command=payload.command.strip(),
            app_context=app_context,
        )

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
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates updating a specific Bedrock server instance in the background.

    The server update operation is performed as a background task.
    This endpoint immediately returns a 202 Accepted response.
    """
    identity = current_user.username
    logger.info(f"API: Update server request for '{server_name}' by user '{identity}'.")
    task_id = app_context.task_manager.run_task(
        server_install_config.update_server,
        username=current_user.username,
        server_name=server_name,
        app_context=app_context,
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
    current_user: User = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
):
    """
    Initiates deleting a specific Bedrock server instance and its data in the background.

    This is a **DESTRUCTIVE** operation. The deletion is performed as a background task.
    This endpoint immediately returns a 202 Accepted response.
    """
    identity = current_user.username
    logger.warning(
        f"API: DELETE server data request for '{server_name}' by user '{identity}'. This is a destructive operation."
    )
    task_id = app_context.task_manager.run_task(
        server_api.delete_server_data,
        username=current_user.username,
        server_name=server_name,
        app_context=app_context,
    )

    return ActionResponse(
        status="pending",
        message=f"Delete operation for server '{server_name}' initiated in background.",
        task_id=task_id,
    )

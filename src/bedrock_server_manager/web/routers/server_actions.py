# bedrock_server_manager/web/routers/server_actions.py
"""
FastAPI router for server lifecycle actions and command execution.

This module defines API endpoints for managing the operational state of
Bedrock server instances, including starting, stopping, restarting, updating,
and deleting servers. It also provides an endpoint for sending commands to
a running server.

Process lifecycle operations are awaited directly and return their operation
results. Updates and deletions use tracked background tasks.
User authentication and server existence are typically verified using
FastAPI dependencies.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from bedrock_server_manager.api.models import (
    DeleteServerDataRequest,
    GetServerSummaryRequest,
    SendCommandRequest,
    UpdateServerRequest,
)

from ...api import install
from ...api import server as server_api
from ...api.models import (
    RestartServerRequest,
    RestartServerResponse,
    StartServerRequest,
    StartServerResponse,
    StopServerRequest,
    StopServerResponse,
)
from ...context import AppContext
from ...error import (
    AppFileNotFoundError,
    BlockedCommandError,
    BSMError,
    ServerNotRunningError,
    UserInputError,
)
from ..deps import (
    get_admin_user,
    get_app_context,
    get_moderator_user,
    validate_server_exists,
)
from ..schemas import ActionResponse, CommandPayload, ServerSchemaResponse, UserResponse
from ..schemas.base import TaskAcceptedResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Server Mannagement"],
)


@router.get(
    "/api/server/{server_name}/summary",
    operation_id="get_server_summary",
    response_model=ServerSchemaResponse,
    tags=["Server Information"],
)
async def get_server_summary(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> ServerSchemaResponse:
    """
    Retrieves the basic summary information for a specific server instance.
    """
    identity = current_user.username
    logger.info(
        f"API: Get server summary request for '{server_name}' by user '{identity}'."
    )

    result = await server_api.get_server_summary(
        request=GetServerSummaryRequest(server_name=server_name),
        app_context=app_context,
    )

    return ServerSchemaResponse.model_validate(result.summary)


# --- API Route: Start Server ---
@router.post(
    "/api/server/{server_name}/start",
    operation_id="start_server",
    response_model=StartServerResponse,
    status_code=status.HTTP_200_OK,
    tags=["Process Management"],
)
async def post_start_server(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> StartServerResponse:
    """Await server start and return its completed operation result."""
    logger.info(
        "API: Start server request for '%s' by user '%s'.",
        server_name,
        current_user.username,
    )
    return await server_api.start_server(
        request=StartServerRequest(server_name=server_name),
        app_context=app_context,
    )


@router.post(
    "/api/server/{server_name}/stop",
    operation_id="stop_server",
    response_model=StopServerResponse,
    status_code=status.HTTP_200_OK,
    tags=["Process Management"],
)
async def post_stop_server(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> StopServerResponse:
    """Await server stop and return its completed operation result."""
    logger.info(
        "API: Stop server request for '%s' by user '%s'.",
        server_name,
        current_user.username,
    )
    return await server_api.stop_server(
        request=StopServerRequest(server_name=server_name),
        app_context=app_context,
    )


@router.post(
    "/api/server/{server_name}/restart",
    operation_id="restart_server",
    response_model=RestartServerResponse,
    status_code=status.HTTP_200_OK,
    tags=["Process Management"],
)
async def post_restart_server(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> RestartServerResponse:
    """Await server restart and return its completed operation result."""
    logger.info(
        "API: Restart server request for '%s' by user '%s'.",
        server_name,
        current_user.username,
    )
    return await server_api.restart_server(
        request=RestartServerRequest(server_name=server_name),
        app_context=app_context,
    )


@router.post(
    "/api/server/{server_name}/send_command",
    operation_id="send_command",
    response_model=ActionResponse,
    tags=["Send Command"],
)
async def post_send_command(
    payload: CommandPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> ActionResponse:
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
        command_result = await server_api.send_command(
            request=SendCommandRequest(
                server_name=server_name, command=payload.command.strip()
            ),
            app_context=app_context,
        )

        logger.info(f"API Send Command '{server_name}': Succeeded.")
        return ActionResponse(
            status=command_result.status,
            message=command_result.message,
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
    except HTTPException:
        raise
    except AppFileNotFoundError:
        raise
    except BSMError as e:  # Catch other BSM specific errors
        logger.error(
            f"API Send Command '{server_name}': Application error. {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValidationError:
        raise
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
    operation_id="update_server",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Server Installation"],
)
async def post_update_server(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates updating a specific Bedrock server instance in the background.

    The server update operation is performed as a background task.
    This endpoint immediately returns a 202 Accepted response.
    """
    identity = current_user.username
    logger.info(f"API: Update server request for '{server_name}' by user '{identity}'.")
    task_id = await app_context.task_manager.run_task(
        install.update_server,
        username=current_user.username,
        app_context=app_context,
        request=UpdateServerRequest(server_name=server_name),
    )

    return TaskAcceptedResponse(
        status="accepted",
        message=f"Update operation for server '{server_name}' initiated in background.",
        task_id=task_id,
    )


@router.delete(
    "/api/server/{server_name}/delete",
    operation_id="delete_server",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Server Installation"],
)
async def delete_server(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_admin_user),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates deleting a specific Bedrock server instance and its data in the background.

    This is a **DESTRUCTIVE** operation. The deletion is performed as a background task.
    This endpoint immediately returns a 202 Accepted response.
    """
    identity = current_user.username
    logger.warning(
        f"API: DELETE server data request for '{server_name}' by user '{identity}'. This is a destructive operation."
    )
    task_id = await app_context.task_manager.run_task(
        server_api.delete_server_data,
        username=current_user.username,
        app_context=app_context,
        request=DeleteServerDataRequest(server_name=server_name),
    )

    return TaskAcceptedResponse(
        status="accepted",
        message=f"Delete operation for server '{server_name}' initiated in background.",
        task_id=task_id,
    )

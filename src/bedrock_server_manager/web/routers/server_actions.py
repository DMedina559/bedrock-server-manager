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

from bedrock_server_manager.api.models import (
    DeleteServerDataRequest,
    GetServerSummaryRequest,
    SendCommandRequest,
    SendCommandResponse,
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
from ..deps import (
    get_admin_user,
    get_app_context,
    get_moderator_user,
    validate_server_exists,
)
from ..deps.server import validate_server_registered
from ..schemas import CommandPayload, ServerSchemaResponse, UserResponse
from ..schemas.base import TaskAcceptedResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/api/server/{server_name}/summary",
    operation_id="get_server_summary",
    tags=["Server Management"],
    response_model=ServerSchemaResponse,
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
    logger.debug(
        "Get server summary request for '%s' by user '%s'.", server_name, identity
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
    tags=["Server Processes"],
    response_model=StartServerResponse,
    status_code=status.HTTP_200_OK,
)
async def post_start_server(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> StartServerResponse:
    """Await server start and return its completed operation result."""
    logger.info(
        "Start server request for '%s' by user '%s'.",
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
    tags=["Server Processes"],
    response_model=StopServerResponse,
    status_code=status.HTTP_200_OK,
)
async def post_stop_server(
    server_name: str = Depends(validate_server_registered),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> StopServerResponse:
    """Await server stop and return its completed operation result."""
    logger.info(
        "Stop server request for '%s' by user '%s'.", server_name, current_user.username
    )
    return await server_api.stop_server(
        request=StopServerRequest(server_name=server_name),
        app_context=app_context,
    )


@router.post(
    "/api/server/{server_name}/restart",
    operation_id="restart_server",
    tags=["Server Processes"],
    response_model=RestartServerResponse,
    status_code=status.HTTP_200_OK,
)
async def post_restart_server(
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> RestartServerResponse:
    """Await server restart and return its completed operation result."""
    logger.info(
        "Restart server request for '%s' by user '%s'.",
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
    tags=["Server Processes"],
    response_model=SendCommandResponse,
)
async def post_send_command(
    payload: CommandPayload,
    server_name: str = Depends(validate_server_exists),
    current_user: UserResponse = Depends(get_moderator_user),
    app_context: AppContext = Depends(get_app_context),
) -> SendCommandResponse:
    """
    Sends a command to a specific running Bedrock server instance.
    """
    identity = current_user.username
    logger.info(
        "Command requested for server '%s' by user '%s'.", server_name, identity
    )

    if not payload.command or not payload.command.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request must contain a non-empty 'command'.",
        )

    command_result = await server_api.send_command(
        request=SendCommandRequest(
            server_name=server_name, command=payload.command.strip()
        ),
        app_context=app_context,
    )

    logger.debug("API Send Command '%s': Succeeded.", server_name)
    return command_result


@router.post(
    "/api/server/{server_name}/update",
    operation_id="update_server",
    tags=["Server Management"],
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
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
    logger.info("Update server request for '%s' by user '%s'.", server_name, identity)
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
    tags=["Server Management"],
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
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
    logger.info(
        "Server deletion requested for '%s' by user '%s'.", server_name, identity
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

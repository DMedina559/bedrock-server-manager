"""FastAPI router for server lifecycle actions and command execution."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status

from ...api import application as app_api
from ...api import install
from ...api import server as server_api
from ...api import system as system_api
from ...context import AppContext
from ...models import (
    CommandPayload,
    DeleteServerDataRequest,
    GetAllServersDataRequest,
    GetAllServersDataResponse,
    GetBedrockProcessInfoRequest,
    GetBedrockProcessInfoResponse,
    GetServerProcessRequest,
    GetServerProcessResponse,
    GetServerRunningStatusRequest,
    GetServerRunningStatusResponse,
    GetServerSummaryRequest,
    RestartServerRequest,
    RestartServerResponse,
    SendCommandRequest,
    SendCommandResponse,
    ServerSummary,
    StartServerRequest,
    StartServerResponse,
    StopServerRequest,
    StopServerResponse,
    TaskAcceptedResponse,
    UpdateServerRequest,
)
from ..access_metadata import describe_access
from ..access_policy import Permission
from ..authorization import current_authorization, server_collection
from ..deps import get_app_context, validate_server_exists
from ..deps.auth import require_permissions, require_recent_interactive
from ..deps.server import validate_server_registered
from ..schemas import BaseApiResponse, UserResponse

# bedrock_server_manager/web/routers/server_actions.py


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/api/server/{server_name}/summary",
    operation_id="get_server_summary",
    tags=["Server Management"],
    response_model=ServerSummary,
)
async def get_server_summary(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_INSPECT]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> ServerSummary:
    """Return the basic summary information for a specific server instance."""
    identity = current_user.username
    logger.debug(
        "Get server summary request for '%s' by user '%s'.", server_name, identity
    )

    result = await server_api.get_server_summary(
        request=GetServerSummaryRequest(server_name=server_name),
        app_context=app_context,
    )

    return ServerSummary.model_validate(result.summary)


@router.get(
    "/api/server/{server_name}/process",
    operation_id="get_server_process",
    tags=["Server Management"],
    response_model=GetServerProcessResponse,
)
async def get_server_process(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_INSPECT]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> GetServerProcessResponse:
    """Inspect process ownership, live capabilities and failure evidence."""
    return await server_api.get_server_process(
        GetServerProcessRequest(server_name=server_name), app_context=app_context
    )


# --- API Route: Start Server ---
@router.post(
    "/api/server/{server_name}/start",
    operation_id="start_server",
    tags=["Server Processes"],
    response_model=StartServerResponse,
    status_code=status.HTTP_200_OK,
)
async def post_start_server(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_LIFECYCLE]
    ),
    server_name: str = Depends(validate_server_exists),
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
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_LIFECYCLE]
    ),
    server_name: str = Depends(validate_server_registered),
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
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_LIFECYCLE]
    ),
    server_name: str = Depends(validate_server_exists),
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
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_COMMAND]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> SendCommandResponse:
    """
    Sends a command to a specific running Bedrock server instance.
    """
    identity = current_user.username
    logger.info(
        "Command requested for server '%s' by user '%s'.", server_name, identity
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
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_INSTALL]
    ),
    server_name: str = Depends(validate_server_exists),
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
@describe_access(
    "permission",
    additional_checks=["recent-interactive-verification"],
)
async def delete_server(
    request: Request,
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_DELETE]
    ),
    server_name: str = Depends(validate_server_registered),
    app_context: AppContext = Depends(get_app_context),
) -> TaskAcceptedResponse:
    """
    Initiates deleting a specific Bedrock server instance and its data in the background.

    This is a **DESTRUCTIVE** operation. The deletion is performed as a background task.
    This endpoint immediately returns a 202 Accepted response.
    """
    await require_recent_interactive(request, current_user, app_context)
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


@router.get(
    "/api/server/{server_name}/status",
    operation_id="get_server_status",
    tags=["Server Processes"],
    response_model=GetServerRunningStatusResponse,
)
async def get_server_running_status(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_READ]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> GetServerRunningStatusResponse:
    """Check if a specific server's process is currently running."""
    identity = current_user.username
    logger.debug(
        "Request for running status for server '%s' by user '%s'.",
        server_name,
        identity,
    )
    return await system_api.get_server_running_status(
        request=GetServerRunningStatusRequest(server_name=server_name),
        app_context=app_context,
    )


@router.get(
    "/api/server/{server_name}/validate",
    operation_id="validate_server",
    tags=["Server Management"],
    response_model=BaseApiResponse,
)
async def get_validate_server(
    server_name: str,
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> BaseApiResponse:
    """
    Validates if a server installation exists and is minimally correct.
    """
    identity = current_user.username
    logger.debug("Request to validate server '%s' by user '%s'.", server_name, identity)
    from ...utils.server import validate_server

    if await validate_server(server_name=server_name, app_context=app_context):
        return BaseApiResponse(
            status="success", message=f"Server '{server_name}' exists and is valid."
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' is not installed or the installation is invalid.",
        )


@router.get(
    "/api/server/{server_name}/process_info",
    operation_id="get_server_process_info",
    tags=["Server Processes"],
    response_model=GetBedrockProcessInfoResponse,
)
async def get_server_process_info(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_READ]
    ),
    server_name: str = Depends(validate_server_exists),
    app_context: AppContext = Depends(get_app_context),
) -> GetBedrockProcessInfoResponse:
    """Return resource usage information for a running server process."""
    identity = current_user.username
    logger.debug("Process info request for '%s' by user '%s'.", server_name, identity)
    return await system_api.get_bedrock_process_info(
        request=GetBedrockProcessInfoRequest(server_name=server_name),
        app_context=app_context,
    )


@router.get(
    "/api/servers",
    operation_id="list_servers",
    tags=["Server Management"],
    response_model=GetAllServersDataResponse,
)
@server_collection
async def get_servers_list(
    current_user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_READ]
    ),
    app_context: AppContext = Depends(get_app_context),
) -> GetAllServersDataResponse:
    """Return a list of all detected server instances with their status and version."""
    identity = current_user.username
    logger.debug("Request for all servers list by user '%s'.", identity)
    result = await app_api.get_all_servers_data(
        request=GetAllServersDataRequest(), app_context=app_context
    )
    authorization = current_authorization.get()
    return GetAllServersDataResponse(
        status=result.status,
        errors=[
            error
            for error in result.errors
            if authorization is None
            or authorization.allows(Permission.SERVERS_READ, error.resource)
        ],
        message=result.message,
        servers=[
            server
            for server in result.servers
            if authorization is None
            or authorization.allows(Permission.SERVERS_READ, server.name)
        ],
        epoch=result.epoch,
        revision=result.revision,
    )

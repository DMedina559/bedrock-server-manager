from ..core.server.removal import delete_all_data

# bedrock_server_manager/api/server.py
"""Provides API functions for managing Bedrock server instances.

This module serves as a key interface layer for server-specific operations within
the Bedrock Server Manager. It leverages the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` core class
to perform a variety of actions such as server lifecycle management (starting,
stopping, restarting), configuration (getting/setting server-specific properties),
and command execution.

All operations use Pydantic request and response contracts. These operations
are suitable for consumption by web API routes, command-line
interface (CLI) commands, or other parts of the application. This module also
integrates with the plugin system by exposing many of its functions as callable
APIs for plugins (via :func:`~bedrock_server_manager.plugins.api_bridge.api_method`)
and by triggering various plugin events during server operations.
"""

import logging
import os
from typing import Any, Dict

from ..config import API_COMMAND_BLACKLIST
from ..context import AppContext
from ..core.system import remove_pid_file_if_exists
from ..error import (
    BlockedCommandError,
    BSMError,
    InvalidServerNameError,
    MissingArgumentError,
    ServerError,
)
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from ..plugins.api_contract import validate_contract
from ..plugins.event_trigger import trigger_event
from .models import (
    RestartServerRequest,
    RestartServerResponse,
    StartServerRequest,
    StartServerResponse,
    StopServerRequest,
    StopServerResponse,
)
from .models.server import (
    DeleteServerDataRequest,
    DeleteServerDataResponse,
    GetAllServerSettingsRequest,
    GetAllServerSettingsResponse,
    GetServerSettingRequest,
    GetServerSettingResponse,
    GetServerSummaryRequest,
    GetServerSummaryResponse,
    SendCommandRequest,
    SendCommandResponse,
    SetServerCustomValueRequest,
    SetServerCustomValueResponse,
    SetServerSettingRequest,
    SetServerSettingResponse,
    SetServerStatusRequest,
    SetServerStatusResponse,
    UpdateServerPlayerStatsRequest,
    UpdateServerPlayerStatsResponse,
)

logger = logging.getLogger(__name__)


@api_method("get_server_setting")
async def get_server_setting(
    request: GetServerSettingRequest, *, app_context: AppContext
) -> GetServerSettingResponse:
    """Reads any value from a server's specific persisted configuration

    Accepts GetServerSettingRequest and returns GetServerSettingResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    key = request.key
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not key:
        raise MissingArgumentError("A 'key' must be provided.")
    logger.debug("Reading server setting for '%s': Key='%s'", server_name, key)
    try:
        server = app_context.get_server(server_name)
        value = server.configuration.read(key)
        success_response: Dict[str, Any] = {"status": "success", "value": value}
        return GetServerSettingResponse.model_validate(success_response)
    except BSMError as e:
        log_operation_error(
            logger,
            "Error reading setting '%s' for server '%s': %s",
            key,
            server_name,
            e,
            error=e,
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error reading setting for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise


@validate_contract
@trigger_event(
    before="before_set_server_setting",
    after="after_set_server_setting",
    identity_keys=("server_name", "key"),
)
async def set_server_setting(
    request: SetServerSettingRequest, *, app_context: AppContext
) -> SetServerSettingResponse:
    """Writes any value to a server's specific persisted configuration

    Accepts SetServerSettingRequest and returns SetServerSettingResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    key = request.key
    value = request.value
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not key:
        raise MissingArgumentError("A 'key' must be provided.")
    logger.debug("Updating setting '%s' for server '%s'.", key, server_name)
    try:
        server = app_context.get_server(server_name)
        await server.configuration.update(key, value)
        return SetServerSettingResponse(
            message=f"Setting '{key}' updated for server '{server_name}'."
        )
    except BSMError as e:
        log_operation_error(
            logger,
            "Error setting '%s' for server '%s': %s",
            key,
            server_name,
            e,
            error=e,
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error setting value for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise


@api_method("set_server_custom_value")
async def set_server_custom_value(
    request: SetServerCustomValueRequest, *, app_context: AppContext
) -> SetServerCustomValueResponse:
    """Writes a key-value pair to the 'custom' section of a server's specific

    Accepts SetServerCustomValueRequest and returns SetServerCustomValueResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    key = request.key
    value = request.value
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not key:
        raise MissingArgumentError("A 'key' must be provided.")
    logger.debug("Writing custom value for '%s': Key='%s'", server_name, key)
    try:
        server = app_context.get_server(server_name)
        await server.set_custom_config_value(key, value)
        return SetServerCustomValueResponse(
            message=f"Custom value '{key}' updated for server '{server_name}'."
        )
    except BSMError as e:
        log_operation_error(
            logger, "Error setting custom value for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error setting custom value for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise


@api_method("get_all_server_settings")
async def get_all_server_settings(
    request: GetAllServerSettingsRequest, *, app_context: AppContext
) -> GetAllServerSettingsResponse:
    """Reads the entire persisted configurationuration for a specific server from its

    Accepts GetAllServerSettingsRequest and returns GetAllServerSettingsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    logger.debug("Reading all settings for server '%s'.", server_name)
    try:
        server = app_context.get_server(server_name)
        all_settings = server.configuration.as_settings()
        success_response: Dict[str, Any] = {
            "status": "success",
            "settings": all_settings,
        }
        return GetAllServerSettingsResponse.model_validate(success_response)
    except BSMError as e:
        log_operation_error(
            logger,
            "Error reading all settings for server '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error reading all settings for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise


@api_method("get_server_summary")
async def get_server_summary(
    request: GetServerSummaryRequest, *, app_context: AppContext
) -> GetServerSummaryResponse:
    """Retrieves the summary information for a specific server.

    Accepts GetServerSummaryRequest and returns GetServerSummaryResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    logger.debug("Requesting summary info for server '%s'.", server_name)
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    try:
        server = app_context.get_server(server_name)
        if not await server.is_installed():
            raise BSMError(f"Server '{server_name}' is not installed.")
        summary = await server.get_summary_info()
        return GetServerSummaryResponse.model_validate(
            {"status": "success", "summary": summary.model_dump(mode="json")}
        )
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error getting summary for server '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise


@api_method("start_server")
@trigger_event(
    before="before_server_start",
    after="after_server_start",
    identity_keys=("server_name",),
)
async def start_server(
    request: StartServerRequest, *, app_context: AppContext
) -> StartServerResponse:
    """Start a server, or report that it is already running; failures raise."""
    server_name = request.server_name
    server = app_context.get_server(server_name)
    async with server.operation_lock:
        if await server.is_running():
            return StartServerResponse(
                server_name=server_name,
                outcome="already_running",
                message=f"Server '{server_name}' is already running.",
            )

        await server.start()
        await app_context.bedrock_process_manager.add_server(server)
        logger.debug("Start for server '%s' completed.", server_name)
        return StartServerResponse(
            server_name=server_name,
            outcome="started",
            message=f"Server '{server_name}' process started.",
        )


@api_method("stop_server")
@trigger_event(
    before="before_server_stop",
    after="after_server_stop",
    identity_keys=("server_name",),
)
async def stop_server(
    request: StopServerRequest, *, app_context: AppContext
) -> StopServerResponse:
    """Stop a server, or report that it is already stopped; failures raise."""
    server_name = request.server_name
    server = app_context.get_server(server_name)
    async with server.operation_lock:
        stopped = False
        try:
            if not await server.is_running():
                await server.set_status_in_config("STOPPED")
                stopped = True
                return StopServerResponse(
                    server_name=server_name,
                    outcome="already_stopped",
                    message=f"Server '{server_name}' was already stopped.",
                )

            await app_context.api.server.set_status(
                request={"server_name": server_name, "status": "STOPPING"}
            )
            await server.stop()
            stopped = True
            await app_context.bedrock_process_manager.remove_server(server.server_name)
            logger.debug("Server '%s' stopped successfully.", server_name)
            return StopServerResponse(
                server_name=server_name,
                outcome="stopped",
                message=f"Server '{server_name}' stopped successfully.",
            )
        finally:
            # A failed stop may leave a live process: retain its PID file.
            if stopped:
                try:
                    pid_file_path = server.get_pid_file_path()
                    if os.path.isfile(pid_file_path):
                        await remove_pid_file_if_exists(pid_file_path)
                except Exception as cleanup_error:
                    logger.warning(
                        "Error during PID file cleanup for '%s': %s",
                        server_name,
                        cleanup_error,
                    )


@api_method("restart_server")
async def restart_server(
    request: RestartServerRequest, *, app_context: AppContext
) -> RestartServerResponse:
    """Orchestrate stop/start; abort on cancellation or either phase failing."""
    server_name = request.server_name
    server = app_context.get_server(server_name)
    async with server.operation_lock:
        was_running = await server.is_running()
        if was_running:
            if request.send_message:
                try:
                    await server.send_command("say Restarting server...")
                except BSMError as error:
                    logger.warning(
                        "Failed to send restart warning to '%s': %s", server_name, error
                    )
            await stop_server(
                StopServerRequest(server_name=server_name), app_context=app_context
            )

        await start_server(
            StartServerRequest(server_name=server_name), app_context=app_context
        )
        return RestartServerResponse(
            server_name=server_name,
            outcome="restarted" if was_running else "started",
            message=(
                f"Server '{server_name}' restarted successfully."
                if was_running
                else f"Server '{server_name}' was not running and has been started."
            ),
        )


@api_method("send_command")
@trigger_event(
    before="before_command_send",
    after="after_command_send",
    identity_keys=("server_name", "command"),
)
async def send_command(
    request: SendCommandRequest, *, app_context: AppContext
) -> SendCommandResponse:
    """Sends a command to a running Bedrock server.

    Accepts SendCommandRequest and returns SendCommandResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    command = request.command
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    if not command or not command.strip():
        raise MissingArgumentError("Command cannot be empty.")
    command_clean = command.strip()
    logger.debug("Sending command to server '%s'.", server_name)
    try:
        blacklist = API_COMMAND_BLACKLIST or []
        command_check = command_clean.lower().lstrip("/")
        for blocked_cmd_prefix in blacklist:
            if isinstance(blocked_cmd_prefix, str) and command_check.startswith(
                blocked_cmd_prefix.lower()
            ):
                error_msg = "Command is blocked by configuration."
                raise BlockedCommandError(error_msg)
        server = app_context.get_server(server_name)
        await server.send_command(command_clean)
        logger.debug("Command delivered to server '%s'.", server_name)
        return SendCommandResponse.model_validate(
            {
                "status": "success",
                "message": f"Command '{command_clean}' sent successfully.",
            }
        )
    except BlockedCommandError:
        logger.warning("Blocked command attempt for server '%s'.", server_name)
        raise
    except BSMError as e:
        log_operation_error(
            logger, "Failed to send command to server '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error sending command to '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise ServerError(f"Unexpected error sending command: {e}") from e


@validate_contract
@trigger_event(
    before="before_delete_server_data",
    after="after_delete_server_data",
    identity_keys=("server_name",),
)
async def delete_server_data(
    request: DeleteServerDataRequest, *, app_context: AppContext
) -> DeleteServerDataResponse:
    """Deletes all data associated with a Bedrock server.

    Accepts DeleteServerDataRequest and returns DeleteServerDataResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    stop_if_running = request.stop_if_running
    if not server_name:
        raise InvalidServerNameError("Server name cannot be empty.")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping server deletion.",
            server_name,
        )
        return DeleteServerDataResponse.model_validate(
            {
                "status": "skipped",
                "message": "A server operation is already in progress.",
            }
        )
    try:
        logger.debug(
            "Deleting all data for server '%s' (stop_if_running=%s).",
            server_name,
            stop_if_running,
        )
        if stop_if_running and await server.is_running():
            logger.debug(
                "Server '%s' is running. Stopping before deletion...", server_name
            )
            await stop_server(
                StopServerRequest(server_name=server_name), app_context=app_context
            )
            logger.debug("Server '%s' stopped.", server_name)
        logger.debug("Proceeding with deletion of data for server '%s'...", server_name)
        await delete_all_data(server)
        await app_context.remove_server(server_name)
        logger.debug("Successfully deleted all data for server '%s'.", server_name)
        return DeleteServerDataResponse.model_validate(
            {
                "status": "success",
                "message": f"All data for server '{server_name}' deleted successfully.",
            }
        )
    except BSMError as e:
        log_operation_error(
            logger, "Failed to delete server data for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error deleting server data for '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise
    finally:
        server.operation_lock.release()


@api_method("set_server_status", expose_to_plugins=False)
@trigger_event(
    before="before_server_status_change",
    after="after_server_status_change",
    identity_keys=("server_name", "status"),
)
async def set_server_status(
    request: SetServerStatusRequest, *, app_context: AppContext
) -> SetServerStatusResponse:
    """Internal API to set server status and trigger events.

    Accepts SetServerStatusRequest and returns SetServerStatusResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    status = request.status
    server = app_context.get_server(server_name)
    previous_status = await server.get_status_from_config()
    await server.configuration.update("server_info.status", status)
    server.logger.debug(
        "Status in persisted configuration for '%s' set to '%s'.",
        server.server_name,
        status,
    )
    return SetServerStatusResponse.model_validate(
        {
            "status": "success",
            "message": f"Server status set to {status}.",
            "server_name": server_name,
            "previous_status": previous_status,
            "new_status": status,
        }
    )


@api_method("update_server_player_stats", expose_to_plugins=False)
@trigger_event(
    before="before_server_players_change", after="after_server_players_change"
)
async def update_server_player_stats(
    request: UpdateServerPlayerStatsRequest, *, app_context: AppContext
) -> UpdateServerPlayerStatsResponse:
    """Internal API to trigger player stat updates for websockets/plugins.

    Accepts UpdateServerPlayerStatsRequest and returns UpdateServerPlayerStatsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    player_count = request.player_count
    players = request.model_dump(mode="python")["players"]
    app_context.state.runtime.update_server_runtime(
        server_name, players=players, players_online=player_count
    )
    return UpdateServerPlayerStatsResponse.model_validate(
        {
            "status": "success",
            "server_name": server_name,
            "player_count": player_count,
            "players": players,
        }
    )

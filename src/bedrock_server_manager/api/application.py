# bedrock_server_manager/api/application.py
"""Provide API functions for application-wide information and actions."""

import logging

from ..config import const as config_const
from ..context import AppContext
from ..error import BSMError, FileError
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from ..state.revision import revision_clock
from ..utils import list_content_files
from .models.application import (
    GetAllServersDataRequest,
    GetAllServersDataResponse,
    GetSystemAndAppInfoRequest,
    GetSystemAndAppInfoResponse,
    ListAvailableWorldsRequest,
    ListAvailableWorldsResponse,
    UpdateServerStatusesRequest,
    UpdateServerStatusesResponse,
)
from .models.common import ServerSummary

logger = logging.getLogger(__name__)


@api_method("list_available_worlds")
async def list_available_worlds(
    request: ListAvailableWorldsRequest, *, app_context: AppContext
) -> ListAvailableWorldsResponse:
    """Lists available .mcworld files from the content directory."""
    logger.debug("Requesting list of available worlds.")
    try:
        content_dir = app_context.settings.get("paths.content")
        worlds = await list_content_files(content_dir, "worlds", [".mcworld"])
        return ListAvailableWorldsResponse.model_validate(
            {"status": "success", "files": worlds}
        )
    except FileError:
        raise
    except Exception as e:
        log_operation_error(logger, "Unexpected error listing worlds: %s", e, error=e)
        raise


@api_method("get_all_servers_data")
async def get_all_servers_data(
    request: GetAllServersDataRequest, *, app_context: AppContext
) -> GetAllServersDataResponse:
    """Return status and version for all detected servers."""
    logger.debug("Getting status for all servers...")
    from ..utils import server as server_utils

    try:
        revision = revision_clock.capture()
        servers_data, bsm_error_messages = await server_utils.get_servers_data(
            app_context=app_context
        )
        servers_data = [dict(server, **revision) for server in servers_data]
        return GetAllServersDataResponse(
            status="partial" if bsm_error_messages else "success",
            servers=[ServerSummary.model_validate(item) for item in servers_data],
            errors=bsm_error_messages,
            **revision,
            message=(
                "Server discovery completed with failures."
                if bsm_error_messages
                else None
            ),
        )
    except BSMError as e:
        log_operation_error(
            logger, "Setup or I/O error in get_all_servers_data: %s", e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error in get_all_servers_data: %s", e, error=e
        )
        raise


@api_method("get_system_and_app_info")
def get_system_and_app_info(
    request: GetSystemAndAppInfoRequest, *, app_context: AppContext
) -> GetSystemAndAppInfoResponse:
    """Return basic system and application information."""
    import platform

    logger.debug("Requesting system and app info.")
    try:
        splash_txt = app_context.splash_txt
        data = {
            "os_type": platform.system(),
            "app_version": config_const.get_installed_version(),
            "splash_text": splash_txt,
        }
        logger.debug("System information retrieved.")
        return GetSystemAndAppInfoResponse.model_validate({"status": "success", **data})
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error getting system info: %s", e, error=e
        )
        raise


@api_method("update_server_statuses", expose_to_plugins=False)
async def update_server_statuses(
    request: UpdateServerStatusesRequest, *, app_context: AppContext
) -> UpdateServerStatusesResponse:
    """Reconciles the status in config files with the runtime state for all servers."""
    from ..utils import server as server_utils

    servers_data, errors = await server_utils.get_servers_data(app_context=app_context)
    return UpdateServerStatusesResponse(
        status="partial" if errors else "success",
        message=f"Status scan reconciled {len(servers_data)} server(s).",
        updated_servers_count=len(servers_data),
        errors=errors,
    )

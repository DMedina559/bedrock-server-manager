# bedrock_server_manager/api/application.py
"""Provides API functions for application-wide information and actions.

This module offers endpoints to retrieve general details about the Bedrock
Server Manager application itself and to perform operations that span across
multiple server instances.

Key functionalities include:
    - Retrieving application metadata (name, version, OS, key directories) via
      :func:`~.get_application_info_api`.
    - Listing globally available content like world templates
      (:func:`~.list_available_worlds`) and addons
      (:func:`~.list_available_addons_api`).
    - Aggregating status and version information for all detected server instances
      using :func:`~.get_all_servers_data`.

These functions are exposed to the plugin system via
:func:`~bedrock_server_manager.plugins.api_bridge.api_method` and are
intended for use by UIs, CLIs, or other high-level components.
"""

import logging

from ..config import const as config_const
from ..context import AppContext
from ..error import BSMError, FileError
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
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

logger = logging.getLogger(__name__)


@api_method("list_available_worlds")
async def list_available_worlds(
    request: ListAvailableWorldsRequest, *, app_context: AppContext
) -> ListAvailableWorldsResponse:
    """Lists available .mcworld files from the content directory.

    Accepts ListAvailableWorldsRequest and returns ListAvailableWorldsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
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
    """Retrieves status and version for all detected servers.

    Accepts GetAllServersDataRequest and returns GetAllServersDataResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    logger.debug("Getting status for all servers...")
    from ..utils import server as server_utils

    try:
        servers_data, bsm_error_messages = await server_utils.get_servers_data(
            app_context=app_context
        )
        if bsm_error_messages:
            for err_msg in bsm_error_messages:
                logger.error(
                    "Individual server error during get_all_servers_data: %s", err_msg
                )
            return GetAllServersDataResponse.model_validate(
                {
                    "status": "success",
                    "servers": servers_data,
                    "message": f"Completed with errors: {'; '.join(bsm_error_messages)}",
                }
            )
        return GetAllServersDataResponse.model_validate(
            {"status": "success", "servers": servers_data}
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
    """Retrieves basic system and application information.

    Accepts GetSystemAndAppInfoRequest and returns GetSystemAndAppInfoResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
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
    """Reconciles the status in config files with the runtime state for all servers.

    Accepts UpdateServerStatusesRequest and returns UpdateServerStatusesResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    from ..utils import server as server_utils

    updated_servers_count = 0
    error_messages = []
    logger.debug("Updating all server statuses...")
    try:
        all_servers_data, discovery_errors = await server_utils.get_servers_data(
            app_context=app_context
        )
        if discovery_errors:
            error_messages.extend(discovery_errors)
        for server_data in all_servers_data:
            server_name = server_data.get("name")
            if not server_name:
                continue
            try:
                logger.debug(
                    "Status for '%s' was reconciled by get_servers_data.", server_name
                )
                updated_servers_count += 1
            except Exception as e:
                msg = f"Could not update status for server '{server_name}': {e}"
                log_operation_error(
                    logger, "API.update_server_statuses: %s", msg, error=e
                )
                error_messages.append(msg)
        if error_messages:
            return UpdateServerStatusesResponse.model_validate(
                {
                    "status": "success",
                    "message": "Status scan completed with partial failures.",
                    "updated_servers_count": updated_servers_count,
                    "errors": error_messages,
                }
            )
        return UpdateServerStatusesResponse.model_validate(
            {
                "status": "success",
                "message": f"Status check completed for {updated_servers_count} servers.",
                "updated_servers_count": updated_servers_count,
            }
        )
    except BSMError as e:
        log_operation_error(logger, "Setup error during status update: %s", e, error=e)
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error during status update: %s", e, error=e
        )
        raise

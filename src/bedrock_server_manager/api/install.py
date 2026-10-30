import asyncio
import logging

from ..context import AppContext
from ..core.server.software import install_or_update, is_update_needed
from ..error import (
    BSMError,
    UserInputError,
)
from ..events import trigger_event
from ..events.operations import OperationName, track_operation
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from .models.install import (
    InstallNewServerRequest,
    InstallNewServerResponse,
    UpdateServerRequest,
    UpdateServerResponse,
)
from .server import server_lifecycle_manager

logger = logging.getLogger(__name__)


@api_method("install_new_server")
@trigger_event(
    before="before_server_install",
    after="after_server_install",
    identity_keys=("server_name", "target_version"),
)
async def install_new_server(
    request: InstallNewServerRequest, *, app_context: AppContext
) -> InstallNewServerResponse:
    """Installs a new server instance."""
    server_name = request.server_name
    target_version = request.target_version
    server_zip_path = request.server_zip_path
    try:
        from ..utils.server import core_validate_server_name_format

        core_validate_server_name_format(server_name)
        server = app_context.prepare_server(server_name)
    except BSMError as e:
        log_operation_error(
            logger, "Installation failed for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error installing '%s': %s", server_name, e, error=e
        )
        raise
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping installation.",
            server_name,
        )
        return InstallNewServerResponse(
            server_name=server_name,
            status="skipped",
            message="An operation is already in progress for this server.",
        )
    try:
        if await server.is_installed():
            raise UserInputError(f"Server '{server_name}' is already installed.")
        logger.debug(
            "Installing new server '%s', target version '%s'.",
            server_name,
            target_version,
        )
        await install_or_update(server, target_version, server_zip_path=server_zip_path)
        return InstallNewServerResponse.model_validate(
            {
                "server_name": server_name,
                "status": "success",
                "version": await server.get_version(),
                "message": f"Server '{server_name}' installed successfully to version {await server.get_version()}.",
            }
        )
    except BSMError as e:
        log_operation_error(
            logger, "Installation failed for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error installing '%s': %s", server_name, e, error=e
        )
        raise
    finally:
        server.operation_lock.release()


@api_method("update_server")
@track_operation(OperationName.SERVER_UPDATE)
@trigger_event(
    before="before_server_update",
    after="after_server_update",
    identity_keys=("server_name",),
)
async def update_server(
    request: UpdateServerRequest, *, app_context: AppContext
) -> UpdateServerResponse:
    """Updates an existing server instance."""
    server_name = request.server_name
    send_message = request.send_message
    try:
        server = app_context.get_server(server_name, require_installation=False)
    except BSMError as e:
        log_operation_error(
            logger, "Update failed for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error updating '%s': %s", server_name, e, error=e
        )
        raise
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping update.",
            server_name,
        )
        return UpdateServerResponse(
            server_name=server_name,
            status="skipped",
            message="An install/update operation is already in progress.",
        )
    try:
        target_version = await server.get_target_version()
        logger.debug(
            "Updating server '%s'. Send message: %s", server_name, send_message
        )
        if not await is_update_needed(server, target_version):
            return UpdateServerResponse.model_validate(
                {
                    "server_name": server_name,
                    "status": "success",
                    "updated": False,
                    "message": "Server is already up-to-date.",
                }
            )
        async with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            logger.debug("Backing up '%s' before update...", server_name)
            from .backup_restore import backup_all
            from .models.backup_restore import BackupAllRequest

            backup = await backup_all(
                BackupAllRequest(server_name=server_name), app_context=app_context
            )
            if (
                backup.status != "success"
                or backup.details is None
                or backup.details.outcome != "completed"
            ):
                from ..error import IncompleteOperationError

                raise IncompleteOperationError(
                    "Pre-update backup did not complete.", backup
                )
            logger.debug(
                "Performing update for '%s' to target '%s'...",
                server_name,
                target_version,
            )
            await install_or_update(server, target_version)
        return UpdateServerResponse.model_validate(
            {
                "server_name": server_name,
                "status": "success",
                "updated": True,
                "new_version": await server.get_version(),
                "message": f"Server '{server_name}' updated successfully to {await server.get_version()}.",
            }
        )
    except BSMError as e:
        log_operation_error(
            logger, "Update failed for '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger, "Unexpected error updating '%s': %s", server_name, e, error=e
        )
        raise
    finally:
        server.operation_lock.release()

# bedrock_server_manager/api/addon.py
"""API functions for managing addons on Bedrock servers.

This module provides a high-level interface for installing and managing addons
(e.g., ``.mcpack``, ``.mcaddon`` files) for specific Bedrock server instances.
It primarily orchestrates calls to the addon processing methods of the
:class:`~bedrock_server_manager.core.bedrock_server.BedrockServer` class.

Currently, the main functionality offered is:
    - Importing and installing addon files into a server's behavior packs and
      resource packs directories via :func:`~.import_addon`.

Operations that modify server files, like addon installation, are designed to be
thread-safe using a per-server operation lock (``server.operation_lock``). The module also utilizes the
:func:`~bedrock_server_manager.api.server.server_lifecycle_manager` to
optionally manage the server's state (stopping and restarting) during these
operations to ensure data integrity. All primary functions are exposed to the
plugin system.
"""

import asyncio
import logging
import os

from ..context import AppContext
from ..error import (
    AppFileNotFoundError,
    BSMError,
    FileError,
    MissingArgumentError,
    SendCommandError,
    ServerNotRunningError,
)
from ..logging import log_operation_error
from ..plugins.api_bridge import api_method
from ..plugins.api_contract import validate_contract
from ..plugins.event_trigger import trigger_event
from ..plugins.runtime_capabilities import server_lifecycle_manager
from ..utils import list_content_files
from .models.addon import (
    DisableAddonRequest,
    DisableAddonResponse,
    EnableAddonRequest,
    EnableAddonResponse,
    ImportAddonRequest,
    ImportAddonResponse,
    ListAvailableAddonsRequest,
    ListAvailableAddonsResponse,
    ListInstalledAddonsRequest,
    ListInstalledAddonsResponse,
    ReorderAddonsRequest,
    ReorderAddonsResponse,
    UninstallAddonRequest,
    UninstallAddonResponse,
    UpdateSubpackRequest,
    UpdateSubpackResponse,
)

logger = logging.getLogger(__name__)


@api_method("list_available_addons")
async def list_available_addons(
    request: ListAvailableAddonsRequest, *, app_context: AppContext
) -> ListAvailableAddonsResponse:
    """Lists available .mcaddon and .mcpack files from the content directory.

    Accepts ListAvailableAddonsRequest and returns ListAvailableAddonsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    logger.debug("Requesting list of available addons.")
    try:
        content_dir = app_context.settings.get("paths.content")
        addons = await list_content_files(
            content_dir, "addons", [".mcpack", ".mcaddon"]
        )
        return ListAvailableAddonsResponse.model_validate(
            {"status": "success", "files": addons}
        )
    except FileError:
        raise
    except Exception as e:
        log_operation_error(logger, "Unexpected error listing addons: %s", e, error=e)
        raise


@api_method("import_addon")
@trigger_event(
    before="before_addon_import",
    after="after_addon_import",
    identity_keys=("server_name", "addon_file_path"),
)
async def import_addon(
    request: ImportAddonRequest, *, app_context: AppContext
) -> ImportAddonResponse:
    """Installs an addon to a specified Bedrock server.

    Accepts ImportAddonRequest and returns ImportAddonResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    addon_file_path = request.addon_file_path
    stop_start_server = request.stop_start_server
    restart_only_on_success = request.restart_only_on_success
    if not server_name:
        raise MissingArgumentError("Server name cannot be empty.")
    if not addon_file_path:
        raise MissingArgumentError("Addon file path cannot be empty.")
    if not os.path.isfile(addon_file_path):
        raise AppFileNotFoundError(addon_file_path, "Addon file")
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        logger.warning(
            "An operation for '%s' is already in progress. Skipping concurrent import.",
            server_name,
        )
        return ImportAddonResponse.model_validate(
            {
                "status": "skipped",
                "message": "An addon operation is already in progress.",
            }
        )
    try:
        addon_filename = os.path.basename(addon_file_path)
        logger.debug(
            "Initiating addon import for '%s' from '%s'. Stop/Start: %s, RestartOnSuccess: %s",
            server_name,
            addon_filename,
            stop_start_server,
            restart_only_on_success,
        )
        try:
            if await server.is_running():
                try:
                    await server.send_command("say Installing addon...")
                except (SendCommandError, ServerNotRunningError) as e:
                    logger.warning(
                        "Failed to send addon installation warning to '%s': %s",
                        server_name,
                        e,
                    )
            async with server_lifecycle_manager(
                server_name,
                stop_before=stop_start_server,
                start_after=stop_start_server,
                restart_on_success_only=restart_only_on_success,
                app_context=app_context,
            ):
                logger.debug(
                    "Processing addon file '%s' for server '%s'...",
                    addon_filename,
                    server_name,
                )
                await server.addons.process_addon_file(addon_file_path)
                logger.debug(
                    "Core addon processing completed for '%s' on '%s'.",
                    addon_filename,
                    server_name,
                )
            message = f"Addon '{addon_filename}' installed successfully for server '{server_name}'."
            if stop_start_server:
                message += " Server stop/start cycle handled."
            return ImportAddonResponse.model_validate(
                {"status": "success", "message": message}
            )
        except BSMError as e:
            log_operation_error(
                logger,
                "Addon import failed for '%s' on '%s': %s",
                addon_filename,
                server_name,
                e,
                error=e,
            )
            raise
        except Exception as e:
            log_operation_error(
                logger,
                "Unexpected error during addon import for '%s': %s",
                server_name,
                e,
                error=e,
            )
            raise
    finally:
        server.operation_lock.release()


@api_method("list_installed_addons")
async def list_installed_addons(
    request: ListInstalledAddonsRequest, *, app_context: AppContext
) -> ListInstalledAddonsResponse:
    """Lists all addons for a server's active world.

    Accepts ListInstalledAddonsRequest and returns ListInstalledAddonsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    server = app_context.get_server(server_name)
    return ListInstalledAddonsResponse.model_validate(
        {"status": "success", "addons": await server.addons.list_installed_addons()}
    )


@api_method("enable_addon")
@trigger_event(
    before="before_addon_enable",
    after="after_addon_enable",
    identity_keys=("server_name", "pack_uuid"),
)
async def enable_addon(
    request: EnableAddonRequest, *, app_context: AppContext
) -> EnableAddonResponse:
    """Enables a disabled addon for a server's active world.

    Accepts EnableAddonRequest and returns EnableAddonResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    pack_uuid = request.pack_uuid
    pack_type = request.pack_type
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        return EnableAddonResponse.model_validate(
            {
                "status": "skipped",
                "message": "An addon operation is already in progress.",
            }
        )
    try:
        async with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            await server.addons.enable_addon(pack_uuid=pack_uuid, pack_type=pack_type)
        return EnableAddonResponse.model_validate(
            {
                "status": "success",
                "message": f"Successfully enabled pack '{pack_uuid}'.",
            }
        )
    except BSMError as e:
        log_operation_error(
            logger,
            "Error enabling addon '%s' on '%s': %s",
            pack_uuid,
            server_name,
            e,
            error=e,
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error enabling addon '%s' on '%s': %s",
            pack_uuid,
            server_name,
            e,
            error=e,
        )
        raise
    finally:
        server.operation_lock.release()


@api_method("disable_addon")
@trigger_event(
    before="before_addon_disable",
    after="after_addon_disable",
    identity_keys=("server_name", "pack_uuid"),
)
async def disable_addon(
    request: DisableAddonRequest, *, app_context: AppContext
) -> DisableAddonResponse:
    """Disables an active addon for a server's active world, preserving files.

    Accepts DisableAddonRequest and returns DisableAddonResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    pack_uuid = request.pack_uuid
    pack_type = request.pack_type
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        return DisableAddonResponse.model_validate(
            {
                "status": "skipped",
                "message": "An addon operation is already in progress.",
            }
        )
    try:
        async with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            await server.addons.disable_addon(pack_uuid=pack_uuid, pack_type=pack_type)
        return DisableAddonResponse.model_validate(
            {
                "status": "success",
                "message": f"Successfully disabled pack '{pack_uuid}'.",
            }
        )
    except BSMError as e:
        log_operation_error(
            logger,
            "Error disabling addon '%s' on '%s': %s",
            pack_uuid,
            server_name,
            e,
            error=e,
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error disabling addon '%s' on '%s': %s",
            pack_uuid,
            server_name,
            e,
            error=e,
        )
        raise
    finally:
        server.operation_lock.release()


@validate_contract
@trigger_event(
    before="before_addon_subpack_update",
    after="after_addon_subpack_update",
    identity_keys=("server_name", "pack_uuid"),
)
async def update_subpack(
    request: UpdateSubpackRequest, *, app_context: AppContext
) -> UpdateSubpackResponse:
    """Updates the active subpack for an addon on a server's active world.

    Accepts UpdateSubpackRequest and returns UpdateSubpackResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    pack_uuid = request.pack_uuid
    pack_type = request.pack_type
    subpack_name = request.subpack_name
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        return UpdateSubpackResponse.model_validate(
            {
                "status": "skipped",
                "message": "An addon operation is already in progress.",
            }
        )
    try:
        async with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            await server.addons.update_subpack(
                pack_uuid=pack_uuid, pack_type=pack_type, subpack_name=subpack_name
            )
        return UpdateSubpackResponse.model_validate(
            {
                "status": "success",
                "message": f"Successfully updated subpack for pack '{pack_uuid}'.",
            }
        )
    except BSMError as e:
        log_operation_error(
            logger,
            "Error updating subpack for addon '%s' on '%s': %s",
            pack_uuid,
            server_name,
            e,
            error=e,
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error updating subpack for addon '%s' on '%s': %s",
            pack_uuid,
            server_name,
            e,
            error=e,
        )
        raise
    finally:
        server.operation_lock.release()


@validate_contract
@trigger_event(
    before="before_addon_uninstall",
    after="after_addon_uninstall",
    identity_keys=("server_name", "pack_uuid"),
)
async def uninstall_addon(
    request: UninstallAddonRequest, *, app_context: AppContext
) -> UninstallAddonResponse:
    """Uninstalls an addon for a server's active world, deleting its files.

    Accepts UninstallAddonRequest and returns UninstallAddonResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    pack_uuid = request.pack_uuid
    pack_type = request.pack_type
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        return UninstallAddonResponse.model_validate(
            {
                "status": "skipped",
                "message": "An addon operation is already in progress.",
            }
        )
    try:
        async with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            await server.addons.remove_addon(pack_uuid=pack_uuid, pack_type=pack_type)
        return UninstallAddonResponse.model_validate(
            {
                "status": "success",
                "message": f"Successfully uninstalled pack '{pack_uuid}'.",
            }
        )
    except BSMError as e:
        log_operation_error(
            logger,
            "Error uninstalling addon '%s' on '%s': %s",
            pack_uuid,
            server_name,
            e,
            error=e,
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error uninstalling addon '%s' on '%s': %s",
            pack_uuid,
            server_name,
            e,
            error=e,
        )
        raise
    finally:
        server.operation_lock.release()


@api_method("reorder_addons")
@trigger_event(
    before="before_addon_reorder",
    after="after_addon_reorder",
    identity_keys=("server_name",),
)
async def reorder_addons(
    request: ReorderAddonsRequest, *, app_context: AppContext
) -> ReorderAddonsResponse:
    """Reorders the active addons for a server's active world.

    Accepts ReorderAddonsRequest and returns ReorderAddonsResponse.
    Invalid requests fail validation before side effects; operation failures raise application exceptions.
    """
    server_name = request.server_name
    uuids = request.uuids
    pack_type = request.pack_type
    server = app_context.get_server(server_name)
    try:
        await server.operation_lock.acquire(timeout=300)
    except asyncio.TimeoutError:
        return ReorderAddonsResponse.model_validate(
            {
                "status": "skipped",
                "message": "An addon operation is already in progress.",
            }
        )
    try:
        async with server_lifecycle_manager(
            server_name,
            stop_before=True,
            start_after=True,
            restart_on_success_only=True,
            app_context=app_context,
        ):
            await server.addons.reorder_addons(uuids=uuids, pack_type=pack_type)
        return ReorderAddonsResponse.model_validate(
            {
                "status": "success",
                "message": f"Successfully reordered {pack_type} packs.",
            }
        )
    except BSMError as e:
        log_operation_error(
            logger, "Error reordering addons on '%s': %s", server_name, e, error=e
        )
        raise
    except Exception as e:
        log_operation_error(
            logger,
            "Unexpected error reordering addons on '%s': %s",
            server_name,
            e,
            error=e,
        )
        raise
    finally:
        server.operation_lock.release()

"""Bedrock software installation operations, independent of server inheritance."""

from typing import TYPE_CHECKING, Optional

from ...error import (
    BSMError,
    FileOperationError,
    MissingArgumentError,
    PermissionsError,
    ServerStopError,
)
from ..downloader import BedrockDownloader
from .removal import set_filesystem_permissions

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


async def is_update_needed(
    server: "BedrockServer", target_version_specification: str
) -> bool:
    """Compare installed software with a specific, latest, or preview release."""
    if (
        not isinstance(target_version_specification, str)
        or not target_version_specification.strip()
    ):
        raise MissingArgumentError(
            "Target version specification cannot be empty and must be a string."
        )
    target = target_version_specification.strip().upper()
    current = await server.get_version()
    if target in ("LATEST", "PREVIEW") and (
        not current or current.upper() == "UNKNOWN"
    ):
        return True
    try:
        downloader = BedrockDownloader(
            settings_obj=server.settings,
            server_dir=server.server_dir,
            target_version=target,
        )
        available = (
            await downloader.get_version_for_target_spec()
            if target in ("LATEST", "PREVIEW")
            else downloader._custom_version_number
        )
        return not available or current != available
    except Exception:
        server.logger.warning(
            "Could not resolve Bedrock release %r for %s; assuming an update is needed.",
            target,
            server.server_name,
            exc_info=True,
        )
        return True


async def _install_or_update(
    server: "BedrockServer",
    target_version_specification: str,
    force_reinstall: bool = False,
    server_zip_path: Optional[str] = None,
) -> None:
    """Stop the server and install or update its Bedrock files."""
    if (
        not isinstance(target_version_specification, str)
        or not target_version_specification.strip()
    ):
        raise MissingArgumentError(
            "Target version specification cannot be empty and must be a string."
        )
    server.logger.info(
        f"Server '{server.server_name}': Initiating async install/update to version spec '{target_version_specification}'. Force reinstall: {force_reinstall}"
    )
    is_currently_installed: bool = await server.is_installed()
    if not force_reinstall and is_currently_installed:
        if not await is_update_needed(server, target_version_specification):
            server.logger.info(
                f"Server '{server.server_name}' is already at the target version or latest for '{target_version_specification}'. No action taken."
            )
            return
    if await server.is_running():
        server.logger.info(
            f"Server '{server.server_name}' is running. Stopping before install/update."
        )
        try:
            await server.stop()
        except ServerStopError:
            raise
        except Exception as e_stop:
            raise ServerStopError(
                f"Failed to stop server '{server.server_name}' before install/update: {e_stop}"
            ) from e_stop
    if await server.is_running():
        raise ServerStopError(
            f"Server '{server.server_name}' is still running; cannot replace its files."
        )
    status_to_set = "UPDATING" if is_currently_installed else "INSTALLING"
    try:
        await server.set_status_in_config(status_to_set)
    except Exception as e_stat:
        server.logger.warning(
            f"Could not set status to {status_to_set} for '{server.server_name}': {e_stat}"
        )
    try:
        if not is_currently_installed:
            await server.set_target_version(
                target_version_specification.strip().upper()
            )
    except Exception as e_set_target:
        server.logger.warning(
            f"Could not set target version for '{server.server_name}': {e_set_target}"
        )
    downloader = BedrockDownloader(
        settings_obj=server.settings,
        server_dir=server.server_dir,
        target_version=target_version_specification,
        server_zip_path=server_zip_path,
    )
    actual_version_downloaded: Optional[str] = None
    try:
        server.logger.info(
            f"Server '{server.server_name}': Performing full setup for '{target_version_specification}'..."
        )
        is_update_op_for_extraction = is_currently_installed and (not force_reinstall)
        actual_version_downloaded = await downloader.full_server_setup(
            is_update_op_for_extraction
        )
        try:
            await set_filesystem_permissions(server)
        except PermissionsError:
            raise
        except Exception as e_perm:
            server.logger.error(
                f"Failed to set permissions for '{server.server_dir}' during setup: {e_perm}. Installation may be incomplete."
            )
            raise PermissionsError(
                f"Unexpected error setting permissions for '{server.server_dir}'."
            ) from e_perm
        await server.set_version(actual_version_downloaded)
        await server.set_status_in_config(
            "UPDATED" if is_update_op_for_extraction else "INSTALLED"
        )
        server.logger.info(
            f"Server '{server.server_name}' successfully {('updated' if is_update_op_for_extraction else 'installed')} to version '{actual_version_downloaded}'."
        )
    except BSMError as e_bsm_install:
        server.logger.error(
            f"Install/Update failed for server '{server.server_name}' due to a BSM error: {e_bsm_install}",
            exc_info=True,
        )
        await server.set_status_in_config("ERROR")
        raise
    except Exception as e_unexp_install:
        server.logger.error(
            f"Unexpected error during install/update for '{server.server_name}': {e_unexp_install}",
            exc_info=True,
        )
        await server.set_status_in_config("ERROR")
        raise FileOperationError(
            f"Unexpected failure during install/update for '{server.server_name}': {e_unexp_install}"
        ) from e_unexp_install


async def install_or_update(
    server: "BedrockServer",
    target_version_specification: str,
    force_reinstall: bool = False,
    server_zip_path: Optional[str] = None,
) -> None:
    """Serialize the operation with other mutations of this server."""
    async with server.operation_lock:
        await _install_or_update(
            server, target_version_specification, force_reinstall, server_zip_path
        )

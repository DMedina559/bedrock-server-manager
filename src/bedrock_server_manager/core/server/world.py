"""Bedrock world component."""

import asyncio
import logging
import os
import re
import shutil
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

import aiofiles
import aiofiles.os
import aiofiles.ospath

from ...error import (
    AppFileNotFoundError,
    BackupRestoreError,
    ConfigParseError,
    ExtractError,
    FileOperationError,
    MissingArgumentError,
)
from ...logging import log_operation_error
from ...utils.threads import check_cancellation, copy_stream, run_in_thread
from ..files import (
    atomic_world_archive,
    extract_archive,
    file_transaction,
    temporary_directory,
)
from ..system import base as system_base

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer


class ServerWorlds:
    """World operations for one Bedrock server."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server
        self.logger = logging.LoggerAdapter(
            logging.getLogger(__name__), {"server_name": server.server_name}
        )

    @property
    def _worlds_base_dir_in_server(self) -> str:
        """str: The absolute path to the 'worlds' subdirectory within the server's
        installation directory (:attr:`~.ServerResources.server_dir`).
        """
        return os.path.join(self.server.paths.server_dir, "worlds")

    async def _get_active_world_directory_path(self) -> str:
        """Resolve the active world directory from the server properties."""
        active_world_name: str = await self.server.get_world_name()
        if not active_world_name or not isinstance(active_world_name, str):
            raise ConfigParseError(
                f"Active world name ('{active_world_name}') received from get_world_name() is invalid for server '{self.server.server_name}'."
            )
        return os.path.join(self._worlds_base_dir_in_server, active_world_name)

    async def extract_mcworld(
        self, mcworld_file_path: str, target_world_dir_name: str
    ) -> str:
        """Validate and extract a world archive, returning its installed directory.

        Stage the new world before replacing an existing target.
        """
        async with self.server.operation_lock:
            if not isinstance(mcworld_file_path, str) or not mcworld_file_path:
                raise MissingArgumentError(
                    "Path to the .mcworld file cannot be empty and must be a string."
                )
            if not target_world_dir_name:
                raise MissingArgumentError(
                    "Target world directory name cannot be empty."
                )
            full_target_extract_dir = os.path.join(
                self._worlds_base_dir_in_server, target_world_dir_name
            )
            mcworld_filename = os.path.basename(mcworld_file_path)
            self.logger.debug(
                "Server '%s': Preparing to extract '%s' into world directory '%s'.",
                self.server.server_name,
                mcworld_filename,
                target_world_dir_name,
            )
            if not await aiofiles.ospath.isfile(mcworld_file_path):
                raise AppFileNotFoundError(mcworld_file_path, ".mcworld file")
            target = Path(full_target_extract_dir)
            try:
                await run_in_thread(target.parent.mkdir, parents=True, exist_ok=True)
                async with temporary_directory(target.parent) as staging:

                    def prepare() -> None:
                        with zipfile.ZipFile(mcworld_file_path, "r") as archive:
                            extract_archive(archive, staging)
                        entries = list(staging.iterdir())
                        if not any(
                            (
                                item.name.lower() in ("level.dat", "level.txt")
                                for item in entries
                            )
                        ):
                            if len(entries) == 1 and entries[0].is_dir():
                                nested = entries[0]
                                for item in nested.iterdir():
                                    shutil.move(str(item), staging)
                                nested.rmdir()
                        if not any(
                            (
                                (staging / name).is_file()
                                for name in ("level.dat", "level.txt")
                            )
                        ):
                            raise zipfile.BadZipFile(
                                "Archive contains no world metadata"
                            )

                    await run_in_thread(prepare)
                    async with file_transaction(target.parent) as transaction:
                        await run_in_thread(transaction.replace, staging, target)
                        await run_in_thread(staging.mkdir)
                return full_target_extract_dir
            except zipfile.BadZipFile as error:
                raise ExtractError(
                    f"Invalid .mcworld file: {mcworld_filename}"
                ) from error
            except OSError as error:
                raise FileOperationError(
                    f"Error extracting world '{mcworld_filename}': {error}"
                ) from error

    async def _live_export_world(
        self,
        world_dir_name: str,
        target_mcworld_file_path: str,
        poll_interval: float = 1.0,
        timeout: float = 30.0,
        capture_directory: str | None = None,
    ) -> None:
        """Executes a live world backup using Bedrock server's save hold/query/resume protocol."""
        log_path = self.server.paths.server_log_path
        start_cursor = 0
        if log_path and os.path.isfile(log_path):
            start_cursor = os.path.getsize(log_path)
        self.logger.debug(
            "Server '%s': Initiating live backup using 'save hold'...",
            self.server.server_name,
        )
        try:
            await self.server.send_command("save hold")
        except Exception as e:
            raise BackupRestoreError(
                f"Failed to issue 'save hold' command to server '{self.server.server_name}': {e}"
            ) from e
        file_list_with_sizes: List[Tuple[str, int]] = []
        query_success = False
        start_time = time.time()
        original_error: BaseException | None = None
        try:
            while time.time() - start_time < timeout:
                await asyncio.sleep(poll_interval)
                await self.server.send_command("save query")
                if log_path and os.path.isfile(log_path):
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        f.seek(start_cursor)
                        log_text = f.read()
                    match = re.search(
                        "(?:Data saved\\. Files are now ready to be copied\\.|Data the world is saved:?)\\s*([\\s\\S]*?)(?=\\n\\r?\\n|\\r?\\n\\r?\\n|\\[\\d{4}-|$)",
                        log_text,
                        re.IGNORECASE,
                    )
                    if match:
                        files_str = match.group(1).strip()
                        entries = [
                            e.strip()
                            for e in re.split("[,\\n\\r]+", files_str)
                            if e.strip()
                        ]
                        parsed_files = []
                        for entry in entries:
                            if ":" in entry:
                                rpath, rsize = entry.rsplit(":", 1)
                                try:
                                    parsed_files.append(
                                        (rpath.strip(), int(rsize.strip()))
                                    )
                                except ValueError:
                                    pass
                        if parsed_files:
                            file_list_with_sizes = parsed_files
                            query_success = True
                            self.logger.debug(
                                "Server '%s': Received file list (%s files) from 'save query'.",
                                self.server.server_name,
                                len(file_list_with_sizes),
                            )
                            break
            if not query_success:
                raise BackupRestoreError(
                    f"Timed out waiting for 'save query' response on server '{self.server.server_name}' after {timeout} seconds."
                )
            full_source_world_dir = os.path.join(
                self._worlds_base_dir_in_server, world_dir_name
            )

            def _copy_and_truncate_world(
                cancellation_event: threading.Event | None = None,
            ) -> None:
                from contextlib import nullcontext

                def copy_file(source, target):
                    check_cancellation(cancellation_event)
                    with open(source, "rb") as stream, open(target, "wb") as output:
                        copy_stream(stream, output, cancellation_event)
                    shutil.copystat(source, target)
                    return target

                with (
                    nullcontext(capture_directory)
                    if capture_directory
                    else tempfile.TemporaryDirectory()
                ) as temp_dir:
                    if os.path.exists(full_source_world_dir):
                        shutil.copytree(
                            full_source_world_dir,
                            temp_dir,
                            dirs_exist_ok=True,
                            copy_function=copy_file,
                        )
                    for rpath, rsize in file_list_with_sizes:
                        check_cancellation(cancellation_event)
                        if rsize < 0:
                            raise BackupRestoreError("Invalid live backup file size.")
                        clean_rel_path = rpath
                        if clean_rel_path.startswith(
                            world_dir_name + "/"
                        ) or clean_rel_path.startswith(world_dir_name + "\\"):
                            start_idx = len(world_dir_name) + 1
                            clean_rel_path = clean_rel_path[start_idx:]
                        elif "/" in clean_rel_path or "\\" in clean_rel_path:
                            if not os.path.exists(
                                os.path.join(full_source_world_dir, clean_rel_path)
                            ):
                                parts = re.split("[/\\\\]", clean_rel_path, maxsplit=1)
                                if len(parts) == 2 and os.path.exists(
                                    os.path.join(full_source_world_dir, parts[1])
                                ):
                                    clean_rel_path = parts[1]
                        from ...backups.archive import safe_name

                        safe_name(clean_rel_path.replace("\\", "/"))
                        src_file = os.path.join(full_source_world_dir, clean_rel_path)
                        if (
                            not Path(src_file)
                            .resolve()
                            .is_relative_to(Path(full_source_world_dir).resolve())
                        ):
                            raise BackupRestoreError("Unsafe live backup source.")
                        if (
                            not os.path.isfile(src_file)
                            or os.path.getsize(src_file) < rsize
                        ):
                            raise BackupRestoreError(
                                "Live backup source is missing or shorter than reported."
                            )
                        dest_file = os.path.join(temp_dir, clean_rel_path)
                        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                        if os.path.exists(src_file):
                            copy_file(src_file, dest_file)
                        if os.path.exists(dest_file):
                            with open(dest_file, "r+b") as f:
                                f.truncate(rsize)
                    if capture_directory is None:
                        atomic_world_archive(temp_dir, target_mcworld_file_path)

            await run_in_thread(_copy_and_truncate_world)
            self.logger.info(
                "Server '%s': Live world archive created: %s",
                self.server.server_name,
                target_mcworld_file_path,
            )
        except BaseException as error:
            original_error = error
            raise
        finally:
            self.logger.debug(
                "Server '%s': Sending 'save resume'...", self.server.server_name
            )
            try:
                await self.server.send_command("save resume")
            except Exception as e_res:
                self.logger.warning(
                    "Server '%s': Failed to send 'save resume': %s",
                    self.server.server_name,
                    e_res,
                )
                if original_error is not None:
                    original_error.add_note(
                        f"Resuming server saves also failed: {type(e_res).__name__}"
                    )
                else:
                    raise BackupRestoreError(
                        "World export completed, but server saves could not be resumed."
                    ) from e_res

    async def export_world(
        self, world_dir_name: str, target_mcworld_file_path: str
    ) -> None:
        """Export a world to the requested ``.mcworld`` path.

        Use save hold/query/resume for a running active world. Replace an existing
        export and clean temporary archive files.
        """
        async with self.server.operation_lock:
            if not isinstance(world_dir_name, str) or not world_dir_name:
                raise MissingArgumentError(
                    "Source world directory name cannot be empty and must be a string."
                )
            if not target_mcworld_file_path:
                raise MissingArgumentError("Target .mcworld file path cannot be empty.")
            full_source_world_dir = os.path.join(
                self._worlds_base_dir_in_server, world_dir_name
            )
            mcworld_filename = os.path.basename(target_mcworld_file_path)
            self.logger.debug(
                "Server '%s': Exporting world '%s' to .mcworld file '%s'.",
                self.server.server_name,
                world_dir_name,
                mcworld_filename,
            )
            if not await aiofiles.ospath.isdir(full_source_world_dir):
                raise AppFileNotFoundError(
                    full_source_world_dir, "Source world directory"
                )
            target_parent_dir = os.path.dirname(target_mcworld_file_path)
            if target_parent_dir:
                try:
                    await run_in_thread(os.makedirs, target_parent_dir, exist_ok=True)
                except OSError as e:
                    raise FileOperationError(
                        f"Cannot create target directory '{target_parent_dir}': {e}"
                    ) from e
            is_running = await self.server.is_running()
            active_world_name = await self.server.get_world_name()
            if (
                is_running
                and active_world_name
                and (world_dir_name == active_world_name)
            ):
                await self._live_export_world(world_dir_name, target_mcworld_file_path)
                return
            try:
                await run_in_thread(
                    atomic_world_archive,
                    full_source_world_dir,
                    target_mcworld_file_path,
                )
            except OSError as error:
                raise BackupRestoreError(
                    f"Failed to create .mcworld for server '{self.server.server_name}': {error}"
                ) from error

    async def import_world(self, mcworld_backup_file_path: str) -> str:
        """Replace the active world from a validated archive and return its name.

        Extraction failure preserves the existing world.
        """
        async with self.server.operation_lock:
            if (
                not isinstance(mcworld_backup_file_path, str)
                or not mcworld_backup_file_path
            ):
                raise MissingArgumentError(
                    ".mcworld backup file path cannot be empty and must be a string."
                )
            mcworld_filename = os.path.basename(mcworld_backup_file_path)
            self.logger.debug(
                "Server '%s': Importing active world from backup '%s'.",
                self.server.server_name,
                mcworld_filename,
            )
            if not await aiofiles.ospath.isfile(mcworld_backup_file_path):
                raise AppFileNotFoundError(
                    mcworld_backup_file_path, ".mcworld backup file"
                )
            try:
                active_world_dir_name = str(await self.server.get_world_name())
                self.logger.debug(
                    "Target active world name for server '%s' is '%s'.",
                    self.server.server_name,
                    active_world_dir_name,
                )
            except (AppFileNotFoundError, ConfigParseError, Exception) as e:
                raise BackupRestoreError(
                    f"Cannot import world: Failed to get active world name for '{self.server.server_name}'."
                ) from e
            try:
                await self.extract_mcworld(
                    mcworld_backup_file_path, active_world_dir_name
                )
                self.logger.info(
                    "Server '%s': Active world import from '%s' completed successfully into '%s'.",
                    self.server.server_name,
                    mcworld_filename,
                    active_world_dir_name,
                )
                return active_world_dir_name
            except (
                AppFileNotFoundError,
                ExtractError,
                FileOperationError,
                MissingArgumentError,
                Exception,
            ) as e_extract:
                raise BackupRestoreError(
                    f"World import for server '{self.server.server_name}' failed into '{active_world_dir_name}': {e_extract}"
                ) from e_extract

    async def delete_world(self) -> bool:
        """Permanently delete the active world; absence also counts as success.

        The server normally regenerates that world at its next start.
        """
        async with self.server.operation_lock:
            try:
                active_world_dir = await self._get_active_world_directory_path()
                active_world_name = os.path.basename(active_world_dir)
            except (AppFileNotFoundError, ConfigParseError, Exception) as e:
                log_operation_error(
                    self.logger,
                    "Server '%s': Cannot delete active world, failed to determine path: %s",
                    self.server.server_name,
                    e,
                    error=e,
                )
                raise
            self.logger.debug(
                "Deleting active world '%s' for server '%s'.",
                active_world_dir,
                self.server.server_name,
            )
            if not await aiofiles.ospath.exists(active_world_dir):
                self.logger.debug(
                    "Server '%s': Active world directory '%s' does not exist. Nothing to delete.",
                    self.server.server_name,
                    active_world_dir,
                )
                return True
            if not await aiofiles.ospath.isdir(active_world_dir):
                raise FileOperationError(
                    f"Path for active world '{active_world_name}' is not a directory: {active_world_dir}"
                )
            success = await system_base.delete_path_robustly(
                active_world_dir,
                f"active world directory '{active_world_name}' for server '{self.server.server_name}'",
            )
            if success:
                self.logger.info(
                    "Server '%s': Successfully deleted active world directory '%s'.",
                    self.server.server_name,
                    active_world_dir,
                )
            else:
                raise FileOperationError(
                    f"Failed to completely delete active world directory '{active_world_name}' for server '{self.server.server_name}'. Check logs."
                )
            return success

    async def has_world_icon(self) -> bool:
        """Return whether the active world has a regular ``world_icon.jpeg`` file."""
        icon_path = await self.get_world_icon_filesystem_path()
        if icon_path and await aiofiles.ospath.isfile(icon_path):
            self.logger.debug(
                "Server '%s': World icon found at '%s'.",
                self.server.server_name,
                icon_path,
            )
            return True
        if icon_path:
            self.logger.debug(
                "Server '%s': World icon not found or is not a file at determined path '%s'.",
                self.server.server_name,
                icon_path,
            )
        return False

    @property
    def world_icon_filename(self) -> str:
        """str: The standard filename for a world's icon image (``world_icon.jpeg``)."""
        return "world_icon.jpeg"

    async def get_world_icon_filesystem_path(self) -> Optional[str]:
        """Optional[str]: The absolute filesystem path to the world icon for the active world.

        This is constructed by joining the active world's directory path (from
        :meth:`._get_active_world_directory_path`) with the standard icon filename
        (:attr:`.world_icon_filename`).

        Returns ``None`` if the active world directory path cannot be determined
        (e.g., if ``get_world_name()`` fails or is unavailable).
        """
        try:
            active_world_dir = await self._get_active_world_directory_path()
            return os.path.join(active_world_dir, self.world_icon_filename)
        except (AppFileNotFoundError, ConfigParseError, Exception) as e:
            self.logger.warning(
                "Server '%s': Cannot determine world icon path because active world name is unavailable: %s",
                self.server.server_name,
                e,
            )
            return None

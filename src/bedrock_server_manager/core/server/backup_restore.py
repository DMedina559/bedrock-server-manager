"""Backup and restore operations with explicit world and filesystem dependencies."""

import logging
import os
import re
from datetime import datetime, timezone
from glob import escape
from typing import TYPE_CHECKING
from uuid import uuid4

import aiofiles.ospath

from ...error import (
    AppFileNotFoundError,
    BackupRestoreError,
    ConfigurationError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
)
from ...logging import log_operation_error
from ...utils.threads import run_in_thread
from ..files import atomic_copy_file
from ..system import find_files

if TYPE_CHECKING:
    from ..bedrock_server import BedrockServer

CONFIG_FILES = ("server.properties", "allowlist.json", "permissions.json")
BACKUP_PATTERNS = {
    "world": "*.mcworld",
    "properties": "server_backup_*.properties",
    "allowlist": "allowlist_backup_*.json",
    "permissions": "permissions_backup_*.json",
}
CONFIG_BACKUP_PATTERN = re.compile(
    r"^(.+)_backup_\d{8}_\d{6}(?:_[a-f0-9]+)?(\.[^/\\]+)?$"
)


class ServerBackups:
    """Create and restore backups under the server operation and config file locks."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server
        self.logger = logging.LoggerAdapter(
            logging.getLogger(__name__), {"server_name": server.server_name}
        )

    @property
    def server_backup_directory(self) -> str | None:
        root = self.server.settings.get("paths.backups")
        return os.path.join(root, self.server.server_name) if root else None

    def _directory(self) -> str:
        directory = self.server_backup_directory
        if not directory:
            raise ConfigurationError(
                f"Backup directory is not configured for '{self.server.server_name}'."
            )
        return directory

    @staticmethod
    def _token() -> str:
        # UUID suffixes also distinguish sequential operations within the same second.
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex

    @staticmethod
    def _world_prefix(world: str) -> str:
        return re.sub(r'[:"/\\|?*]', "_", world) + "_backup_"

    async def _find(self, pattern: str) -> list[str]:
        files = await find_files(
            self._directory(), pattern, sort_by="mtime", reverse=True
        )
        return [
            str(path)
            for path in files
            if isinstance(path, str) and await aiofiles.ospath.isfile(path)
        ]

    async def list_backups(self, backup_type: str) -> list[str] | dict[str, list[str]]:
        if not isinstance(backup_type, str) or not backup_type.strip():
            raise MissingArgumentError("Backup type must be a non-empty string.")
        kind = backup_type.strip().lower()
        if kind not in BACKUP_PATTERNS and kind != "all":
            raise UserInputError(f"Invalid backup type: '{backup_type}'.")
        directory = self._directory()
        async with self.server.operation_lock:
            if not await aiofiles.ospath.isdir(directory):
                return {} if kind == "all" else []
            try:
                if kind != "all":
                    return await self._find(BACKUP_PATTERNS[kind])
                result = {}
                for category, pattern in BACKUP_PATTERNS.items():
                    files = await self._find(pattern)
                    if files:
                        result[f"{category}_backups"] = files
                return result
            except OSError as error:
                raise FileOperationError(
                    f"Cannot list backups for '{self.server.server_name}': {error}"
                ) from error

    async def prune_server_backups(
        self, component_prefix: str, file_extension: str
    ) -> None:
        if not isinstance(component_prefix, str) or not component_prefix.strip():
            raise MissingArgumentError("Backup prefix must be a non-empty string.")
        if (
            not isinstance(file_extension, str)
            or not file_extension.lstrip(".").strip()
        ):
            raise MissingArgumentError("Backup extension must be a non-empty string.")
        if any(char in component_prefix + file_extension for char in "/\\"):
            raise UserInputError(
                "Backup prefix and extension must be literal filename components."
            )
        count = self.server.settings.get("retention.backups", 3)
        if isinstance(count, bool):
            raise UserInputError("Backup retention must be a non-negative integer.")
        try:
            keep = int(count)
            if keep < 0 or str(keep) != str(count):
                raise ValueError
        except (TypeError, ValueError) as error:
            raise UserInputError(
                "Backup retention must be a non-negative integer."
            ) from error
        async with self.server.operation_lock:
            failures = []
            try:
                for path in (
                    await self._find(
                        f"{escape(component_prefix)}*.{escape(file_extension.lstrip('.').strip())}"
                    )
                )[keep:]:
                    try:
                        await run_in_thread(os.remove, path)
                    except OSError:
                        failures.append(path)
            except OSError as error:
                raise FileOperationError(f"Cannot prune backups: {error}") from error
            if failures:
                raise FileOperationError(
                    f"Cannot delete old backups: {', '.join(failures)}"
                )

    @staticmethod
    def _copy_backup(source: str, destination: str) -> None:
        atomic_copy_file(source, destination)
        # Backup ordering tracks creation, rather than the source's copied mtime.
        os.utime(destination, None)

    async def backup_world(self) -> str:
        async with self.server.operation_lock:
            world = await self.server.get_world_name()
            directory = self._directory()
            await run_in_thread(os.makedirs, directory, exist_ok=True)
            destination = os.path.join(
                directory, self._world_prefix(world) + self._token() + ".mcworld"
            )
            await self.server.worlds.export_world(world, destination)
            await self.prune_server_backups(self._world_prefix(world), "mcworld")
            return destination

    async def backup_config(self, filename: str) -> str | None:
        self._validate_filename(filename)
        async with self.server.operation_lock:
            source = os.path.join(self.server.paths.server_dir, filename)
            async with self.server.get_file_lock(source):
                if not await aiofiles.ospath.isfile(source):
                    return None
                directory = self._directory()
                await run_in_thread(os.makedirs, directory, exist_ok=True)
                stem, extension = os.path.splitext(filename)
                destination = os.path.join(
                    directory, f"{stem}_backup_{self._token()}{extension}"
                )
                try:
                    await run_in_thread(self._copy_backup, source, destination)
                except OSError as error:
                    raise FileOperationError(
                        f"Cannot back up '{filename}': {error}"
                    ) from error
            await self.prune_server_backups(stem + "_backup_", extension)
            self.logger.debug("Configuration backup created: '%s'.", destination)
            return destination

    async def backup_all_data(self) -> dict[str, str | None]:
        async with self.server.operation_lock:
            results: dict[str, str | None] = {}
            world_error = None
            try:
                results["world"] = await self.backup_world()
            except Exception as error:
                world_error = error
                results["world"] = None
                log_operation_error(
                    self.logger,
                    "World backup failed for '%s'.",
                    self.server.server_name,
                    error=error,
                )
            for filename in CONFIG_FILES:
                try:
                    results[filename] = await self.backup_config(filename)
                except Exception as error:
                    log_operation_error(
                        self.logger,
                        "Configuration backup failed for '%s'.",
                        filename,
                        error=error,
                    )
                    results[filename] = None
            if world_error:
                raise BackupRestoreError(
                    f"World backup failed for '{self.server.server_name}'. Configuration backups were attempted."
                ) from world_error
            missing = [name for name, path in results.items() if path is None]
            if missing:
                self.logger.warning(
                    "Backup incomplete; configuration files missing or failed: %s.",
                    ", ".join(missing),
                )
            else:
                self.logger.info(
                    "Full backup completed for server '%s'.", self.server.server_name
                )
            return results

    @staticmethod
    def _validate_filename(filename: str) -> None:
        if (
            not isinstance(filename, str)
            or not filename
            or filename in (".", "..")
            or any(char in filename for char in "/\\")
        ):
            raise UserInputError("Configuration file must be a local filename.")

    @staticmethod
    def _config_filename(path: str) -> str:
        match = CONFIG_BACKUP_PATTERN.fullmatch(os.path.basename(path))
        if not match:
            raise UserInputError("Invalid configuration backup filename.")
        filename = match.group(1) + match.group(2)
        if filename not in CONFIG_FILES:
            raise UserInputError(
                "Configuration backup name and extension do not match."
            )
        return filename

    async def restore_config(self, path: str) -> str:
        filename = self._config_filename(path)
        async with self.server.operation_lock:
            if await self.server.is_running():
                raise BackupRestoreError(
                    "Stop the server before restoring its configuration."
                )
            if not await aiofiles.ospath.isfile(path):
                raise AppFileNotFoundError(path, "Backup config file")
            destination = os.path.join(self.server.paths.server_dir, filename)
            async with self.server.get_file_lock(destination):
                try:
                    await run_in_thread(
                        os.makedirs, self.server.paths.server_dir, exist_ok=True
                    )
                    await run_in_thread(atomic_copy_file, path, destination)
                except OSError as error:
                    raise FileOperationError(
                        f"Cannot restore '{filename}': {error}"
                    ) from error
            self.logger.debug("Configuration restored from '%s'.", path)
            return destination

    async def restore_all_data_from_latest(self) -> dict[str, str | None]:
        async with self.server.operation_lock:
            directory = self._directory()
            if not await aiofiles.ospath.isdir(directory):
                return {}
            if await self.server.is_running():
                raise BackupRestoreError("Stop the server before restoring its data.")
            # Resolve all candidates before mutating files. Properties must restore
            # first so the selected world follows the restored level-name.
            candidates = {
                filename: await self._find(BACKUP_PATTERNS[kind])
                for filename, kind in zip(
                    CONFIG_FILES, ("properties", "allowlist", "permissions")
                )
            }
            worlds = await self._find(BACKUP_PATTERNS["world"])
            results: dict[str, str | None] = {}
            failures = []
            for filename, files in candidates.items():
                try:
                    results[filename] = (
                        await self.restore_config(files[0]) if files else None
                    )
                except Exception as error:
                    log_operation_error(
                        self.logger, "Restore failed for '%s'.", filename, error=error
                    )
                    results[filename] = None
                    failures.append(filename)
            try:
                if "server.properties" in failures:
                    raise BackupRestoreError(
                        "Cannot select a world after properties restore failed."
                    )
                prefix = self._world_prefix(await self.server.get_world_name())
                matching = [
                    path for path in worlds if os.path.basename(path).startswith(prefix)
                ]
                world = (
                    await self.server.worlds.import_world(matching[0])
                    if matching
                    else None
                )
                results["world"] = (
                    os.path.join(self.server.paths.server_dir, "worlds", world)
                    if world
                    else None
                )
            except Exception:
                self.logger.exception(
                    "World restore failed for '%s'.", self.server.server_name
                )
                results["world"] = None
                failures.append("world")
            if failures:
                raise BackupRestoreError(f"Restore failed for: {', '.join(failures)}")
            self.logger.info(
                "Latest-backup restore completed for server '%s' (%s components restored).",
                self.server.server_name,
                sum(path is not None for path in results.values()),
            )
            return results

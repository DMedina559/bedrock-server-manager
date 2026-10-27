"""Backup and restore operations with explicit world and filesystem dependencies."""

import logging
import os
import re
from glob import escape
from typing import TYPE_CHECKING

import aiofiles.ospath

from ...backups.models import ConfigComponent
from ...backups.server import UnifiedServerBackups
from ...error import (
    AppFileNotFoundError,
    BackupRestoreError,
    ConfigurationError,
    FileOperationError,
    MissingArgumentError,
    UserInputError,
)
from ...failures import classify_failure
from ...results import (
    CleanupResult,
    CompletedItem,
    ComponentResults,
)
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


class ServerBackups(UnifiedServerBackups):
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
    ) -> CleanupResult:
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
            files = await self._find(
                f"{escape(component_prefix)}*.{escape(file_extension.lstrip('.').strip())}"
            )
            deleted = []
            failures = {}
            for path in ([] if keep == 0 else files[keep:]):
                try:
                    await run_in_thread(os.remove, path)
                    deleted.append(path)
                except OSError as error:
                    failures[path] = classify_failure(error).error
            return CleanupResult(
                deleted=deleted,
                retained=files if keep == 0 else files[:keep],
                failures=failures,
            )

    async def backup_world(self) -> str:
        """Compatibility alias: create the unified archive, including configuration."""
        snapshot = await self.create_snapshot()
        return os.path.join(self._directory(), snapshot.filename)

    async def backup_config(self, filename: str) -> str | None:
        """Compatibility alias: capture a unified archive instead of a loose file."""
        if filename not in CONFIG_FILES:
            raise UserInputError("Unsupported server configuration file.")
        if not await aiofiles.ospath.isfile(
            os.path.join(self.server.paths.server_dir, filename)
        ):
            return None
        snapshot = await self.create_snapshot()
        return os.path.join(self._directory(), snapshot.filename)

    @staticmethod
    def _config_filename(path: str) -> str:
        match = CONFIG_BACKUP_PATTERN.fullmatch(os.path.basename(path))
        if not match:
            raise UserInputError("Invalid configuration backup filename.")
        filename = match.group(1) + (match.group(2) or "")
        if filename not in CONFIG_FILES:
            raise UserInputError(
                "Configuration backup name and extension do not match."
            )
        return filename

    async def restore_config(
        self, path: str, *, component: ConfigComponent | None = None
    ) -> str:
        if path.endswith(".bsmbackup"):
            if component is None:
                raise UserInputError(
                    "Select a component explicitly when restoring a unified archive."
                )
            identifier = os.path.basename(path)
            if os.path.realpath(path) != str(self.resolve_backup(identifier)):
                raise BackupRestoreError("Backup must belong to this server.")
            plan = await self.plan_restore(identifier, [component])
            await self.restore_snapshot(identifier, [component], plan.token)
            return os.path.join(self.server.paths.server_dir, component)
        filename = self._config_filename(path)
        if component is not None and component != filename:
            raise UserInputError("Backup file does not match the selected component.")
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

    async def restore_all_data_from_latest(self) -> ComponentResults:
        """Restore one latest unified archive, never combine independent legacy files."""
        async with self.server.operation_lock:
            snapshots = await self.list_snapshots()
            if not snapshots:
                raise BackupRestoreError(
                    "No unified backup is available. Select individual legacy files explicitly."
                )
            snapshot = await self.inspect_snapshot(snapshots[0].backup_id)
            assert snapshot.manifest is not None
            selected = [
                name
                for name, state in snapshot.manifest.components.items()
                if state == "included"
            ]
            plan = await self.plan_restore(snapshot.backup_id, selected)
            result = await self.restore_snapshot(
                snapshot.backup_id, selected, plan.token
            )
            return ComponentResults(
                components={
                    name: CompletedItem(
                        outcome="completed", path=plan.destinations[name]
                    )
                    for name in result.restored
                }
            )

"""Shared dependencies, file paths, locks, and runtime snapshots for a server."""

import logging
import os
import platform
from typing import TYPE_CHECKING, Dict, Optional

from .paths import ServerPaths

if TYPE_CHECKING:
    from ...context import AppContext
    from ...config.settings import Settings
    from ...state.app_state import AppState
    from ...db.storage import Storage

from ...error import ConfigurationError, MissingArgumentError
from ...state.models import RuntimeState
from ...utils.general import ReentrantAsyncLock


class ServerResources:
    """Shared server identity, paths, locks, and runtime snapshots."""

    def __init__(
        self,
        server_name: str,
        *,
        settings: Optional["Settings"] = None,
        app_context: Optional["AppContext"] = None,
        state: Optional["AppState"] = None,
        storage: Optional["Storage"] = None,
    ) -> None:
        """Validate dependencies and freeze the server filesystem identity."""
        super().__init__()
        if not server_name:
            raise MissingArgumentError(
                "BedrockServer cannot be initialized without a server_name."
            )
        self.logger: logging.Logger = logging.getLogger(__name__)
        if settings is None:
            raise ConfigurationError("Settings instance is required but not provided.")
        self.settings = settings
        self.state = state
        self._runtime_state = state.runtime if state is not None else RuntimeState()
        self.storage = storage
        self.app_context = app_context
        self.logger.debug(f"Server resources for '{server_name}' initialized")
        _base_dir_val = self.settings.get("paths.servers")
        if not _base_dir_val:
            raise ConfigurationError(
                "BASE_DIR not configured in settings. Cannot initialize BedrockServer."
            )
        _app_cfg_dir_val = self.settings.config_dir
        if not _app_cfg_dir_val:
            raise ConfigurationError(
                "Application config_dir not available from settings. Cannot initialize BedrockServer."
            )
        self._paths = ServerPaths(
            server_name, _base_dir_val, _app_cfg_dir_val, platform.system()
        )
        self._file_locks: Dict[str, ReentrantAsyncLock] = {}
        self.operation_lock: ReentrantAsyncLock = ReentrantAsyncLock()
        self.logger.debug(
            f"Server resources initialized for '{self.server_name}' at '{self.paths.server_dir}'. App Config Dir: '{self.paths.app_config_dir}'"
        )

    @property
    def players(self) -> list[dict[str, str]]:
        return [
            {"name": player.name, "xuid": player.xuid}
            for player in self._runtime_state.get_server_runtime(
                self.server_name
            ).players
        ]

    @players.setter
    def players(self, values: list[dict[str, str]]) -> None:
        self._runtime_state.update_server_runtime(
            self.server_name, players=values, players_online=len(values)
        )

    @property
    def player_count(self) -> int:
        return self._runtime_state.get_server_runtime(self.server_name).players_online

    def get_pid_file_path(self) -> str:
        """Return the process ID file in this server's configuration directory."""
        return os.path.join(
            self.paths.server_config_dir, f"bedrock_{self.server_name}.pid"
        )

    def get_file_lock(self, filepath: str) -> ReentrantAsyncLock:
        """Retrieves or creates a ReentrantAsyncLock for the specified filepath.

        This ensures that asynchronous operations (like atomic JSON writes)
        do not concurrently collide when targeting the same configuration file,
        while allowing re-entrant locks within the same task.

        Args:
            filepath (str): The absolute path to the file.

        Returns:
            ReentrantAsyncLock: The re-entrant lock associated with the given file.
        """
        filepath = os.path.normcase(os.path.realpath(filepath))
        if filepath not in self._file_locks:
            self._file_locks[filepath] = ReentrantAsyncLock()
        return self._file_locks[filepath]

    @property
    def server_name(self) -> str:
        return self.paths.server_name

    @property
    def paths(self) -> ServerPaths:
        """Immutable filesystem locations for this server identity."""
        return self._paths

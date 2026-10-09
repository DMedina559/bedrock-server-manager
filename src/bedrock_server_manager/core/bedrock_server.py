"""A single Bedrock server's runtime and game data interface."""

import asyncio
import subprocess
from io import BufferedWriter
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from . import server
from .data import SummaryRecord

if TYPE_CHECKING:
    import psutil

    from ..config.settings import Settings
    from ..context import AppContext
    from ..db.storage import Storage
    from ..state.app_state import AppState


class BedrockServer(
    server.ServerStateMixin,
    server.ServerProcessMixin,
    server.ServerInstallationMixin,
    server.ServerWorldMixin,
    server.ServerAddonMixin,
    server.ServerBackupMixin,
    server.ServerPlayerMixin,
    server.ServerAllowlistMixin,
    server.ServerPermissionsMixin,
    server.ServerPropertiesMixin,
    server.BedrockServerBaseMixin,
):
    """Manage a Bedrock process, configuration, players, worlds, and addons.

    Software acquisition and removal live in core.server.software and removal."""

    def __init__(
        self,
        server_name: str,
        *,
        settings: Optional["Settings"] = None,
        app_context: Optional["AppContext"] = None,
        state: Optional["AppState"] = None,
        storage: Optional["Storage"] = None,
    ) -> None:
        """Initialize the runtime with explicit application dependencies."""
        super().__init__(
            server_name=server_name,
            settings=settings,
            app_context=app_context,
            state=state,
            storage=storage,
        )
        self._process: Optional[
            Union[subprocess.Popen[Any], asyncio.subprocess.Process, "psutil.Process"]
        ] = None
        self.intentionally_stopped = True
        self.failure_count = 0
        self.start_time = 0.0
        self._log_file_handle: BufferedWriter | None = None
        self._log_file_cursor = 0
        self._scan_log_cursor = 0
        self.logger.info(
            f"BedrockServer instance '{self.server_name}' fully initialized and ready for operations."
        )

    async def get_summary_info(self) -> Dict[str, Any]:
        """Returns a generic summary of the server's current status and state asynchronously."""
        self.logger.debug(
            f"Gathering async summary info for server '{self.server_name}'."
        )
        status = await self.get_status()
        version = await self.get_version()
        summary = {
            "name": self.server_name,
            "status": status,
            "version": version,
            "player_count": self.player_count,
            "players": self.players,
        }
        return SummaryRecord.model_validate(summary).model_dump(mode="json")

"""One Bedrock runtime composed from explicit server components."""

from typing import TYPE_CHECKING

from pydantic import JsonValue

from ..error import ConfigParseError, UserInputError
from .data import PlayerRecord, SummaryRecord
from .server.addon import ServerAddons
from .server.allowlist import ServerAllowlist
from .server.backup_restore import ServerBackups
from .server.configuration import ServerConfiguration
from .server.installation import ServerInstallation
from .server.permissions import ServerPermissions
from .server.player import ServerPlayers
from .server.process import ServerProcess
from .server.properties import ServerProperties
from .server.resources import ServerResources
from .server.world import ServerWorlds

if TYPE_CHECKING:
    from ..config.settings import Settings
    from ..context import AppContext
    from ..db.storage import Storage
    from ..state.app_state import AppState


class BedrockServer(ServerResources):
    """Own a server's identity and coordinate its process and game data."""

    def __init__(
        self,
        server_name: str,
        *,
        settings: "Settings | None" = None,
        app_context: "AppContext | None" = None,
        state: "AppState | None" = None,
        storage: "Storage | None" = None,
    ) -> None:
        super().__init__(
            server_name,
            settings=settings,
            app_context=app_context,
            state=state,
            storage=storage,
        )
        self.configuration = ServerConfiguration(self)
        self.properties = ServerProperties(self)
        self.installation = ServerInstallation(self)
        self.process = ServerProcess(self)
        self.player_tracker = ServerPlayers(self)
        self.worlds = ServerWorlds(self)
        self.addons = ServerAddons(self)
        self.allowlist = ServerAllowlist(self)
        self.permissions = ServerPermissions(self)
        self.backups = ServerBackups(self)

    async def is_installed(self) -> bool:
        return await self.installation.is_installed()

    async def validate_installation(self) -> bool:
        return await self.installation.validate_installation()

    async def is_running(self) -> bool:
        return await self.process.is_running()

    async def start(self) -> None:
        await self.process.start()

    async def stop(self) -> None:
        await self.process.stop()

    async def send_command(self, command: str) -> None:
        await self.process.send_command(command)

    async def get_process_info(self) -> dict[str, object] | None:
        return await self.process.get_process_info()

    async def get_version(self) -> str:
        return self.configuration.snapshot().installed_version

    async def set_version(self, version_string: str) -> None:
        await self.configuration.update("server_info.installed_version", version_string)

    async def get_autoupdate(self) -> bool:
        return self.configuration.snapshot().autoupdate

    async def set_autoupdate(self, value: bool) -> None:
        await self.configuration.update("settings.autoupdate", value)

    async def get_autostart(self) -> bool:
        return self.configuration.snapshot().autostart

    async def set_autostart(self, value: bool) -> None:
        await self.configuration.update("settings.autostart", value)

    async def get_target_version(self) -> str:
        return self.configuration.snapshot().target_version.strip() or "LATEST"

    async def set_target_version(self, version_string: str) -> None:
        await self.configuration.update("settings.target_version", version_string)

    async def get_custom_config_value(self, key: str) -> JsonValue:
        if not isinstance(key, str) or not key.strip():
            raise UserInputError("Custom configuration key must be a non-empty string.")
        return self.configuration.read(f"custom.{key}")

    async def set_custom_config_value(self, key: str, value: JsonValue) -> None:
        if not isinstance(key, str) or not key.strip():
            raise UserInputError("Custom configuration key must be a non-empty string.")
        await self.configuration.update(f"custom.{key}", value)

    async def get_status_from_config(self) -> str:
        return self.configuration.snapshot().status

    async def set_status_in_config(self, status_string: str) -> None:
        """Preserve the existing API event path until event dispatch is extracted."""
        if not isinstance(status_string, str):
            raise UserInputError("Server status must be a string.")
        if self.app_context and self.app_context.api:
            try:
                await self.app_context.api.server.set_status(
                    request={"server_name": self.server_name, "status": status_string}
                )
                return
            except AttributeError:
                pass
        await self.configuration.update("server_info.status", status_string)

    async def get_world_name(self) -> str:
        value = (
            (await self.properties.get_server_properties())
            .get("level-name", "")
            .strip()
        )
        if not value:
            raise ConfigParseError(
                f"Missing or empty level-name in {self.paths.server_properties_path}"
            )
        return value

    async def get_status(self) -> str:
        """Read effective process status without persisting or emitting events."""
        running = await self.is_running()
        stored = self.configuration.snapshot().status
        if running:
            return "RUNNING"
        return "STOPPED" if stored in ("RUNNING", "UNKNOWN") else stored

    async def reconcile_status(self, running: bool) -> str:
        """Publish an observed process transition from the monitor."""
        stored = self.configuration.snapshot().status
        status = (
            "RUNNING"
            if running
            else "STOPPED" if stored in ("RUNNING", "UNKNOWN") else stored
        )
        if status != stored:
            await self.set_status_in_config(status)
        return status

    async def get_summary_info(self) -> SummaryRecord:
        status = await self.get_status()
        runtime = self._runtime_state.get_server_runtime(self.server_name)
        return SummaryRecord(
            name=self.server_name,
            status=status,
            version=await self.get_version(),
            player_count=runtime.players_online,
            players=[
                PlayerRecord(name=player.name, xuid=player.xuid)
                for player in runtime.players
            ],
        )

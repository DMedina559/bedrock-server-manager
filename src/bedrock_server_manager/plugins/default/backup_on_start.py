# bedrock_server_manager/plugins/default/auto_backup_on_start.py
"""
Plugin to automatically back up a server before it starts.
"""

import asyncio
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from bedrock_server_manager import ExistingServerName, PluginBase, app_event
from bedrock_server_manager.backups.contents import DEFAULT_COMPONENTS, BackupComponents
from bedrock_server_manager.logging import log_operation_error


class PluginSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    servers: list[ExistingServerName] = Field(
        default_factory=list,
        description="Servers to back up before starting. Leave empty to include all servers.",
    )
    require_complete_backup: bool = Field(
        default=False, description="Cancel server start if the backup cannot complete."
    )
    reuse_sequence_backup: bool = Field(
        default=True,
        description="Reuse a complete backup from the same operation sequence, including a pre-update backup.",
    )
    backup_mode: Literal["world", "selected", "full", "default"] = Field(
        default="world",
        description="Contents to capture before start. Default uses global backup settings.",
    )
    components: BackupComponents = Field(
        default_factory=lambda: list(DEFAULT_COMPONENTS),
        description="Components used only in selected mode.",
    )
    encryption: Literal["default", "on", "off"] = Field(
        default="default",
        description="Use global encryption, force encryption on, or force it off.",
    )
    timeout_seconds: float = Field(
        default=300.0,
        gt=0,
        le=3600,
        description="Maximum seconds for a pre-start backup (default 5 minutes). Optional backup failures allow startup; required backups prevent startup.",
    )
    enable_backup_on_start: bool = Field(
        default=True, description="Back up this server before starting it."
    )


class AutoBackupOnStart(PluginBase):
    """Backs up selected server contents before starting a server. This
    plugin hooks into the ``before_server_start`` event to ensure a recent backup
    exists before the server goes online.
    """

    settings_model = PluginSettings

    version = "1.3.2"
    description = "Backs up selected server contents before starting a server. This plugin hooks into the `before_server_start` event."
    author = "dmedina559"
    name = "Auto Backup On Start"

    @app_event("on_load")
    async def plugin_loaded(self):
        """Logs a message when the plugin is loaded."""
        self.logger.debug(
            "Plugin loaded. Will back up selected contents before server starts."
        )

    @app_event("before_server_start", timeout_seconds=3600)
    async def backup_on_start(self, **kwargs: Any):
        """
        Backs up selected contents before the server starts.
        """
        from bedrock_server_manager.operations import OperationName

        sequence = self.api.operations.sequence()
        if sequence and any(
            item.name == OperationName.BACKUP_RESTORE
            and item.server_name == kwargs.get("server_name")
            for item in sequence.ancestry
        ):
            return
        if not await self.get_plugin_setting("enable_backup_on_start", default=True):
            self.logger.debug("Backup on start is disabled in plugin settings.")
            return

        server_name = kwargs.get("server_name")
        if not server_name:
            return
        selected = await self.get_plugin_setting("servers", default=[])
        if selected and server_name not in selected:
            return

        mode = await self.get_plugin_setting("backup_mode", default="world")
        request = {
            "server_name": server_name,
            "mode": None if mode == "default" else mode,
        }
        if mode == "selected":
            request["components"] = await self.get_plugin_setting(
                "components", default=list(DEFAULT_COMPONENTS)
            )
        if await self.get_plugin_setting("reuse_sequence_backup", default=True):
            coverage = await self.api.backup_restore.can_reuse_server_backup(
                request=request
            )
            if coverage.reusable:
                self.logger.info(
                    "Skipping pre-start backup for '%s': a complete backup already finished in this operation sequence.",
                    server_name,
                )
                return

        self.logger.info("Performing pre-start backup for server '%s'...", server_name)

        try:
            # The start operation holds the server lock and verified it is offline.

            encryption = await self.get_plugin_setting("encryption", default="default")
            timeout = await self.get_plugin_setting("timeout_seconds", default=900.0)
            self.logger.debug("Pre-start backup deadline: %.3f seconds", timeout)
            async with asyncio.timeout(timeout):
                result = await self.api.backup_restore.backup_all(
                    request={
                        **request,
                        "encrypted": (
                            None if encryption == "default" else encryption == "on"
                        ),
                    }
                )

            if result.status == "success":
                self.logger.info(
                    "Pre-start backup for '%s' completed successfully.", server_name
                )
            else:
                event = kwargs.get("event")
                if event is not None and await self.get_plugin_setting(
                    "require_complete_backup", default=False
                ):
                    event.cancel("Pre-start backup did not complete.")
                # Partial and skipped work are explicit operation outcomes.
                error_message = result.message
                self.logger.warning(
                    "Pre-start backup for '%s' failed: %s", server_name, error_message
                )

        except TimeoutError:
            event = kwargs.get("event")
            required = await self.get_plugin_setting(
                "require_complete_backup", default=False
            )
            if required and event is not None:
                event.cancel("Required pre-start backup timed out.")
            self.logger.warning(
                "Pre-start backup timed out for '%s'; startup %s",
                server_name,
                (
                    "cancelled because a complete backup is required"
                    if required
                    else "will continue because backup is optional"
                ),
            )
        except Exception as e:
            event = kwargs.get("event")
            if event is not None and await self.get_plugin_setting(
                "require_complete_backup", default=False
            ):
                event.cancel("Pre-start backup failed.")
            # Keep optional backup failures isolated from server startup.
            # This ensures the plugin does not crash the main application.
            log_operation_error(
                self.logger,
                "An unexpected error occurred during pre-start backup for '%s': %s",
                server_name,
                e,
                error=e,
            )

# bedrock_server_manager/plugins/default/auto_backup_on_start.py
"""
Plugin to automatically back up a server before it starts.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from bedrock_server_manager import ExistingServerName, PluginBase, app_event
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
    enable_backup_on_start: bool = Field(
        default=True, description="Back up this server before starting it."
    )


class AutoBackupOnStart(PluginBase):
    """Ensures a complete backup before starting a server. This
    plugin hooks into the ``before_server_start`` event to ensure a recent backup
    exists before the server goes online.
    """

    settings_model = PluginSettings

    version = "1.3.0"
    description = "Ensures a complete backup before starting a server. This plugin hooks into the `before_server_start` event."
    author = "dmedina559"
    name = "Auto Backup On Start"

    @app_event("on_load")
    async def plugin_loaded(self):
        """Logs a message when the plugin is loaded."""
        self.logger.debug(
            "Plugin loaded. Will ensure a complete backup before server starts."
        )

    @app_event("before_server_start")
    async def backup_on_start(self, **kwargs: Any):
        """
        Triggers a full backup of the server before it starts.
        """
        if not await self.get_plugin_setting("enable_backup_on_start", default=True):
            self.logger.debug("Backup on start is disabled in plugin settings.")
            return

        server_name = kwargs.get("server_name")
        if not server_name:
            return
        selected = await self.get_plugin_setting("servers", default=[])
        if selected and server_name not in selected:
            return

        if await self.get_plugin_setting("reuse_sequence_backup", default=True):
            from bedrock_server_manager.operations import (
                OperationName,
                OperationResultQuery,
            )

            required = {
                "world",
                "server.properties",
                "allowlist.json",
                "permissions.json",
            }
            backups = self.api.operations.results(
                OperationResultQuery(
                    name=OperationName.BACKUP_CREATE,
                    server_name=server_name,
                    status="finished",
                    outcome="completed",
                )
            )
            if any(required.issubset(item.scope) for item in backups):
                self.logger.info(
                    "Skipping pre-start backup for '%s': a complete backup already finished in this operation sequence.",
                    server_name,
                )
                return

        self.logger.info("Performing pre-start backup for server '%s'...", server_name)

        try:
            # The start operation holds the server lock and verified it is offline.

            result = await self.api.backup_restore.backup_all(
                request={"server_name": server_name}
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

# bedrock_server_manager/plugins/default/auto_backup_on_start.py
"""
Plugin to automatically back up a server before it starts.
"""

from typing import Any

from bedrock_server_manager import PluginBase, app_event

from ...logging import log_operation_error


class AutoBackupOnStart(PluginBase):
    """
    Performs a full backup of a server each time a start command is initiated.
    This plugin hooks into the `before_server_start` event to ensure a recent
    backup exists before the server goes online.
    """

    version = "1.2.0"
    description = "Performs a full backup of a server each time a start command is initiated. This plugin hooks into the `before_server_start` event."
    author = "dmedina559"
    name = "Auto Backup On Start"

    @app_event("on_load")
    async def plugin_loaded(self):
        """Logs a message when the plugin is loaded."""
        self.logger.debug(
            "Plugin loaded. Will perform a full backup before any server starts."
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

        self.logger.info("Performing pre-start backup for server '%s'...", server_name)

        try:
            # The server is guaranteed to be offline at this point, so it is safe
            # to run a backup without stopping it first.

            result = await self.api.backup_restore.backup_all(
                request={"server_name": server_name}
            )

            if result.status == "success":
                self.logger.info(
                    "Pre-start backup for '%s' completed successfully.", server_name
                )
            else:
                # The backup operation itself reported an error (e.g., file permissions).
                error_message = result.message
                self.logger.warning(
                    "Pre-start backup for '%s' failed: %s", server_name, error_message
                )

        except Exception as e:
            # A more serious error where the API call itself failed.
            # This ensures the plugin does not crash the main application.
            log_operation_error(
                self.logger,
                "An unexpected error occurred during pre-start backup for '%s': %s",
                server_name,
                e,
                error=e,
            )

# bedrock_server_manager/plugins/default/auto_backup_on_start.py
"""
Plugin to automatically back up a server before it starts.
"""
from bedrock_server_manager import PluginBase
from typing import Any


class AutoBackupOnStart(PluginBase):
    """
    Performs a full backup of a server each time a start command is initiated.
    This plugin hooks into the `before_server_start` event to ensure a recent
    backup exists before the server goes online.
    """

    version = "1.1.0"

    def on_load(self):
        """Logs a message when the plugin is loaded."""
        self.logger.info(
            "Plugin loaded. Will perform a full backup before any server starts."
        )

    def before_server_start(self, **kwargs: Any):
        """
        Triggers a full backup of the server before it starts.
        """
        server_name = kwargs.get("server_name")
        self.logger.info(f"Performing pre-start backup for server '{server_name}'...")

        try:
            # The server is guaranteed to be offline at this point, so it is safe
            # to run a backup without stopping it first.
            result = self.api.backup_all(
                server_name=server_name, stop_start_server=False
            )

            if result.get("status") == "success":
                self.logger.info(
                    f"Pre-start backup for '{server_name}' completed successfully."
                )
            else:
                # The backup operation itself reported an error (e.g., file permissions).
                error_message = result.get("message", "Unknown backup error")
                self.logger.warning(
                    f"Pre-start backup for '{server_name}' failed: {error_message}"
                )

        except Exception as e:
            # A more serious error where the API call itself failed.
            # This ensures the plugin does not crash the main application.
            self.logger.error(
                f"An unexpected error occurred during pre-start backup for '{server_name}': {e}",
                exc_info=True,
            )

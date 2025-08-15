# bedrock_server_manager/plugins/default/world_operation_notifications.py
"""
Plugin to send in-game notifications before world operations like export, import, or reset.
"""
from bedrock_server_manager import PluginBase


class WorldOperationNotificationsPlugin(PluginBase):
    """
    Notifies in-game players before significant world operations (export, import, reset)
    are performed on a running server, providing a heads-up for potential disruptions.
    """

    version = "1.0.0"

    def on_load(self):
        """Logs a message when the plugin is loaded."""
        self.logger.info("Plugin loaded. Will send notifications for world operations.")

    def _is_server_running(self, server_name: str) -> bool:
        """Checks if a server is currently running via the API."""
        try:
            response = self.api.get_server_running_status(server_name=server_name)
            if response and response.get("status") == "success":
                return response.get("is_running", False)
            self.logger.warning(
                f"Could not determine running status for '{server_name}'. API: {response}"
            )
        except AttributeError:
            self.logger.error(
                "API is missing 'get_server_running_status'. Cannot check server status."
            )
        except Exception as e:
            self.logger.error(
                f"Error checking server status for '{server_name}': {e}", exc_info=True
            )
        return False

    def _send_ingame_warning(self, server_name: str, message: str, context: str):
        """Helper to send an in-game "say" command if the server is running."""
        if self._is_server_running(server_name):
            try:
                # Ensure the message is formatted as a "say" command.
                if not message.lower().startswith("say "):
                    command = f"say {message}"
                else:
                    command = message

                self.api.send_command(server_name=server_name, command=command)
                self.logger.info(
                    f"Sent {context} warning to '{server_name}': {message}"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to send {context} warning to '{server_name}': {e}",
                    exc_info=True,
                )
        else:
            self.logger.info(
                f"Server '{server_name}' not running, skipping {context} warning."
            )

    def before_world_export(self, server_name: str, export_dir: str):
        """Notifies players before a world export begins."""
        self.logger.debug(
            f"Handling before_world_export for '{server_name}' to '{export_dir}'."
        )
        self._send_ingame_warning(
            server_name, "World export starting...", "world export"
        )

    def before_world_import(self, server_name: str, file_path: str):
        """Notifies players before a world import begins."""
        self.logger.debug(
            f"Handling before_world_import for '{server_name}' from '{file_path}'."
        )
        self._send_ingame_warning(
            server_name,
            "World import starting... Current world will be replaced.",
            "world import",
        )

    def before_world_reset(self, server_name: str):
        """Sends a critical warning before a world reset operation."""
        self.logger.debug(f"Handling before_world_reset for '{server_name}'.")
        self.logger.warning(
            f"Critical operation: World reset initiated for server '{server_name}'."
        )
        self._send_ingame_warning(
            server_name,
            "CRITICAL WARNING: Server world is being reset NOW!",
            "world reset",
        )

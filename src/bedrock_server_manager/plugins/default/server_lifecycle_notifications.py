# bedrock_server_manager/plugins/default/server_lifecycle_notifications.py
"""
Plugin to send in-game messages and manage delays during server lifecycle events.
"""
import time
from bedrock_server_manager import PluginBase


class ServerLifecycleNotificationsPlugin(PluginBase):
    """
    Enhances server management by sending in-game notifications and introducing
    delays at critical server lifecycle points (e.g., stop, start, update, delete).
    This gives players warnings and can help ensure smoother transitions.
    """

    version = "1.0.1"

    def on_load(self):
        """Initializes default delays and logs plugin activation."""
        # Default delays in seconds. These could be made configurable in the future.
        self.stop_warning_delay: int = 10
        self.post_stop_settle_delay: int = 1
        self.post_start_settle_delay: int = 3

        self.logger.info(
            "Plugin loaded. Will manage server lifecycle notifications and delays."
        )

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

    def _send_ingame_message(self, server_name: str, message: str, context: str):
        """Helper to send an in-game message if the server is running."""
        if self._is_server_running(server_name):
            try:
                # Ensure the message is formatted as a "say" command.
                if not message.lower().startswith("say "):
                    command = f"say {message}"
                else:
                    command = message

                self.api.send_command(server_name=server_name, command=command)
                self.logger.info(
                    f"Sent {context} message to '{server_name}': {message}"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to send {context} message to '{server_name}': {e}",
                    exc_info=True,
                )
        else:
            self.logger.info(
                f"Server '{server_name}' not running, skipping {context} message."
            )

    def before_server_stop(self, server_name: str):
        """Sends a shutdown warning and waits before the server stops."""
        self.logger.debug(f"Handling before_server_stop for '{server_name}'.")
        if self._is_server_running(server_name):
            warning_message = (
                f"Server is stopping in {self.stop_warning_delay} seconds..."
            )
            self._send_ingame_message(server_name, warning_message, "shutdown warning")

            self.logger.info(
                f"Waiting {self.stop_warning_delay}s before '{server_name}' stops."
            )
            time.sleep(self.stop_warning_delay)

    def after_server_stop(self, server_name: str, result: dict):
        """Waits for a short period after a server stops, e.g., for port release."""
        self.logger.debug(f"Handling after_server_stop for '{server_name}'.")
        if result.get("status") == "success":
            self.logger.info(
                f"Waiting {self.post_stop_settle_delay}s after '{server_name}' stopped."
            )
            time.sleep(self.post_stop_settle_delay)

    def before_delete_server_data(self, server_name: str):
        """Sends a final warning before server data is deleted if the server is running."""
        self.logger.debug(f"Handling before_delete_server_data for '{server_name}'.")
        self._send_ingame_message(
            server_name,
            "WARNING: Server data is being deleted permanently!",
            "data deletion warning",
        )

    def before_server_update(self, server_name: str, target_version: str):
        """Notifies players before a server update begins."""
        self.logger.debug(
            f"Handling before_server_update for '{server_name}' to v{target_version}."
        )
        self._send_ingame_message(
            server_name, "Server is updating now, please wait...", "update notification"
        )

    def after_server_start(self, server_name: str, result: dict):
        """Waits for a short period after a server starts to allow initialization."""
        self.logger.debug(f"Handling after_server_start for '{server_name}'.")
        if result.get("status") == "success":
            self.logger.info(
                f"Waiting {self.post_start_settle_delay}s after '{server_name}' started."
            )
            time.sleep(self.post_start_settle_delay)

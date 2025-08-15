# bedrock_server_manager/plugins/default/auto_reload_config.py
"""
Plugin that automatically reloads server configurations after changes.
"""
from bedrock_server_manager import PluginBase


class AutoReloadPlugin(PluginBase):
    """
    Automatically sends a `reload` command to a running server after its
    configuration files (e.g., allowlist.json, permissions.json) are modified,
    ensuring changes take effect immediately without manual intervention.
    """

    version = "1.0.0"

    def on_load(self):
        """Logs a message when the plugin is loaded."""
        self.logger.info(
            "Plugin loaded. Will send reload commands after config changes if server is running."
        )

    def _is_server_running(self, server_name: str) -> bool:
        """Checks if a server is currently running via the API."""
        try:
            response = self.api.get_server_running_status(server_name=server_name)
            if response and response.get("status") == "success":
                return response.get("is_running", False)

            self.logger.warning(
                f"Could not determine running status for '{server_name}'. API response: {response}"
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

    def _send_reload_command(self, server_name: str, command: str, context: str):
        """Sends a given command to a server if it's running."""
        if self._is_server_running(server_name):
            try:
                self.logger.info(
                    f"{context.capitalize()} changed for '{server_name}', triggering reload."
                )
                self.api.send_command(server_name=server_name, command=command)
                self.logger.info(f"Successfully sent '{command}' to '{server_name}'.")
            except Exception as e:
                self.logger.warning(
                    f"Failed to send '{command}' to '{server_name}': {e}", exc_info=True
                )
        else:
            self.logger.info(
                f"Server '{server_name}' is not running, skipping reload after {context} change."
            )

    def after_allowlist_change(self, server_name: str, result: dict):
        """Triggers an `allowlist reload` if the allowlist was successfully modified."""
        self.logger.debug(f"Handling after_allowlist_change for '{server_name}'.")

        if result.get("status") == "success":
            # Check if any players were actually added or removed to avoid unnecessary reloads.
            added_count = result.get("added_count", 0)
            removed_players = result.get("details", {}).get("removed", [])

            if added_count > 0 or len(removed_players) > 0:
                self._send_reload_command(server_name, "allowlist reload", "allowlist")
            else:
                self.logger.info(
                    f"Allowlist operation for '{server_name}' reported no changes, skipping reload."
                )
        else:
            self.logger.debug(
                f"Allowlist change for '{server_name}' was not successful, skipping reload."
            )

    def after_permission_change(self, server_name: str, xuid: str, result: dict):
        """Triggers a `permission reload` if permissions were successfully modified."""
        self.logger.debug(f"Handling after_permission_change for '{server_name}'.")

        if result.get("status") == "success":
            self._send_reload_command(server_name, "permission reload", "permission")
        else:
            self.logger.debug(
                f"Permission change for '{server_name}' was not successful, skipping reload."
            )

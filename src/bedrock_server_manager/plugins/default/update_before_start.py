# bedrock_server_manager/plugins/default/update_before_start.py
"""
Plugin that automatically updates a Bedrock server to the latest version.
"""
from bedrock_server_manager import PluginBase
from bedrock_server_manager import BedrockServer
from bedrock_server_manager.error import BSMError


class AutoupdatePlugin(PluginBase):
    """
    Automatically updates a server to the latest version before it starts.
    This plugin checks for a server-specific `autoupdate: true` setting in its
    configuration. If enabled, it triggers the update process before launch.
    """

    version = "1.0.1"

    def on_load(self):
        """Logs a message when the plugin is loaded."""
        self.logger.info(
            "Plugin loaded. Will check for updates before server starts if enabled."
        )

    def before_server_start(self, server_name: str, mode: str):
        """
        Checks for the 'autoupdate' flag before a server starts and runs
        the update process if it's enabled.
        """
        self.logger.debug(
            f"Handling before_server_start for '{server_name}' (mode: {mode})"
        )

        try:
            # Create an instance for the server to access its configuration.
            server_instance = BedrockServer(server_name)
            autoupdate_enabled = server_instance.get_autoupdate()

            if not autoupdate_enabled:
                self.logger.info(
                    f"Autoupdate is disabled for '{server_name}'. Skipping check."
                )
                return

            self.logger.info(
                f"Autoupdate enabled for '{server_name}'. Checking for updates..."
            )

            # Call the main API to perform the update.
            update_result = self.api.update_server(
                server_name=server_name, send_message=False
            )

            if update_result.get("status") == "success":
                if update_result.get("updated", False):
                    new_version = update_result.get("new_version", "N/A")
                    self.logger.info(
                        f"Autoupdate successful for '{server_name}'. New version: {new_version}"
                    )
                else:
                    self.logger.info(
                        f"Autoupdate check for '{server_name}': Server is already up-to-date."
                    )
            else:
                # Log the failure but allow the server to attempt to start with its current version.
                error_message = update_result.get("message", "Unknown error")
                self.logger.error(
                    f"Autoupdate process failed for '{server_name}': {error_message}. Server will start with current version."
                )

        except BSMError as e:
            # Error accessing server config (e.g., file not found).
            self.logger.error(
                f"Error accessing server config for '{server_name}': {e}. Server start will continue."
            )
        except Exception as e:
            # Catch any other unexpected errors to prevent them from stopping the server start process.
            self.logger.error(
                f"An unexpected error occurred during autoupdate for '{server_name}': {e}. Server start will continue.",
                exc_info=True,
            )

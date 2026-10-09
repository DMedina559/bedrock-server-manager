# bedrock_server_manager/plugins/default/update_before_start.py
"""
Plugin that automatically updates a Bedrock server to the latest version.
"""

from typing import Any

from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.error import BSMError

from ...logging import log_operation_error


class AutoupdatePlugin(PluginBase):
    """
    Automatically updates a server to the latest version before it starts.
    This plugin checks for a server-specific `autoupdate: true` setting in its
    configuration. If enabled, it triggers the update process before launch.
    """

    version = "1.2.0"
    description = "Automatically updates a server to the latest version before it starts. This plugin checks for a server-specific `autoupdate: true` setting in its configuration."
    author = "dmedina559"
    name = "Auto Update on Start"

    @app_event("on_load")
    async def plugin_loaded(self):
        """Logs a message when the plugin is loaded."""
        self.logger.debug(
            "Plugin loaded. Will check for updates before server starts if enabled."
        )

    @app_event("before_server_start")
    async def update_before_start(self, **kwargs: Any):
        """
        Checks for the 'autoupdate' flag before a server starts and runs
        the update process if it's enabled.
        """
        server_name = str(kwargs.get("server_name"))
        if not server_name or server_name == "None":
            return

        self.logger.debug("Handling before_server_start for '%s'.", server_name)

        try:
            # Check if the server has autoupdate enabled in its settings
            result = await self.api.server.get_setting(
                request={"server_name": server_name, "key": "settings.autoupdate"}
            )
            autoupdate_enabled = result.value if result.status == "success" else False

            if not autoupdate_enabled:
                self.logger.debug(
                    "Autoupdate is disabled for '%s'. Skipping check.", server_name
                )
                return

            self.logger.debug(
                "Autoupdate enabled for '%s'. Checking for updates...", server_name
            )

            # Call the main API to perform the update. We run it in a thread so it doesn't block the async loop.
            update_result = await self.api.install.update_server(
                request={"server_name": server_name, "send_message": False}
            )

            if update_result.status == "success":
                if update_result.updated:
                    new_version = update_result.new_version
                    self.logger.info(
                        "Autoupdate successful for '%s'. New version: %s",
                        server_name,
                        new_version,
                    )
                else:
                    self.logger.debug(
                        "Autoupdate check for '%s': Server is already up-to-date.",
                        server_name,
                    )
            else:
                # Log the failure but allow the server to attempt to start with its current version.
                error_message = update_result.message
                self.logger.error(
                    "Autoupdate process failed for '%s': %s. Server will start with current version.",
                    server_name,
                    error_message,
                )

        except BSMError as e:
            # Error accessing server config (e.g., file not found).
            log_operation_error(
                self.logger,
                "Error accessing server config for '%s': %s. Server start will continue.",
                server_name,
                e,
                error=e,
            )
        except Exception as e:
            # Catch any other unexpected errors to prevent them from stopping the server start process.
            log_operation_error(
                self.logger,
                "An unexpected error occurred during autoupdate for '%s': %s. Server start will continue.",
                server_name,
                e,
                error=e,
            )

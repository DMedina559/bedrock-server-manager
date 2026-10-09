# bedrock_server_manager/plugins/default/world_operation_notifications.py
"""
Plugin to send in-game notifications before world operations like export, import, or reset.
"""

from typing import Any

from bedrock_server_manager import PluginBase, app_event

from ...logging import log_operation_error


class WorldOperationNotificationsPlugin(PluginBase):
    """
    Notifies in-game players before significant world operations (export, import, reset)
    are performed on a running server, providing a heads-up for potential disruptions.
    """

    version = "1.2.0"
    description = "Notifies in-game players before significant world operations (export, import, reset) are performe..."
    author = "dmedina559"

    @app_event("on_load")
    async def plugin_loaded(self):
        """Logs a message when the plugin is loaded."""
        self.logger.debug(
            "Plugin loaded. Will send notifications for world operations."
        )

    async def _is_server_running(self, server_name: str) -> bool:
        """Checks if a server is currently running via the API."""
        try:
            response = await self.api.system.get_server_running_status(
                request={"server_name": server_name}
            )
            if response and response.status == "success":
                return bool(response.is_running)
            self.logger.warning(
                "Could not determine running status for '%s'.",
                server_name,
            )
        except AttributeError:
            self.logger.error(
                "API is missing 'get_server_running_status'. Cannot check server status."
            )
        except Exception as e:
            log_operation_error(
                self.logger,
                "Error checking server status for '%s': %s",
                server_name,
                e,
                error=e,
            )
        return False

    async def _send_ingame_warning(self, server_name: str, message: str, context: str):
        """Helper to send an in-game "say" command if the server is running."""
        if await self._is_server_running(server_name):
            try:
                # Ensure the message is formatted as a "say" command.
                if not message.lower().startswith("say "):
                    command = f"say {message}"
                else:
                    command = message

                await self.api.server.send_command(
                    request={"server_name": server_name, "command": command}
                )
                self.logger.debug(
                    "Sent %s warning to '%s': %s", context, server_name, message
                )
            except Exception as e:
                log_operation_error(
                    self.logger,
                    "Failed to send %s warning to '%s': %s",
                    context,
                    server_name,
                    e,
                    error=e,
                )
        else:
            self.logger.debug(
                "Server '%s' not running, skipping %s warning.", server_name, context
            )

    @app_event("before_world_export")
    async def send_export_warning(self, **kwargs: Any):
        """Notifies players before a world export begins."""

        server_name = str(kwargs.get("server_name"))
        export_dir = kwargs.get("export_dir")
        self.logger.debug(
            "Handling before_world_export for '%s' to '%s'.", server_name, export_dir
        )
        summary = await self.api.server.get_summary(
            request={"server_name": server_name}
        )
        player_count = (
            summary.summary.player_count if summary.status == "success" else 0
        )
        if player_count > 0:
            await self._send_ingame_warning(
                server_name,
                "World export starting...",
                "world export",
            )

    @app_event("before_world_import")
    async def send_import_warning(self, **kwargs: Any):
        """Notifies players before a world import begins."""

        server_name = str(kwargs.get("server_name"))
        file_path = kwargs.get("file_path")
        self.logger.debug(
            "Handling before_world_import for '%s' from '%s'.", server_name, file_path
        )
        summary = await self.api.server.get_summary(
            request={"server_name": server_name}
        )
        player_count = (
            summary.summary.player_count if summary.status == "success" else 0
        )
        if player_count > 0:
            await self._send_ingame_warning(
                server_name,
                "World import starting... Current world will be replaced.",
                "world import",
            )

    @app_event("before_world_reset")
    async def send_reset_warning(self, **kwargs: Any):
        """Sends a critical warning before a world reset operation."""

        server_name = str(kwargs.get("server_name"))
        self.logger.debug("Handling before_world_reset for '%s'.", server_name)
        self.logger.debug(
            "Critical operation: World reset initiated for server '%s'.", server_name
        )
        summary = await self.api.server.get_summary(
            request={"server_name": server_name}
        )
        player_count = (
            summary.summary.player_count if summary.status == "success" else 0
        )
        if player_count > 0:
            await self._send_ingame_warning(
                server_name,
                "CRITICAL WARNING: Server world is being reset NOW!",
                "world reset",
            )

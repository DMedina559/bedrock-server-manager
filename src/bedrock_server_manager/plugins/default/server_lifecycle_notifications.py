# bedrock_server_manager/plugins/default/server_lifecycle_notifications.py
"""
Plugin to send in-game messages and manage delays during server lifecycle events.
"""

import asyncio
from typing import Any

from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.logging import log_operation_error


class ServerLifecycleNotificationsPlugin(PluginBase):
    """
    Enhances server management by sending in-game notifications and introducing
    delays at critical server lifecycle points (e.g., stop, start, update, delete).
    This gives players warnings and can help ensure smoother transitions.
    """

    version = "1.2.0"
    description = "Enhances server management by sending in-game notifications and introducing delays at critical server lifecycle points."
    author = "dmedina559"
    name = "Server Lifecycle Notifications"

    @app_event("on_load")
    async def plugin_loaded(self) -> None:
        """Initializes default delays and logs plugin activation."""
        # Default delays in seconds. These could be made configurable in the future.
        self.stop_warning_delay: int = 3
        self.post_stop_settle_delay: int = 1
        self.post_start_settle_delay: int = 1

        self.logger.debug(
            "Plugin loaded. Will manage server lifecycle notifications and delays."
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

    async def _send_ingame_message(
        self, server_name: str, message: str, context: str
    ) -> None:
        """Helper to send an in-game message if the server is running."""
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
                    "Sent %s message to '%s': %s", context, server_name, message
                )
            except Exception as e:
                log_operation_error(
                    self.logger,
                    "Failed to send %s message to '%s': %s",
                    context,
                    server_name,
                    e,
                    error=e,
                )
        else:
            self.logger.debug(
                "Server '%s' not running, skipping %s message.", server_name, context
            )

    @app_event("before_server_stop")
    async def send_shutdown_warning(self, **kwargs: Any) -> None:
        """Sends a shutdown warning and waits before the server stops."""
        server_name = str(kwargs.get("server_name"))
        self.logger.debug("Handling before_server_stop for '%s'.", server_name)

        summary = await self.api.server.get_summary(
            request={"server_name": server_name}
        )
        player_count = (
            summary.summary.player_count if summary.status == "success" else 0
        )
        if player_count > 0:

            # Run the check in a separate thread so it doesn't block the loop
            is_running = await self._is_server_running(server_name)
            if is_running:
                warning_message = (
                    f"Server is stopping in {self.stop_warning_delay} seconds..."
                )
                await self._send_ingame_message(
                    server_name, warning_message, "shutdown warning"
                )

                self.logger.debug(
                    "Waiting %ss before '%s' stops.",
                    self.stop_warning_delay,
                    server_name,
                )
                await asyncio.sleep(self.stop_warning_delay)

    @app_event("after_server_stop")
    async def wait_after_stop(self, **kwargs: Any) -> None:
        """Waits for a short period after a server stops, e.g., for port release."""

        server_name = kwargs.get("server_name")
        result = kwargs.get("result")
        self.logger.debug("Handling after_server_stop for '%s'.", server_name)
        if getattr(result, "status", None) == "success":
            self.logger.debug(
                "Waiting %ss after '%s' stopped.",
                self.post_stop_settle_delay,
                server_name,
            )
            await asyncio.sleep(self.post_stop_settle_delay)

    @app_event("before_delete_server_data")
    async def send_delete_warning(self, **kwargs: Any) -> None:
        """Sends a final warning before server data is deleted if the server is running."""

        server_name = str(kwargs.get("server_name"))
        self.logger.debug("Handling before_delete_server_data for '%s'.", server_name)

        summary = await self.api.server.get_summary(
            request={"server_name": server_name}
        )
        player_count = (
            summary.summary.player_count if summary.status == "success" else 0
        )
        if player_count > 0:
            await self._send_ingame_message(
                server_name,
                "WARNING: Server data is being deleted permanently!",
                "data deletion warning",
            )

    @app_event("before_server_update")
    async def send_update_notification(self, **kwargs: Any) -> None:
        """Notifies players before a server update begins."""

        server_name = str(kwargs.get("server_name"))
        target_version = kwargs.get("target_version")
        self.logger.debug(
            "Handling before_server_update for '%s' to v%s.",
            server_name,
            target_version,
        )

        summary = await self.api.server.get_summary(
            request={"server_name": server_name}
        )
        player_count = (
            summary.summary.player_count if summary.status == "success" else 0
        )
        if player_count > 0:
            await self._send_ingame_message(
                server_name,
                "Server is updating now, please wait...",
                "update notification",
            )

    @app_event("after_server_start")
    async def wait_after_start(self, **kwargs: Any) -> None:
        """Waits for a short period after a server starts to allow initialization."""

        server_name = kwargs.get("server_name")
        result = kwargs.get("result")
        self.logger.debug("Handling after_server_start for '%s'.", server_name)
        if getattr(result, "status", None) == "success":
            self.logger.debug(
                "Waiting %ss after '%s' started.",
                self.post_start_settle_delay,
                server_name,
            )
            await asyncio.sleep(self.post_start_settle_delay)

# bedrock_server_manager/plugins/default/auto_reload_config.py
"""
Plugin that automatically reloads server configurations after changes.
"""

from typing import Any

from bedrock_server_manager import PluginBase, app_event
from bedrock_server_manager.api.models.allowlist import (
    AddToAllowlistResponse,
    RemoveFromAllowlistResponse,
)
from bedrock_server_manager.logging import log_operation_error


class AutoReloadPlugin(PluginBase):
    """
    Automatically sends a `reload` command to a running server after its
    configuration files (e.g., allowlist.json, permissions.json) are modified,
    ensuring changes take effect immediately without manual intervention.
    """

    version = "1.2.0"
    description = "Automatically sends a `reload` command to a running server after its configuration files (e.g., allowlist.json, permissions.json) are modified."
    author = "dmedina559"
    name = "Auto Reload Config"

    @app_event("on_load")
    async def plugin_loaded(self):
        """Logs a message when the plugin is loaded."""
        self.logger.debug(
            "Plugin loaded. Will send reload commands after config changes if server is running."
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

    async def _send_reload_command(self, server_name: str, command: str, context: str):
        """Sends a given command to a server if it's running."""
        if not await self.get_plugin_setting("enable_auto_reload", default=True):
            self.logger.debug("Auto reload is disabled in plugin settings.")
            return
        if await self._is_server_running(server_name):
            try:
                self.logger.info(
                    "%s changed for '%s', triggering reload.",
                    context.capitalize(),
                    server_name,
                )
                await self.api.server.send_command(
                    request={"server_name": server_name, "command": command}
                )
                self.logger.debug(
                    "Reload command delivered to server '%s'.", server_name
                )
            except Exception as e:
                self.logger.warning(
                    "Could not reload configuration for server '%s': %s",
                    server_name,
                    e,
                    exc_info=True,
                )
        else:
            self.logger.debug(
                "Server '%s' is not running, skipping reload after %s change.",
                server_name,
                context,
            )

    @app_event("after_allowlist_change")
    async def send_allowlist_reload_command(self, **kwargs: Any):
        """Triggers an `allowlist reload` if the allowlist was successfully modified."""

        server_name = str(kwargs.get("server_name"))
        result = kwargs.get("result")
        self.logger.debug("Handling after_allowlist_change for '%s'.", server_name)

        if getattr(result, "status", None) == "success":
            # Check if any players were actually added or removed to avoid unnecessary reloads.
            added_count = (
                result.added_count if isinstance(result, AddToAllowlistResponse) else 0
            )
            removed_players = (
                result.details.removed
                if isinstance(result, RemoveFromAllowlistResponse)
                else []
            )

            if added_count > 0 or len(removed_players) > 0:
                await self._send_reload_command(
                    server_name,
                    "allowlist reload",
                    "allowlist",
                )
            else:
                self.logger.debug(
                    "Allowlist operation for '%s' reported no changes, skipping reload.",
                    server_name,
                )
        else:
            self.logger.debug(
                "Allowlist change for '%s' was not successful, skipping reload.",
                server_name,
            )

    @app_event("after_permission_change")
    async def send_permission_reload_command(self, **kwargs: Any):
        """Triggers a `permission reload` if permissions were successfully modified."""

        server_name = str(kwargs.get("server_name"))
        result = kwargs.get("result")
        self.logger.debug("Handling after_permission_change for '%s'.", server_name)

        if getattr(result, "status", None) == "success":
            await self._send_reload_command(
                server_name,
                "permission reload",
                "permission",
            )
        else:
            self.logger.debug(
                "Permission change for '%s' was not successful, skipping reload.",
                server_name,
            )

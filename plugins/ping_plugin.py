# <PLUGIN_DIR>/ping_plugin.py
"""
Example plugin: PingPlugin - Demonstrates sending custom plugin events.

This plugin sends a custom event, 'pingplugin:ping', when a specific
application event occurs (e.g., after a server successfully starts).
It's designed to work in conjunction with PongPlugin, which listens for this event.
"""

import time
from typing import Any, Dict

from bedrock_server_manager import PluginBase, app_event


class PingPlugin(PluginBase):
    """
    A plugin that demonstrates how to send custom events to other plugins.
    It sends a 'pingplugin:ping' event after a server successfully starts.
    """

    version = "1.2.0"
    author = "dmedina559"
    description = "A plugin that demonstrates how to send custom events to other plugins. It sends a 'pingplugin:ping' event after a server successfully starts."
    name = "Ping Test"

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs):
        """
        Called by the PluginManager when this plugin is loaded.
        """
        self.logger.debug(
            "'%s' v%s loaded. Will send 'pingplugin:ping' events after successful server starts.",
            self.name,
            self.version,
        )

    @app_event("after_server_start")
    async def send_ping_event(self, **kwargs: Any):
        """
        An application event hook, called by the PluginManager after a server
        start attempt.

        If the server start was successful, this plugin will construct and send
        a custom 'pingplugin:ping' event.

        Args:
            server_name (str): The name of the server that was started.
            result (dict): A dictionary containing the outcome of the start operation.
                           Expected to have a "status" key (e.g., "success").
        """
        server_name = str(kwargs.get("server_name"))
        result: Dict[str, Any] = kwargs.get("result", {})

        self.logger.debug(
            "'%s' received 'after_server_start' event for server '%s'. Result: %s",
            self.name,
            server_name,
            result.get("status"),
        )

        if result.get("status") == "success":
            self.logger.debug(
                "Server '%s' started successfully. '%s' is preparing to send a 'pingplugin:ping' event.",
                server_name,
                self.name,
            )

            # Prepare the payload for the custom event.
            # It's good practice to use a dictionary for structured data.
            ping_payload_data = {
                "message": f"Ping from {self.name} regarding server {server_name}!",
                "timestamp": time.time(),
                "details": "Server is now active.",
            }

            # Use self.api.send_event() to trigger a custom event.
            # The first argument is the event name (string).
            # Subsequent arguments can be positional (*args) or keyword (**kwargs).
            # Keyword arguments are often more descriptive for event payloads.
            # The event name "pingplugin:ping" suggests this event originates from
            # "pingplugin" and is about a "ping".
            await self.api.send_event(
                "pingplugin:ping",  # Event name
                server_name=server_name,  # Example of a top-level kwarg
                data=ping_payload_data,  # Example of a nested dictionary as a kwarg
            )

            self.logger.debug(
                "'%s' successfully sent 'pingplugin:ping' event for server '%s'",
                self.name,
                server_name,
            )
        else:
            self.logger.debug(
                "Server '%s' did not start successfully (status: %s). '%s' will not send a ping event.",
                server_name,
                result.get("status"),
                self.name,
            )

    @app_event("on_unload")
    async def plugin_unloaded(self, **kwargs):
        """
        Called by the PluginManager when this plugin is being unloaded.
        """
        self.logger.debug("'%s' v%s is unloading.", self.name, self.version)

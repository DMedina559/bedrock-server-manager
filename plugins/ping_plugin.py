# <PLUGIN_DIR>/ping_plugin.py
"""
Example plugin: PingPlugin - Demonstrates sending custom plugin events.

This plugin sends a custom event, 'pingplugin:ping', when a specific
application event occurs (e.g., after a server successfully starts).
It's designed to work in conjunction with PongPlugin, which listens for this event.
"""
import time
from bedrock_server_manager import PluginBase


class PingPlugin(PluginBase):
    """
    A plugin that demonstrates how to send custom events to other plugins.
    It sends a 'pingplugin:ping' event after a server successfully starts.
    """

    version = "1.1.0"

    def on_load(self):
        """
        Called by the PluginManager when this plugin is loaded.
        """
        self.logger.info(
            f"'{self.name}' v{self.version} loaded. Will send 'pingplugin:ping' events after successful server starts."
        )

    def after_server_start(self, **kwargs: any):
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
        server_name = kwargs.get("server_name")
        result = kwargs.get("result", {})

        self.logger.debug(
            f"'{self.name}' received 'after_server_start' event for server '{server_name}'. Result: {result.get('status')}"
        )

        if result.get("status") == "success":
            self.logger.info(
                f"Server '{server_name}' started successfully. '{self.name}' is preparing to send a 'pingplugin:ping' event."
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
            self.api.send_event(
                "pingplugin:ping",  # Event name
                server_name=server_name,  # Example of a top-level kwarg
                data=ping_payload_data,  # Example of a nested dictionary as a kwarg
            )

            self.logger.info(
                f"'{self.name}' successfully sent 'pingplugin:ping' event for server '{server_name}' with payload: {ping_payload_data}"
            )
        else:
            self.logger.info(
                f"Server '{server_name}' did not start successfully (status: {result.get('status')}). "
                f"'{self.name}' will not send a ping event."
            )

    def on_unload(self):
        """
        Called by the PluginManager when this plugin is being unloaded.
        """
        self.logger.info(f"'{self.name}' v{self.version} is unloading.")

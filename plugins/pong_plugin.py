# <PLUGIN_DIR>/pong_plugin.py
"""
Example plugin: PongPlugin - Demonstrates listening for custom plugin events.

This plugin listens for a specific custom event, 'pingplugin:ping', and logs
the data it receives. It's designed to work in conjunction with PingPlugin,
which sends this event.
"""
from bedrock_server_manager import PluginBase


class PongPlugin(PluginBase):
    """
    A plugin that demonstrates how to listen for and handle custom events
    sent by other plugins. It specifically listens for 'pingplugin:ping'.
    """

    version = "1.1.0"

    def on_load(self):
        """
        Called by the PluginManager when this plugin is loaded.

        This method is the ideal place to register listeners for any custom events
        this plugin is interested in.
        """
        self.logger.info(
            f"'{self.name}' v{self.version} loaded. Registering listener for 'pingplugin:ping' event."
        )
        # Use self.api.listen_for_event() to subscribe to a custom event.
        # The first argument is the event name (string).
        # The second argument is the callback method that will be invoked when the event occurs.
        # It's good practice to namespace event names, e.g., "source_plugin_name:event_description".
        self.api.listen_for_event("pingplugin:ping", self.handle_ping_event)

    def handle_ping_event(self, *args, **kwargs):
        """
        Callback method for the 'pingplugin:ping' custom event.

        This method is executed whenever the 'pingplugin:ping' event is triggered
        by any plugin (e.g., PingPlugin).

        It receives any positional (*args) and keyword (**kwargs) arguments
        that were passed when the event was sent.

        Additionally, the PluginManager automatically injects a `_triggering_plugin`
        keyword argument, which contains the name of the plugin that sent the event.
        """
        # It's good practice to extract _triggering_plugin first.
        # The .pop() method retrieves it and removes it from kwargs,
        # so it doesn't interfere with your expected payload.
        triggering_plugin_name = kwargs.pop("_triggering_plugin", "UnknownPlugin")

        self.logger.info(
            f"'{self.name}' received 'pingplugin:ping' event from plugin: '{triggering_plugin_name}'."
        )

        # Log all received arguments for demonstration purposes.
        if args:
            self.logger.info(f"  Received positional arguments: {args}")
        if kwargs:  # kwargs will now not include _triggering_plugin
            self.logger.info(f"  Received keyword arguments (payload): {kwargs}")
        else:
            self.logger.info("  No additional keyword arguments (payload) received.")

        # Example of how to safely access specific data from the event payload (kwargs).
        # This assumes PingPlugin sends 'server_name' and a 'data' dictionary.
        server_name = kwargs.get("server_name", "N/A")  # Use .get() for safe access
        ping_data_payload = kwargs.get(
            "data", {}
        )  # Default to empty dict if 'data' is missing

        message = ping_data_payload.get("message", "No message content")
        timestamp = ping_data_payload.get("timestamp", 0)

        self.logger.info(
            f"  Parsed data from event: Server='{server_name}', Message='{message}', Timestamp='{timestamp}'"
        )
        # Add any further processing of the event data here.

    def on_unload(self):
        """
        Called by the PluginManager when this plugin is being unloaded
        (e.g., during a reload or application shutdown).

        For custom event listeners registered via `self.api.listen_for_event()`,
        explicit unregistration in `on_unload` is generally not required because
        the PluginManager clears all custom event listeners when plugins are reloaded.
        However, if a plugin manages resources that need specific cleanup related to
        its event handling, this would be the place to do it.
        """
        self.logger.info(f"'{self.name}' v{self.version} is unloading.")

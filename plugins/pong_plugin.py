# <PLUGIN_DIR>/pong_plugin.py
"""
Example plugin: PongPlugin - Demonstrates listening for custom plugin events.

This plugin listens for a specific custom event, 'pingplugin:ping', and logs
receipt without logging the event payload. It's designed to work in conjunction with PingPlugin,
which sends this event.
"""

from bedrock_server_manager import PluginBase
from bedrock_server_manager.plugins import app_event


class PongPlugin(PluginBase):
    """
    A plugin that demonstrates how to listen for and handle custom events
    sent by other plugins. It specifically listens for 'pingplugin:ping'.
    """

    version = "1.2.0"
    author = "dmedina559"
    description = "A plugin that demonstrates how to listen for and handle custom events sent by other plugins. It specifically listens for 'pingplugin:ping'."
    name = "Pong Test"

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs):
        """
        Called by the PluginManager when this plugin is loaded.

        This method is the ideal place to register listeners for any custom events
        this plugin is interested in.
        """
        self.logger.debug(
            "'%s' v%s loaded. Registering listener for 'pingplugin:ping' event.",
            self.name,
            self.version,
        )

    @app_event("pingplugin:ping")
    async def handle_ping_event(self, *args, **kwargs):
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

        self.logger.debug(
            "Received 'pingplugin:ping' from '%s' for server '%s' (%s positional arguments, %s keyword arguments).",
            triggering_plugin_name,
            kwargs.get("server_name", "N/A"),
            len(args),
            len(kwargs),
        )

    @app_event("on_unload")
    async def plugin_unloaded(self, **kwargs):
        """
        Called by the PluginManager when this plugin is being unloaded
        (e.g., during a reload or application shutdown).

        For custom event listeners registered via `self.api.listen_for_event()`,
        explicit unregistration in `on_unload` is generally not required because
        the PluginManager clears all custom event listeners when plugins are reloaded.
        However, if a plugin manages resources that need specific cleanup related to
        its event handling, this would be the place to do it.
        """
        self.logger.debug("'%s' v%s is unloading.", self.name, self.version)

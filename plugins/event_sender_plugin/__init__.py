# <PLUGIN_DIR>/plugins/event_sender_plugin/__init__.py
"""
Plugin to provide a web UI for sending custom plugin events.
"""

from fastapi import APIRouter

from bedrock_server_manager import PluginBase, app_event

from .routes import define_routes


class EventSenderPlugin(PluginBase):
    version = "1.4.0"
    permissions = []
    author = "dmedina559"
    name = "Event Sender"
    description = "A plugin that provides a web UI for sending custom plugin events."

    http_permissions = [
        ("manage", "Manage event sender and dispatch events", ["admin"]),
    ]

    @app_event("on_load")
    async def plugin_loaded(self):
        self.logger.debug(
            "Plugin '%s' v%s loaded. Event sender page available at /event_sender/ui",
            self.name,
            self.version,
        )

        self.router = APIRouter(
            prefix="/event_sender",
            tags=["Event Sender Plugin"],
        )
        define_routes(self.router, self)
        self.logger.debug("EventSenderPlugin v%s initialized.", self.version)

    @app_event("on_unload")
    async def plugin_unloaded(self):
        self.logger.debug("Plugin '%s' v%s unloaded.", self.name, self.version)

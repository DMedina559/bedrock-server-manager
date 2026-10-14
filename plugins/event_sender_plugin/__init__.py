# <PLUGIN_DIR>/plugins/event_sender_plugin/__init__.py
"""
Plugin to provide a web UI for sending custom plugin events.
"""

from fastapi import APIRouter

from bedrock_server_manager import PluginBase, app_event

from .routes import define_routes


class EventSenderPlugin(PluginBase):
    version = "1.3.0"
    author = "dmedina559"
    description = "A plugin that provides a web UI for sending custom plugin events."
    name = "Event Sender"

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

    def get_fastapi_routers(self):
        self.logger.debug("Providing FastAPI router for %s", self.name)
        return [self.router]

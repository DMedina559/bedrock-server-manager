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
    def plugin_loaded(self):
        self.logger.info(
            f"Plugin '{self.name}' v{self.version} loaded. Event sender page available at /event_sender/ui"
        )

        self.router = APIRouter(
            prefix="/event_sender",
            tags=["Event Sender Plugin"],
        )
        define_routes(self.router, self)
        self.logger.info(f"EventSenderPlugin v{self.version} initialized.")

    @app_event("on_unload")
    def plugin_unloaded(self):
        self.logger.info(f"Plugin '{self.name}' v{self.version} unloaded.")

    def get_fastapi_routers(self):
        self.logger.debug(f"Providing FastAPI router for {self.name}")
        return [self.router]

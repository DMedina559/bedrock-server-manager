# <PLUGIN_DIR>/plugins/event_sender_plugin/__init__.py
"""
Plugin to provide a web UI for sending custom plugin events.
"""

from fastapi import APIRouter

from bedrock_server_manager import PluginBase

from .routes import define_routes


class EventSenderPlugin(PluginBase):
    version = "1.2.0"

    def on_load(self):
        self.logger.info(
            f"Plugin '{self.name}' v{self.version} loaded. Event sender page available at /event_sender/ui"
        )

        self.router = APIRouter(
            prefix="/event_sender",
            tags=["Event Sender Plugin"],  # Tag for OpenAPI documentation
        )
        define_routes(self.router, self)
        self.logger.info(f"EventSenderPlugin v{self.version} initialized.")

    def on_unload(self):
        self.logger.info(f"Plugin '{self.name}' v{self.version} unloaded.")

    def get_fastapi_routers(self):
        self.logger.debug(f"Providing FastAPI router for {self.name}")
        return [self.router]

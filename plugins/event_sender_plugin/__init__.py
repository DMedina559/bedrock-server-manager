# <PLUGIN_DIR>/plugins/event_sender_plugin/__init__.py
"""
Plugin to provide a web UI for sending custom plugin events.
"""

from fastapi import APIRouter

from bedrock_server_manager import PluginBase


class EventSenderPlugin(PluginBase):
    version = "1.1.1"

    def on_load(self):
        self.logger.info(
            f"Plugin '{self.name}' v{self.version} loaded. Event sender page available at /event_sender/page"
        )

        self.router = APIRouter(
            tags=["Event Sender Plugin"]  # Tag for OpenAPI documentation
        )
        self._define_routes()
        self.logger.info(f"EventSenderPlugin v{self.version} initialized.")

    def on_unload(self):
        self.logger.info(f"Plugin '{self.name}' v{self.version} unloaded.")

    def get_fastapi_routers(self):
        self.logger.debug(f"Providing FastAPI router for {self.name}")
        return [self.router]

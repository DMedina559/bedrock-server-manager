# <PLUGIN_DIR>/lifecycle_test_plugin.py
from typing import Any, Dict

from bedrock_server_manager import PluginBase, app_event


class LifecycleTestPlugin(PluginBase):
    version = "1.1.0"
    author = "dmedina559"
    description = "A custom Bedrock Server Manager plugin."
    name = "Lifecycle Test"

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs):
        self.logger.debug("Lifecycle Test Plugin loaded.")

    @app_event("after_server_start")
    async def run_lifecycle_test(self, **kwargs: Any):

        server_name = str(kwargs.get("server_name"))
        result: Dict[str, Any] = kwargs.get("result", {})
        if result.get("status") == "success":
            self.logger.debug(
                "Server '%s' started. Now testing lifecycle manager.", server_name
            )

            try:
                async with self.api.runtime.server_lifecycle_manager(
                    server_name, stop_before=True, start_after=True
                ):
                    self.logger.debug(
                        "Inside the lifecycle manager's 'async with' block. Server should be stopped now."
                    )
                    self.logger.debug(
                        "Finished work inside the 'async with' block. Server should restart shortly."
                    )

                self.logger.debug("Lifecycle manager test completed successfully.")
            except Exception as e:
                self.logger.error(
                    "An error occurred during the lifecycle manager test: %s",
                    e,
                    exc_info=True,
                )

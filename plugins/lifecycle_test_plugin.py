# <PLUGIN_DIR>/lifecycle_test_plugin.py
import asyncio
from typing import Any, Dict

from bedrock_server_manager import PluginBase, app_event


class LifecycleTestPlugin(PluginBase):
    version = "1.1.0"
    author = "dmedina559"
    description = "A custom Bedrock Server Manager plugin."
    name = "Lifecycle Test"

    @app_event("on_load")
    def plugin_loaded(self, **kwargs):
        self.logger.info("Lifecycle Test Plugin loaded.")

    @app_event("after_server_start")
    async def run_lifecycle_test(self, **kwargs: Any):

        server_name = str(kwargs.get("server_name"))
        result: Dict[str, Any] = kwargs.get("result", {})
        if result.get("status") == "success":
            self.logger.info(
                f"Server '{server_name}' started. Now testing lifecycle manager."
            )

            def lifecycle_task():
                try:
                    with self.api.server_lifecycle_manager(
                        server_name, stop_before=True, start_after=True
                    ):
                        self.logger.info(
                            "Inside the lifecycle manager's 'with' block. Server should be stopped now."
                        )
                        self.logger.info(
                            "Finished work inside the 'with' block. Server should restart shortly."
                        )

                    self.logger.info("Lifecycle manager test completed successfully.")
                except Exception as e:
                    self.logger.error(
                        f"An error occurred during the lifecycle manager test: {e}",
                        exc_info=True,
                    )

            await asyncio.to_thread(lifecycle_task)

# <PLUGIN_DIR>/lifecycle_test_plugin.py
from bedrock_server_manager import PluginBase
from typing import Any
import time


class LifecycleTestPlugin(PluginBase):
    version = "1.0.0"

    def on_load(self, **kwargs):
        self.logger.info("Lifecycle Test Plugin loaded.")

    def after_server_start(self, **kwargs: Any):
        server_name = kwargs.get("server_name")
        result = kwargs.get("result")
        if result.get("status") == "success":
            self.logger.info(
                f"Server '{server_name}' started. Now testing lifecycle manager."
            )

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

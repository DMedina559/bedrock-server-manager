# <PLUGIN_DIR>/nested_seperate_server_test.py
"""Demonstrate nested start hooks for different servers without suppressing valid work."""

from typing import Any

from bedrock_server_manager import PluginBase, app_event

# --- Configuration for the test ---
# These should be names of actual, configured servers in your BSM setup.
# SERVER_A_NAME should be the one you manually start to trigger the test.
# SERVER_B_NAME is the one that will be started by the plugin.
SERVER_A_NAME_TRIGGER = "test"  # The server you will manually start.
SERVER_B_NAME_NESTED = "test_2"  # A DIFFERENT server to be started by the plugin.
# Ensure SERVER_A_NAME_TRIGGER != SERVER_B_NAME_NESTED for this test.

# To prevent this test plugin from infinitely trying to start SERVER_B_NAME
# if this handler is called for SERVER_B_NAME itself due to some other interaction,
# or if SERVER_A_NAME_TRIGGER and SERVER_B_NAME_NESTED were accidentally the same.
_server_b_triggered_by_this_plugin = False


class NestedDifferentServerStartPlugin(PluginBase):
    """
    Tests that the granular re-entrancy guard allows nested event dispatches
    for the same event type but different identifying parameters (e.g., different server names).
    """

    version = "1.2.0"
    author = "dmedina559"
    description = "Tests that the granular re-entrancy guard allows nested event dispatches for the same event type but different identifying parameters (e.g., different server names)."
    name = "Nested Different Server Start"

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs):
        global _server_b_triggered_by_this_plugin
        _server_b_triggered_by_this_plugin = False  # Reset state on load/reload

        self.logger.debug("Plugin '%s' v%s loaded.", self.name, self.version)
        if SERVER_A_NAME_TRIGGER == SERVER_B_NAME_NESTED:
            self.logger.error(
                "'%s' Misconfiguration: SERVER_A_NAME_TRIGGER ('%s') and SERVER_B_NAME_NESTED ('%s') are the same. This test requires two different server names. Plugin might not work as intended.",
                self.name,
                SERVER_A_NAME_TRIGGER,
                SERVER_B_NAME_NESTED,
            )
            return

        self.logger.debug(
            "'%s': Test Instructions:\n  1. Ensure this plugin is enabled and BSM DEBUG logging for PluginManager is active.\n  2. Ensure servers '%s' and '%s' are configured in BSM.\n  3. Manually start server '%s'.\n  4. This plugin's 'before_server_start' for '%s' will attempt to start '%s'.\n  5. Expect to see 'before_server_start' logs from this plugin for BOTH '%s' AND '%s'.",
            self.name,
            SERVER_A_NAME_TRIGGER,
            SERVER_B_NAME_NESTED,
            SERVER_A_NAME_TRIGGER,
            SERVER_A_NAME_TRIGGER,
            SERVER_B_NAME_NESTED,
            SERVER_A_NAME_TRIGGER,
            SERVER_B_NAME_NESTED,
        )

    @app_event("before_server_start")
    async def trigger_nested_server_start(self, **kwargs: Any):
        global _server_b_triggered_by_this_plugin

        server_name = kwargs.get("server_name")

        self.logger.debug(
            "--- NESTED TEST: 'before_server_start' invoked for server '%s'.",
            server_name,
        )

        if (
            server_name == SERVER_A_NAME_TRIGGER
            and not _server_b_triggered_by_this_plugin
        ):
            self.logger.debug(
                "--- NESTED TEST (Server A: '%s'): This is the initial trigger. Attempting to start Server B ('%s').",
                SERVER_A_NAME_TRIGGER,
                SERVER_B_NAME_NESTED,
            )
            _server_b_triggered_by_this_plugin = True  # Set flag to avoid re-triggering from Server B's handler if it's this plugin
            try:
                # This API call should trigger 'before_server_start' for SERVER_B_NAME_NESTED.
                # The granular re-entrancy guard should allow its handlers to run.
                await self.api.server.start({"server_name": SERVER_B_NAME_NESTED})
                self.logger.debug(
                    "--- NESTED TEST (Server A: '%s'): Call to start Server B ('%s') initiated.",
                    SERVER_A_NAME_TRIGGER,
                    SERVER_B_NAME_NESTED,
                )
            except Exception as e:
                self.logger.error(
                    "--- NESTED TEST (Server A: '%s'): API call self.api.server.start for '%s' failed unexpectedly: %s",
                    SERVER_A_NAME_TRIGGER,
                    SERVER_B_NAME_NESTED,
                    e,
                    exc_info=True,
                )

        elif server_name == SERVER_B_NAME_NESTED:
            # This block is expected to be reached if the granular guard works correctly.
            self.logger.debug(
                "--- NESTED TEST (Server B: '%s'): 'before_server_start' successfully dispatched for the nested server start. Granular guard test PASSED for this step.",
                SERVER_B_NAME_NESTED,
            )
            # Do not trigger further starts from here to prevent complex loops in this test.

        else:
            self.logger.debug(
                "--- NESTED TEST: 'before_server_start' for '%s' is not part of the primary test flow. Ignoring.",
                server_name,
            )

        self.logger.debug(
            "--- NESTED TEST: Finished 'before_server_start' for server '%s'.",
            server_name,
        )

    @app_event("on_unload")
    async def plugin_unloaded(self, **kwargs):
        self.logger.debug("Plugin '%s' v%s is unloading.", self.name, self.version)

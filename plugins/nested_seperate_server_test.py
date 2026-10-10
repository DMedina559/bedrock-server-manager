# <PLUGIN_DIR>/nested_seperate_server_test.py
"""
Plugin: NestedDifferentServerStartPlugin

Purpose:
Tests the PluginManager's GRANULAR event re-entrancy guard.
Specifically, it verifies that if `before_server_start` for Server A triggers
a `start_server` call for a DIFFERENT Server B, the `before_server_start`
event handlers for Server B ARE correctly dispatched (not skipped).

Test Flow:
1. Initial Trigger:
   - Manually start a server (e.g., "server1") via CLI or Web UI.
   - This triggers `before_server_start` for "server1".

2. Event A (`before_server_start` for "server1"):
   - This plugin's `before_server_start` handler is invoked for "server1".
   - It logs this and then calls `self.api.server.start(server_name="server2", ...)`.
     (Ensure "server2" is a different, validly configured server name).

3. Event B (Expected `before_server_start` for "server2"):
   - The `self.api.server.start(server_name="server2")` call should trigger
     `before_server_start` for "server2".
   - **Expected Behavior (Granular Guard):** The PluginManager should generate a
     key like `('before_server_start', 'server2')`. This key should NOT match
     `('before_server_start', 'server1')` already on the stack.
     Thus, event handlers for `before_server_start` (including this plugin's)
     SHOULD be dispatched for "server2".

4. Verification:
   - This plugin's `before_server_start` handler will be called again, this
     time with `server_name="server2"`.
   - The plugin logs this second call, confirming the dispatch for Server B.
   - The handler for "server2" will not trigger further starts to keep the test simple.

Setup for Testing:
- Ensure you have at least two servers configured, e.g., "server1" and "server2".
- Place this plugin in your user plugin directory and ensure it's enabled.
- Set logging level for 'bedrock_server_manager.plugins.plugin_manager' to DEBUG.
- Start "server1" (e.g., `bsm server start server1`).

What to Look For in the Logs:
- Log messages from this plugin for both "server1" and "server2" within `before_server_start`.
- DEBUG logs from `PluginManager` showing:
  - `Dispatching standard event 'before_server_start' (key: ('before_server_start', 'server1')) ...`
  - Later, inside that, `Dispatching standard event 'before_server_start' (key: ('before_server_start', 'server2')) ...`
  - Crucially, NO "Skipping recursive trigger..." message for the "server2" event.
"""

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

"""
Plugin: CustomEventLoopTestPlugin - Tests PluginManager's Custom Event Re-entrancy Guard.

Purpose:
This plugin intentionally creates a controlled scenario where custom plugin events
could lead to an infinite recursive loop if not for the PluginManager's
thread-local custom event stack protection (`_custom_event_context.stack`).

Test Flow (Custom Event X -> Custom Event Y -> Attempted Custom Event X'):
1. Initial Trigger:
   - Upon loading (`on_load`), this plugin sends 'custom_loop:event_X'.

2. Handling 'custom_loop:event_X':
   - The plugin's `handle_event_x` method is invoked.
   - Inside this handler, it sends 'custom_loop:event_Y'.

3. Handling 'custom_loop:event_Y':
   - The plugin's `handle_event_y` method is invoked.
   - Inside this handler, it attempts to send 'custom_loop:event_X' again.

4. Attempted Recursive 'custom_loop:event_X' dispatch:
   - The `self.api.send_event('custom_loop:event_X', ...)` call from `handle_event_y`
     would normally try to trigger 'custom_loop:event_X' again.
   - **Expected Behavior (Re-entrancy Guard in Action):**
     The PluginManager should detect that 'custom_loop:event_X' is already being
     processed in the current thread's *custom event* stack. Consequently, it will
     *skip dispatching the event handlers* for this second, recursive attempt.
     The `self.api.send_event()` call itself will complete.

Setup for Testing:
- Place this plugin in your user plugin directory.
- Ensure the plugin is enabled.
- **Crucially, set the logging level for 'bedrock_server_manager.plugins.plugin_manager'
  to DEBUG** in your application's logging configuration to see the
  "Skipping recursive custom event..." message.
- The test automatically runs when the plugin is loaded.

What to Look For in the Logs:
- All "--- CUSTOM LOOP TEST ---" log messages from this plugin.
- A **DEBUG** log message from `bedrock_server_manager.plugins.plugin_manager` stating:
  "Skipping recursive custom event 'custom_loop:event_X'..."
  This confirms the re-entrancy guard for custom events worked.
- The log message from this plugin:
  "--- CUSTOM LOOP TEST (HANDLER Y): Recursive self.api.send_event('custom_loop:event_X') completed."
  This indicates the API call itself returned and didn't cause a stack overflow.
"""

from bedrock_server_manager import PluginBase, app_event

EVENT_X_NAME = "custom_loop:event_X"
EVENT_Y_NAME = "custom_loop:event_Y"


class CustomEventLoopTestPlugin(PluginBase):
    """
    Tests the PluginManager's stack-based re-entrancy guard for custom events
    using a chained custom event sequence: Event X -> Event Y -> Event X (recursive).
    """

    version = "1.2.0"
    author = "dmedina559"
    description = "Tests the PluginManager's stack-based re-entrancy guard for custom events using a chained custom event sequence."
    name = "Custom Event Loop Test"

    @app_event("on_load")
    async def plugin_loaded(self):
        self.logger.debug("Plugin '%s' v%s loaded.", self.name, self.version)
        self.logger.warning(
            "'%s': This plugin will intentionally attempt to create a '%s' -> '%s' -> (recursive) '%s' custom event dispatch loop to test the PluginManager's custom event re-entrancy guard.",
            self.name,
            EVENT_X_NAME,
            EVENT_Y_NAME,
            EVENT_X_NAME,
        )
        self.logger.debug(
            "'%s': To observe the test: \n  1. Ensure this plugin is enabled.\n  2. Set logging level for 'bedrock_server_manager.plugins.plugin_manager' to DEBUG.\n  3. The test initiates automatically. Observe application logs for '--- CUSTOM LOOP TEST ---' messages and the critical 'Skipping recursive custom event' DEBUG message from PluginManager.",
            self.name,
        )

        # Initial trigger for the event chain
        self.logger.debug(
            "--- CUSTOM LOOP TEST (ON_LOAD): Initial trigger by sending '%s'.",
            EVENT_X_NAME,
        )
        try:
            await self.api.send_event(EVENT_X_NAME, source_method="on_load")
            self.logger.debug(
                "--- CUSTOM LOOP TEST (ON_LOAD): Initial '%s' sent successfully.",
                EVENT_X_NAME,
            )
        except Exception as e:
            self.logger.error(
                "--- CUSTOM LOOP TEST (ON_LOAD): Failed to send initial '%s': %s",
                EVENT_X_NAME,
                e,
                exc_info=True,
            )

    @app_event(EVENT_X_NAME)
    async def handle_event_x(self, *args, **kwargs):
        """
        Handler for EVENT_X_NAME ('custom_loop:event_X').
        This is the first step in our loop if triggered by on_load,
        or the recursive step if triggered by handle_event_y.
        """
        triggering_plugin = kwargs.pop(
            "_triggering_plugin", self.name
        )  # Should be self.name
        source_method = kwargs.get("source_method", "unknown")

        self.logger.debug(
            "--- CUSTOM LOOP TEST (HANDLER X): Received '%s' (Source: %s, Triggered by: %s).",
            EVENT_X_NAME,
            source_method,
            triggering_plugin,
        )
        self.logger.debug(
            "--- CUSTOM LOOP TEST (HANDLER X -> Y): From '%s' handler, sending '%s'.",
            EVENT_X_NAME,
            EVENT_Y_NAME,
        )
        try:
            await self.api.send_event(EVENT_Y_NAME, source_event_x_payload=kwargs)
        except Exception as e:
            self.logger.error(
                "--- CUSTOM LOOP TEST (HANDLER X): Failed to send '%s': %s",
                EVENT_Y_NAME,
                e,
                exc_info=True,
            )
        self.logger.debug(
            "--- CUSTOM LOOP TEST (HANDLER X): Finished handling '%s' (Source: %s).",
            EVENT_X_NAME,
            source_method,
        )

    @app_event(EVENT_Y_NAME)
    async def handle_event_y(self, *args, **kwargs):
        """
        Handler for EVENT_Y_NAME ('custom_loop:event_Y').
        This is the middle step, which will attempt the recursive call.
        """
        triggering_plugin = kwargs.pop(
            "_triggering_plugin", self.name
        )  # Should be self.name

        self.logger.debug(
            "--- CUSTOM LOOP TEST (HANDLER Y): Received '%s' (Triggered by: %s). ",
            EVENT_Y_NAME,
            triggering_plugin,
        )
        self.logger.debug(
            "--- CUSTOM LOOP TEST (HANDLER Y -> X - Recursive Attempt): From '%s' handler, DANGEROUSLY attempting to re-send '%s'.",
            EVENT_Y_NAME,
            EVENT_X_NAME,
        )
        try:
            # This send_event call will attempt to trigger EVENT_X_NAME again.
            # The PluginManager's custom event stack guard should prevent the *handlers*
            # for this recursive EVENT_X_NAME from executing again.
            await self.api.send_event(
                EVENT_X_NAME, source_method="handle_event_y_recursive_attempt"
            )

            self.logger.debug(
                "--- CUSTOM LOOP TEST (HANDLER Y): Recursive self.api.send_event('%s') call completed. This means the API call itself didn't crash due to a stack overflow from custom event recursion. The **critical confirmation** of the re-entrancy guard is a DEBUG log message from 'bedrock_server_manager.plugins.plugin_manager' stating: 'Skipping recursive custom event '%s'...'. ",
                EVENT_X_NAME,
                EVENT_X_NAME,
            )
        except Exception as e:
            self.logger.error(
                "--- CUSTOM LOOP TEST (HANDLER Y): Recursive API call self.api.send_event('%s') failed unexpectedly: %s",
                EVENT_X_NAME,
                e,
                exc_info=True,
            )
        self.logger.debug(
            "--- CUSTOM LOOP TEST (HANDLER Y): Finished handling '%s'.", EVENT_Y_NAME
        )

    @app_event("on_unload")
    async def on_unload(self, **kwargs):
        """Called when the plugin is unloaded."""
        self.logger.debug("Plugin '%s' v%s is unloading.", self.name, self.version)

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

from bedrock_server_manager import PluginBase

EVENT_X_NAME = "custom_loop:event_X"
EVENT_Y_NAME = "custom_loop:event_Y"


class CustomEventLoopTestPlugin(PluginBase):
    """
    Tests the PluginManager's stack-based re-entrancy guard for custom events
    using a chained custom event sequence: Event X -> Event Y -> Event X (recursive).
    """

    version = "1.1.0"

    def on_load(self):
        self.logger.info(f"Plugin '{self.name}' v{self.version} loaded.")
        self.logger.warning(
            f"'{self.name}': This plugin will intentionally attempt to create a "
            f"'{EVENT_X_NAME}' -> '{EVENT_Y_NAME}' -> (recursive) '{EVENT_X_NAME}' "
            "custom event dispatch loop to test the PluginManager's custom event re-entrancy guard."
        )
        self.logger.info(
            f"'{self.name}': To observe the test: \n"
            f"  1. Ensure this plugin is enabled.\n"
            f"  2. Set logging level for 'bedrock_server_manager.plugins.plugin_manager' to DEBUG.\n"
            f"  3. The test initiates automatically. Observe application logs for "
            f"'--- CUSTOM LOOP TEST ---' messages and the critical "
            f"'Skipping recursive custom event' DEBUG message from PluginManager."
        )

        # Register listeners
        self.api.listen_for_event(EVENT_X_NAME, self.handle_event_x)
        self.api.listen_for_event(EVENT_Y_NAME, self.handle_event_y)

        # Initial trigger for the event chain
        self.logger.info(
            f"--- CUSTOM LOOP TEST (ON_LOAD): Initial trigger by sending '{EVENT_X_NAME}'."
        )
        try:
            self.api.send_event(EVENT_X_NAME, source_method="on_load")
            self.logger.info(
                f"--- CUSTOM LOOP TEST (ON_LOAD): Initial '{EVENT_X_NAME}' sent successfully."
            )
        except Exception as e:
            self.logger.error(
                f"--- CUSTOM LOOP TEST (ON_LOAD): Failed to send initial '{EVENT_X_NAME}': {e}",
                exc_info=True,
            )

    def handle_event_x(self, *args, **kwargs):
        """
        Handler for EVENT_X_NAME ('custom_loop:event_X').
        This is the first step in our loop if triggered by on_load,
        or the recursive step if triggered by handle_event_y.
        """
        triggering_plugin = kwargs.pop(
            "_triggering_plugin", self.name
        )  # Should be self.name
        source_method = kwargs.get("source_method", "unknown")

        self.logger.info(
            f"--- CUSTOM LOOP TEST (HANDLER X): Received '{EVENT_X_NAME}' (Source: {source_method}, Triggered by: {triggering_plugin})."
        )
        self.logger.info(
            f"--- CUSTOM LOOP TEST (HANDLER X -> Y): From '{EVENT_X_NAME}' handler, sending '{EVENT_Y_NAME}'."
        )
        try:
            self.api.send_event(EVENT_Y_NAME, source_event_x_payload=kwargs)
        except Exception as e:
            self.logger.error(
                f"--- CUSTOM LOOP TEST (HANDLER X): Failed to send '{EVENT_Y_NAME}': {e}",
                exc_info=True,
            )
        self.logger.info(
            f"--- CUSTOM LOOP TEST (HANDLER X): Finished handling '{EVENT_X_NAME}' (Source: {source_method})."
        )

    def handle_event_y(self, *args, **kwargs):
        """
        Handler for EVENT_Y_NAME ('custom_loop:event_Y').
        This is the middle step, which will attempt the recursive call.
        """
        triggering_plugin = kwargs.pop(
            "_triggering_plugin", self.name
        )  # Should be self.name
        original_payload = kwargs.get("source_event_x_payload", {})

        self.logger.info(
            f"--- CUSTOM LOOP TEST (HANDLER Y): Received '{EVENT_Y_NAME}' (Triggered by: {triggering_plugin}). "
            f"Original X payload: {original_payload}"
        )
        self.logger.info(
            f"--- CUSTOM LOOP TEST (HANDLER Y -> X - Recursive Attempt): From '{EVENT_Y_NAME}' handler, "
            f"DANGEROUSLY attempting to re-send '{EVENT_X_NAME}'."
        )
        try:
            # This send_event call will attempt to trigger EVENT_X_NAME again.
            # The PluginManager's custom event stack guard should prevent the *handlers*
            # for this recursive EVENT_X_NAME from executing again.
            self.api.send_event(
                EVENT_X_NAME, source_method="handle_event_y_recursive_attempt"
            )

            self.logger.info(
                f"--- CUSTOM LOOP TEST (HANDLER Y): Recursive self.api.send_event('{EVENT_X_NAME}') call completed. "
                "This means the API call itself didn't crash due to a stack overflow from custom event recursion. "
                "The **critical confirmation** of the re-entrancy guard is a DEBUG log message from "
                "'bedrock_server_manager.plugins.plugin_manager' stating: "
                f"'Skipping recursive custom event '{EVENT_X_NAME}'...'. "
            )
        except Exception as e:
            self.logger.error(
                f"--- CUSTOM LOOP TEST (HANDLER Y): Recursive API call self.api.send_event('{EVENT_X_NAME}') "
                f"failed unexpectedly: {e}",
                exc_info=True,
            )
        self.logger.info(
            f"--- CUSTOM LOOP TEST (HANDLER Y): Finished handling '{EVENT_Y_NAME}'."
        )

    def on_unload(self):
        """Called when the plugin is unloaded."""
        self.logger.info(f"Plugin '{self.name}' v{self.version} is unloading.")

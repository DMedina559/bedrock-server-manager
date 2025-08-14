# <PLUGIN_DIR>/recursive_loop_test.py
"""
Plugin to test the PluginManager's event re-entrancy guard.

Purpose:
This plugin is designed to intentionally create a scenario where plugin events
could lead to an infinite recursive loop if not for the PluginManager's
thread-local event stack protection.

Test Flow (A -> B -> A'):
1. Event A ('before_server_start'):
   - This plugin's `before_server_start` handler is called.
   - It then calls `self.api.backup_all()`.

2. Event B ('before_backup'):
   - The `self.api.backup_all()` call internally triggers the 'before_backup' event.
   - This plugin's `before_backup` handler is called.
   - It then attempts to call `self.api.start_server()` for the same server.

3. Event A' ('before_server_start' - Recursive Attempt):
   - The `self.api.start_server()` call from Event B would normally try to
     trigger the 'before_server_start' event again.
   - **Expected Behavior:** The PluginManager should detect that 'before_server_start'
     is already in the current thread's event stack and will *skip dispatching
     the event handlers* for this second, recursive attempt. The `api.start_server()`
     function itself will continue its execution (and might report "server already
     running" or attempt to start another instance depending on system state,
     which is separate from the event guard test).

What to look for in the logs:
- The "--- LOOP TEST ---" messages from this plugin.
- A DEBUG message from `bedrock_server_manager.plugins.plugin_manager` similar to:
  "Skipping recursive event trigger for 'before_server_start'."
- The "--- LOOP TEST (B): Recursive self.api.start_server() call completed..." message,
  indicating the API call didn't crash due to an event stack overflow.
"""
from bedrock_server_manager import PluginBase
from typing import Any


class RecursiveLoopPlugin(PluginBase):
    """
    Tests the PluginManager's stack-based re-entrancy guard using a
    'before_server_start' -> 'before_backup' -> 'before_server_start' event chain.
    """

    version = "1.1.0"

    def on_load(self):
        self.logger.info(
            f"Plugin '{self.name}' v{self.version} loaded. "
            "This plugin tests event loop protection. To run the test, start any server "
            "in a way that does NOT set the GUARD_VARIABLE for the initial start trigger "
            "(e.g., direct CLI call, or if api.start_server uses trigger_event)."
        )
        self.logger.warning(
            f"Plugin '{self.name}': This plugin will intentionally attempt to create an "
            "A ('before_server_start') -> B ('before_backup') -> A' ('before_server_start') event dispatch loop."
        )

    def before_server_start(self, **kwargs: Any):
        """This is EVENT A in the A -> B -> A' loop."""
        server_name = kwargs.get("server_name")
        self.logger.info(
            f"--- LOOP TEST (EVENT A - Handler Call): 'before_server_start' entered for server '{server_name}'."
        )
        self.logger.info(
            "--- LOOP TEST (A->B): From 'before_server_start', calling self.api.backup_all() to trigger 'before_backup'."
        )
        try:
            # Assuming the server is not yet running, so stop_start_server=False is appropriate.
            self.api.backup_all(server_name=server_name, stop_start_server=False)
        except Exception as e:
            self.logger.error(
                f"--- LOOP TEST (EVENT A): API call self.api.backup_all() failed unexpectedly: {e}",
                exc_info=True,
            )

        self.logger.info(
            "--- LOOP TEST (EVENT A - Handler Call): Finished 'before_server_start' handler execution."
        )

    def before_backup(self, **kwargs: Any):
        """This is EVENT B in the A -> B -> A' loop."""
        server_name = kwargs.get("server_name")
        self.logger.info(
            f"--- LOOP TEST (EVENT B - Handler Call): 'before_backup' entered for server '{server_name}'."
        )
        self.logger.info(
            "--- LOOP TEST (B->A' - Recursive Attempt): From 'before_backup', DANGEROUS CALL! "
            "Attempting self.api.start_server() to re-trigger 'before_server_start' event dispatch."
        )
        try:
            # This call to api.start_server() will attempt to trigger 'before_server_start' again.
            # The PluginManager's event stack guard should prevent the *handlers* for this
            # recursive 'before_server_start' from executing.
            # The api.start_server() function itself will still run its internal logic.
            self.api.start_server(
                server_name=server_name
            )  # Using "detached" for the API call

            self.logger.info(
                "--- LOOP TEST (EVENT B): Recursive self.api.start_server() call completed. "
                "This indicates the API call itself did not crash. "
                "Crucially, check application DEBUG logs for a message like "
                "'Skipping recursive event trigger for before_server_start' from PluginManager. "
                "That log line confirms the event re-entrancy guard worked for the *event dispatch*."
            )
        except Exception as e:
            self.logger.error(
                f"--- LOOP TEST (EVENT B): Recursive API call self.api.start_server() failed unexpectedly: {e}",
                exc_info=True,
            )

        self.logger.info(
            "--- LOOP TEST (EVENT B - Handler Call): Finished 'before_backup' handler execution."
        )

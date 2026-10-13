# <PLUGIN_DIR>/recursive_loop_test.py
"""Demonstrate cancellation of a recursive start hook for the same server."""

from typing import Any

from bedrock_server_manager import PluginBase, app_event


class RecursiveLoopPlugin(PluginBase):
    """
    Tests the PluginManager's stack-based re-entrancy guard using a
    'before_server_start' -> 'before_backup' -> 'before_server_start' event chain.
    """

    version = "1.2.0"
    author = "dmedina559"
    description = "Tests the PluginManager's stack-based re-entrancy guard using a 'before_server_start' -> 'before_backup' -> 'before_server_start' event chain."
    name = "Recursive Loop Test"

    @app_event("on_load")
    async def plugin_loaded(self, **kwargs):
        self.logger.debug(
            "Plugin '%s' v%s loaded. This plugin tests event loop protection. To run the test, start any server in a way that does NOT set the GUARD_VARIABLE for the initial start trigger (e.g., direct CLI call, or if api.server.start uses trigger_event).",
            self.name,
            self.version,
        )
        self.logger.warning(
            "Plugin '%s': This plugin will intentionally attempt to create an A ('before_server_start') -> B ('before_backup') -> A' ('before_server_start') event dispatch loop.",
            self.name,
        )

    @app_event("before_server_start")
    async def trigger_recursive_loop_a(self, **kwargs: Any):
        """This is EVENT A in the A -> B -> A' loop."""

        server_name = kwargs.get("server_name")
        self.logger.debug(
            "--- LOOP TEST (EVENT A - Handler Call): 'before_server_start' entered for server '%s'.",
            server_name,
        )
        self.logger.debug(
            "--- LOOP TEST (A->B): From 'before_server_start', calling self.api.backup_restore.backup_all() to trigger 'before_backup'."
        )
        try:
            (
                await self.api.backup_restore.backup_all(
                    request={"server_name": server_name}
                )
            ).model_dump(mode="python")
        except Exception as e:
            self.logger.error(
                "--- LOOP TEST (EVENT A): API call self.api.backup_restore.backup_all() failed unexpectedly: %s",
                e,
                exc_info=True,
            )

        self.logger.debug(
            "--- LOOP TEST (EVENT A - Handler Call): Finished 'before_server_start' handler execution."
        )

    @app_event("before_backup")
    async def trigger_recursive_loop_b(self, **kwargs: Any):
        """This is EVENT B in the A -> B -> A' loop."""

        server_name = kwargs.get("server_name")
        self.logger.debug(
            "--- LOOP TEST (EVENT B - Handler Call): 'before_backup' entered for server '%s'.",
            server_name,
        )
        self.logger.debug(
            "--- LOOP TEST (B->A' - Recursive Attempt): From 'before_backup', DANGEROUS CALL! "
            "Attempting self.api.server.start() to re-trigger 'before_server_start' event dispatch."
        )
        try:
            # This call to api.server.start() will attempt to trigger 'before_server_start' again.
            # The PluginManager's event stack guard should prevent the *handlers* for this
            # recursive 'before_server_start' from executing.
            # The api.server.start() function itself will still run its internal logic.
            await self.api.server.start({"server_name": server_name})

            self.logger.debug(
                "--- LOOP TEST (EVENT B): Recursive self.api.server.start() call completed. "
                "This indicates the API call itself did not crash. "
                "Crucially, check application DEBUG logs for a message like "
                "'Skipping recursive event trigger for before_server_start' from PluginManager. "
                "That log line confirms the event re-entrancy guard worked for the *event dispatch*."
            )
        except Exception as e:
            self.logger.error(
                "--- LOOP TEST (EVENT B): Recursive API call self.api.server.start() failed unexpectedly: %s",
                e,
                exc_info=True,
            )

        self.logger.debug(
            "--- LOOP TEST (EVENT B - Handler Call): Finished 'before_backup' handler execution."
        )

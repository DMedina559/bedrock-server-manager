# src/bedrock_server_manager/core/bedrock_process_manager.py
"""Manage the lifecycle and monitoring of Bedrock server processes.

This module provides the :class:`~.BedrockProcessManager` class, which is responsible
for monitoring running Bedrock server instances. It detects crashes or unexpected
shutdowns and attempts to restart servers based on configuration policies. Player presence is reduced by each owned output stream.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional

from ..error import BSMError, FileOperationError
from ..logging import RepeatedFailureReporter, log_operation_error

if TYPE_CHECKING:
    from ..config.settings import Settings
    from ..state.models import RuntimeState
    from .bedrock_server import BedrockServer


class BedrockProcessManager:
    """Monitor owned server processes and restart unintended stops asynchronously."""

    def __init__(
        self,
        settings: "Settings",
        server_provider: Optional[Callable[[str], "BedrockServer"]] = None,
        *,
        stop_server: Callable[[str], Awaitable[None]] | None = None,
        record_failure: Callable[[str, Exception, float], None] | None = None,
        runtime: "RuntimeState | None" = None,
        start_server: Callable[[str], Awaitable[None]] | None = None,
    ):
        """Initialize the BedrockProcessManager with explicit dependencies."""
        self.settings = settings
        self.server_provider = server_provider
        self.stop_server = stop_server
        self.record_failure = record_failure
        self.runtime = runtime
        self.start_server = start_server
        self.recovery_failures: set[str] = set()
        self._healthy_since: dict[str, float] = {}
        self.monitor_observed_at: float | None = None
        self.monitor_failures = 0
        self.monitor_observations: dict[str, float] = {}
        self.monitor_errors: dict[str, str] = {}
        self.servers: Dict[str, "BedrockServer"] = {}
        self.restart_attempts: dict[str, int] = {}
        self._server_checks: dict[str, asyncio.Task] = {}
        self._check_slots = asyncio.Semaphore(4)
        self._restart_after: dict[str, float] = {}
        self.logger = logging.getLogger(__name__)
        self._failures = RepeatedFailureReporter(self.logger)
        self._shutdown_event = asyncio.Event()
        self._wake = asyncio.Event()
        self.monitoring_task: Optional[asyncio.Task[Any]] = None
        self.logger.debug("BedrockProcessManager initialized.")

    def check_health(self) -> bool:
        """Check if server process monitoring and managed servers are healthy."""
        if self._shutdown_event.is_set():
            return True
        if self.monitoring_task is not None and self.monitoring_task.done():
            return False
        if self.recovery_failures or self.monitor_errors:
            return False
        if (
            self.monitor_observed_at is not None
            and time.time() - self.monitor_observed_at
            > max(30, self.settings.get("monitoring.process_interval_sec", 10) * 3)
        ):
            return False
        runtimes = (
            self.runtime.servers.values()
            if self.runtime is not None
            else (
                server._runtime_state.get_server_runtime(name)
                for name, server in self.servers.items()
            )
        )
        if any(
            record.output_error is not None
            or (record.running and not record.command_available)
            for record in runtimes
        ):
            return False
        for attempts in self.restart_attempts.values():
            if attempts > 0:
                return False
        return True

    async def start(self):
        """Call this from the main thread to start monitoring."""
        if self.monitoring_task is None or self.monitoring_task.done():
            self._shutdown_event = asyncio.Event()
            self.monitor_observed_at = time.time()
            self.monitoring_task = asyncio.create_task(self._monitor_servers())

    async def add_server(self, server: "BedrockServer"):
        """Adds a server to be managed by the process manager.

        :param server: The server instance to monitor.
        """
        self.logger.debug(
            "Adding server '%s' to process manager for monitoring.", server.server_name
        )
        self.servers[server.server_name] = server
        server.process.on_exit = self._wake.set
        self.recovery_failures.discard(server.server_name)

    async def remove_server(self, server_name: str):
        """Remove a server from the process manager.

        This stops the manager from monitoring the server, but does not stop the
        server process itself.

        :param server_name: The name of the server to remove.
        """
        self.recovery_failures.discard(server_name)
        self._healthy_since.pop(server_name, None)
        if server_name in self.servers:
            self.logger.debug("Removing server '%s' from process manager.", server_name)
            del self.servers[server_name]
            self.monitor_observations.pop(server_name, None)
            self.monitor_errors.pop(server_name, None)
            self.restart_attempts.pop(server_name, None)
            self._restart_after.pop(server_name, None)
            task = self._server_checks.get(server_name)
            if task is not None and task is not asyncio.current_task():
                task.cancel()
            for phase in ("probe", "recovery", "players"):
                self._failures.failures.pop(f"{phase}:{server_name}", None)

    async def quiesce(self) -> None:
        """Stop monitoring and automatic restarts before draining operations."""
        self.logger.debug("Shutdown signal received. Stopping server monitoring.")
        self._shutdown_event.set()

        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            await asyncio.gather(self.monitoring_task, return_exceptions=True)

    async def shutdown(self):
        """Shuts down all managed servers concurrently and stops the monitoring task.

        This method:
        1. Sets the shutdown event for the monitoring task and cancels it immediately.
        2. Spawns tasks to stop all currently running servers concurrently with exception handling.
        """

        await self.quiesce()

        # Concurrently shut down all servers
        self.logger.debug("Stopping all running servers concurrently...")

        async def _stop_server(server_name, server):
            try:
                is_running = await server.is_running()

                if not is_running:
                    return

                try:
                    if self.stop_server is None:
                        raise BSMError("Server stop capability is not available.")
                    await self.stop_server(server_name)
                except Exception as e:
                    log_operation_error(
                        self.logger,
                        "Error stopping '%s' through the stop capability: %s. Attempting direct stop.",
                        server_name,
                        e,
                        error=e,
                    )
                    await server.stop()

                self.logger.debug("Stopped server '%s'", server_name)
            except Exception as e_stop:
                log_operation_error(
                    self.logger,
                    "Failed to stop server '%s': %s",
                    server_name,
                    e_stop,
                    error=e_stop,
                )

        tasks = [
            _stop_server(server_name, server)
            for server_name, server in list(self.servers.items())
        ]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _try_restart_server(self, server: "BedrockServer"):
        """Tries to restart a crashed server asynchronously.

        Checks the restart retry limit before attempting to restart. If the
        limit is reached, marks the server status as 'ERROR' and stops monitoring.

        :param server: The server instance to restart.
        """
        if time.monotonic() < self._restart_after.get(server.server_name, 0):
            return
        max_retries = self.settings.get("monitoring.max_retries", 3)

        if self.restart_attempts.get(server.server_name, 0) > max_retries:
            self.logger.error(
                "Server '%s' reached the restart limit (%s attempts); automatic recovery has stopped.",
                server.server_name,
                max_retries,
            )
            await self.write_error_status(server.server_name)
            await self.remove_server(server.server_name)  # Stop monitoring
            self.recovery_failures.add(server.server_name)
            return

        self.logger.info(
            "Attempting to restart server '%s'. Attempt %s/%s.",
            server.server_name,
            self.restart_attempts.get(server.server_name, 0),
            max_retries,
        )
        try:
            if self.start_server is not None:
                await self.start_server(server.server_name)
            else:
                await server.start()
            self._restart_after.pop(server.server_name, None)
            self.logger.debug("Server '%s' restarted successfully.", server.server_name)
        except Exception as e:
            log_operation_error(
                self.logger,
                "Could not restart server '%s': %s",
                server.server_name,
                e,
                error=e,
            )
            self._restart_after[server.server_name] = time.monotonic() + 5

    async def write_error_status(self, server_name: str):
        """Writes 'ERROR' to server config status asynchronously.

        :param server_name: The name of the server.

        :raises FileOperationError: If writing to the config file fails.
        """
        if not callable(self.server_provider):
            return
        server = self.server_provider(server_name)
        if server:
            try:
                await server.set_status_in_config("ERROR")
            except BSMError as e:
                log_operation_error(
                    self.logger,
                    "Error writing status for server '%s': %s",
                    server_name,
                    e,
                    error=e,
                )
                raise FileOperationError(
                    f"Failed to write status for server '{server_name}'."
                )

    async def _monitor_servers(self):  # noqa: C901
        """Monitors server processes and restarts them if they crash asynchronously.

        This method runs as a background task. It periodically checks:
        1. If registered servers are running. If a server has crashed (stopped
           without ``intentionally_stopped`` flag), it attempts restart.
        Player presence, bans and identities are driven by the owned output stream.
        """

        try:
            monitoring_interval = int(
                self.settings.get("monitoring.process_interval_sec", 10)
            )
        except Exception:
            monitoring_interval = 10

        self.logger.debug(
            "Async server monitoring loop started with a %s second interval.",
            monitoring_interval,
        )

        try:
            while not self._shutdown_event.is_set():
                # Wait loop utilizing shutdown event natively with timeout
                try:
                    try:
                        await asyncio.wait_for(
                            self._wake.wait(), timeout=monitoring_interval
                        )
                    except asyncio.TimeoutError:
                        pass

                    if self._shutdown_event.is_set():
                        break
                except asyncio.CancelledError:
                    break

                self._wake.clear()
                self.monitor_observed_at = time.time()
                for server_name, server in list(self.servers.items()):
                    if server_name not in self._server_checks:
                        task = asyncio.create_task(
                            self._check_server(server_name, server),
                            name=f"server-monitor:{server_name}",
                        )
                        self._server_checks[server_name] = task
                        task.add_done_callback(
                            lambda finished, name=server_name: self._check_finished(
                                name, finished
                            )
                        )
        finally:
            tasks = list(self._server_checks.values())
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    def _check_finished(self, name: str, task: asyncio.Task) -> None:
        if self._server_checks.get(name) is task:
            self._server_checks.pop(name, None)
        if not task.cancelled():
            self.monitor_observed_at = time.time()
        if not task.cancelled() and task.exception() is not None:
            self.logger.error(
                "Server monitor failed for '%s'.", name, exc_info=task.exception()
            )

    async def _check_server(self, server_name, server):
        async with self._check_slots:
            if (
                self.servers.get(server_name) is not server
                or self._shutdown_event.is_set()
            ):
                return
            await self._observe_server(server_name, server)

    async def _observe_server(self, server_name, server):
        # Determine run state
        probe_started = time.monotonic()
        try:
            is_running = await server.is_running()
            await server.reconcile_status(is_running)
            self._failures.recover(f"probe:{server_name}")
            self.monitor_observations[server_name] = time.time()
            self.monitor_errors.pop(server_name, None)
        except Exception as error:
            self.monitor_failures += 1
            self.monitor_errors[server_name] = type(error).__name__
            if self.record_failure is not None:
                self.record_failure(server_name, error, probe_started)
            self._failures.report(
                f"probe:{server_name}",
                "Server monitoring unavailable (%s): %s; retrying.",
                error,
            )
            return

        if not is_running:
            self._healthy_since.pop(server_name, None)
            if not server.process.intentionally_stopped:
                if time.monotonic() < self._restart_after.get(server_name, 0):
                    return
                self.logger.warning(
                    "Monitored server '%s' has crashed.", server.server_name
                )
                self.restart_attempts[server_name] = (
                    self.restart_attempts.get(server_name, 0) + 1
                )
                try:
                    await self._try_restart_server(server)
                    self._failures.recover(f"recovery:{server_name}")
                except Exception as error:
                    self._failures.report(
                        f"recovery:{server_name}",
                        "Server recovery unavailable (%s): %s; retrying.",
                        error,
                    )
            else:
                self.logger.debug(
                    "Server '%s' was stopped intentionally. Removing from monitoring.",
                    server.server_name,
                )
                await self.remove_server(server_name)
        else:
            run = server.process.run
            if run is not None and not run.ready:
                self._healthy_since.pop(server_name, None)
                return
            stable_since = self._healthy_since.setdefault(server_name, time.monotonic())
            if time.monotonic() - stable_since >= max(
                30, self.settings.get("monitoring.process_interval_sec", 10) * 3
            ):
                self.restart_attempts.pop(server_name, None)
                self._restart_after.pop(server_name, None)

        # Owned output applies presence, bans and persistence independently of supervision.

# src/bedrock_server_manager/core/bedrock_process_manager.py
"""Manage the lifecycle and monitoring of Bedrock server processes.

This module provides the :class:`~.BedrockProcessManager` class, which is responsible
for monitoring running Bedrock server instances. It detects crashes or unexpected
shutdowns and attempts to restart servers based on configuration policies. It also
handles periodic tasks like player scanning from logs.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional

from ..error import BSMError, FileOperationError
from ..logging import RepeatedFailureReporter, log_operation_error

if TYPE_CHECKING:
    from ..config.settings import Settings
    from ..db.storage import Storage
    from ..events.publisher import EventPublisher
    from ..state.models import BanItem
    from .bedrock_server import BedrockServer


class BedrockProcessManager:
    """Monitor owned server processes and restart unintended stops asynchronously.

    Publish player observations through the injected event publisher.
    """

    def __init__(
        self,
        settings: "Settings",
        storage: "Storage",
        server_provider: Optional[Callable[[str], "BedrockServer"]] = None,
        *,
        events: Optional["EventPublisher"] = None,
        stop_server: Callable[[str], Awaitable[None]] | None = None,
        get_bans: Callable[[str], Awaitable[list["BanItem"]]] | None = None,
        record_failure: Callable[[str, Exception, float], None] | None = None,
    ):
        """Initialize the BedrockProcessManager with explicit dependencies."""
        self.settings = settings
        self.storage = storage
        self.server_provider = server_provider
        self.events = events
        self.stop_server = stop_server
        self.get_bans = get_bans
        self.record_failure = record_failure
        self.monitor_observed_at: float | None = None
        self.monitor_failures = 0
        self.monitor_observations: dict[str, float] = {}
        self.monitor_errors: dict[str, str] = {}
        self.servers: Dict[str, "BedrockServer"] = {}
        self.restart_attempts: dict[str, int] = {}
        self._pending_player_events: set[str] = set()
        self._server_checks: dict[str, asyncio.Task] = {}
        self._check_slots = asyncio.Semaphore(4)
        self._restart_after: dict[str, float] = {}
        self.logger = logging.getLogger(__name__)
        self._failures = RepeatedFailureReporter(self.logger)
        self._shutdown_event = asyncio.Event()
        self.player_scan_counter = 0
        self.monitoring_task: Optional[asyncio.Task[Any]] = None
        self.logger.debug("BedrockProcessManager initialized.")

    async def _publish_players(self, server: "BedrockServer") -> None:
        from ..events.player import PlayerSnapshot, publish_player_snapshot

        if self.events is None:
            raise BSMError("Player event publisher is not available.")
        receipt = await publish_player_snapshot(
            self.events,
            PlayerSnapshot(
                server_name=server.server_name,
                player_count=server.player_count,
                players=server.players,
            ),
        )
        if receipt.rejection_reason in {"capacity", "depth_limit"}:
            self._pending_player_events.add(server.server_name)
        else:
            # Partial listener delivery is recorded, not replayed to successful listeners.
            self._pending_player_events.discard(server.server_name)

    async def start(self):
        """Call this from the main thread to start monitoring."""
        if self.monitoring_task is None or self.monitoring_task.done():
            self._shutdown_event = asyncio.Event()
            self.monitoring_task = asyncio.create_task(self._monitor_servers())

    async def add_server(self, server: "BedrockServer"):
        """Adds a server to be managed by the process manager.

        :param server: The server instance to monitor.
        """
        self.logger.debug(
            "Adding server '%s' to process manager for monitoring.", server.server_name
        )
        self.servers[server.server_name] = server

    async def remove_server(self, server_name: str):
        """Remove a server from the process manager.

        This stops the manager from monitoring the server, but does not stop the
        server process itself.

        :param server_name: The name of the server to remove.
        """
        if server_name in self.servers:
            self.logger.debug("Removing server '%s' from process manager.", server_name)
            del self.servers[server_name]
            self.monitor_observations.pop(server_name, None)
            self.monitor_errors.pop(server_name, None)
            self.restart_attempts.pop(server_name, None)
            self._restart_after.pop(server_name, None)
            self._pending_player_events.discard(server_name)
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
            return

        self.logger.info(
            "Attempting to restart server '%s'. Attempt %s/%s.",
            server.server_name,
            self.restart_attempts.get(server.server_name, 0),
            max_retries,
        )
        try:
            await server.start()
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
        2. Queries server status for player counts.
        3. Scans logs for player activity.
        """

        try:
            monitoring_interval = int(
                self.settings.get("monitoring.process_interval_sec", 10)
            )
            player_log_monitoring_interval_sec = int(
                self.settings.get("monitoring.player_interval_sec", 10)
            )
        except Exception:
            monitoring_interval = 10
            player_log_monitoring_interval_sec = 10

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
                            self._shutdown_event.wait(), timeout=monitoring_interval
                        )
                    except asyncio.TimeoutError:
                        pass

                    if self._shutdown_event.is_set():
                        break
                except asyncio.CancelledError:
                    break

                self.player_scan_counter += monitoring_interval
                scan_players = (
                    self.player_scan_counter >= player_log_monitoring_interval_sec
                )
                for server_name, server in list(self.servers.items()):
                    if server_name not in self._server_checks:
                        task = asyncio.create_task(
                            self._check_server(
                                server_name, server, scan_players=scan_players
                            ),
                            name=f"server-monitor:{server_name}",
                        )
                        self._server_checks[server_name] = task
                        task.add_done_callback(
                            lambda finished, name=server_name: self._check_finished(
                                name, finished
                            )
                        )
                if self.player_scan_counter >= player_log_monitoring_interval_sec:
                    self.player_scan_counter = 0
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

    async def _check_server(self, server_name, server, *, scan_players):
        async with self._check_slots:
            if (
                self.servers.get(server_name) is not server
                or self._shutdown_event.is_set()
            ):
                return
            await self._observe_server(server_name, server, scan_players=scan_players)

    async def _observe_server(self, server_name, server, *, scan_players):
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
        elif scan_players:
            observed = False
            try:
                previous_player_count = server.player_count
                previous_players = server.players

                server.players = await server.player_tracker.update_online_players()
                observed = True
                server._runtime_state.update_server_runtime(
                    server_name, players_available=True
                )

                if (
                    server.player_count != previous_player_count
                    or server.players != previous_players
                    or server_name in self._pending_player_events
                ):
                    self.logger.debug(
                        "Player list/count changed for server '%s': count %s -> %s",
                        server.server_name,
                        previous_player_count,
                        server.player_count,
                    )
                    # Publish the authoritative snapshot through the application event bus.
                    try:
                        await self._publish_players(server)
                    except Exception as e:
                        self._pending_player_events.add(server_name)
                        self.logger.warning(
                            "Could not publish player stats update: %s",
                            type(e).__name__,
                            exc_info=True,
                        )

                # Enforce bans
                if server.players:
                    try:
                        if self.get_bans is None:
                            raise BSMError("Ban lookup capability is not available.")
                        bans = await self.get_bans(server.server_name)

                        if bans:
                            banned_xuids = {b.xuid: b for b in bans}
                            for p in server.players:
                                xuid = p.get("xuid")
                                if xuid in banned_xuids:
                                    reason = (
                                        banned_xuids[xuid].reason
                                        or "You have been banned from this server."
                                    )
                                    p_name = p.get("name", "Unknown")
                                    self.logger.warning(
                                        "Kicking banned player '%s' from server '%s'.",
                                        p_name,
                                        server.server_name,
                                    )
                                    try:
                                        await server.send_command(
                                            f'kick "{p_name}" {reason}'
                                        )
                                    except Exception as kick_err:
                                        log_operation_error(
                                            self.logger,
                                            "Failed to kick banned player '%s': %s",
                                            p_name,
                                            kick_err,
                                            error=kick_err,
                                        )
                    except Exception as e:
                        self._failures.report(
                            f"bans:{server_name}",
                            "Ban enforcement unavailable (%s): %s; retrying.",
                            e,
                        )
                    else:
                        self._failures.recover(f"bans:{server_name}")

                if server.players:
                    self.logger.debug(
                        "Server '%s' has %s players online. Scanning for players.",
                        server.server_name,
                        server.player_count,
                    )
                    players = await server.player_tracker.scan_log_for_players(
                        incremental=True
                    )

                    if players and self.storage is not None:
                        await self.storage.save_players(players)
                self._failures.recover(f"players:{server_name}")
            except Exception as e:
                if not observed:
                    server._runtime_state.update_server_runtime(
                        server_name, players_available=False
                    )
                self._failures.report(
                    f"players:{server_name}",
                    "Player monitoring unavailable (%s): %s; retrying.",
                    e,
                )

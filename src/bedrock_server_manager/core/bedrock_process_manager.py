# src/bedrock_server_manager/core/bedrock_process_manager.py
"""
Manages the lifecycle and monitoring of Bedrock server processes.

This module provides the :class:`~.BedrockProcessManager` class, which is responsible
for monitoring running Bedrock server instances. It detects crashes or unexpected
shutdowns and attempts to restart servers based on configuration policies.
It also handles periodic tasks like player scanning from logs.
"""
import logging
import os
import platform
import subprocess
import threading
import time
from typing import TYPE_CHECKING, Dict, Optional

from mcstatus import BedrockServer as mc

from ..config.settings import Settings
from ..context import AppContext
from ..core.system import process as core_process
from ..error import (
    BSMError,
    FileOperationError,
    ServerNotRunningError,
    ServerStartError,
)

if TYPE_CHECKING:
    from .bedrock_server import BedrockServer


class BedrockProcessManager:
    """
    Manages Bedrock server processes, including monitoring and restarting.

    The ``BedrockProcessManager`` runs a background monitoring thread that checks
    the status of registered servers at regular intervals. If a server is found
    to be stopped without being intentionally stopped (crashed), it attempts
    to restart it. It also periodically queries server status to update
    player counts and scan logs for player activity.

    Attributes:
        servers (Dict[str, BedrockServer]): A dictionary mapping server names
            to :class:`~.core.bedrock_server.BedrockServer` instances currently being managed.
        logger (logging.Logger): Logger for the process manager.
        app_context (AppContext): The application context.
        settings (Settings): The application settings.
    """

    def __init__(
        self,
        app_context: AppContext,
    ):
        """Initializes the BedrockProcessManager.

        Args:
            app_context (AppContext): The global application context, providing
                access to settings and the main manager.
        """
        self.servers: Dict[str, "BedrockServer"] = {}
        self.logger = logging.getLogger(__name__)
        self.app_context = app_context
        self.settings = self.app_context.settings
        self._shutdown_event = threading.Event()
        self.player_scan_counter = 0
        self.monitoring_thread = threading.Thread(
            target=self._monitor_servers, daemon=True
        )
        self.monitoring_thread.start()
        self.logger.info("BedrockProcessManager initialized.")

    def add_server(self, server: "BedrockServer"):
        """Adds a server to be managed by the process manager.

        Args:
            server (BedrockServer): The server instance to monitor.
        """
        self.logger.info(
            f"Adding server '{server.server_name}' to process manager for monitoring."
        )
        self.servers[server.server_name] = server

    def remove_server(self, server_name: str):
        """Removes a server from the process manager.

        This stops the manager from monitoring the server, but does not stop
        the server process itself.

        Args:
            server_name (str): The name of the server to remove.
        """
        if server_name in self.servers:
            self.logger.info(f"Removing server '{server_name}' from process manager.")
            del self.servers[server_name]

    def shutdown(self):
        """Signals the monitoring thread to shut down.

        This method sets the shutdown event, causing the background monitoring
        thread to exit its loop. It waits (up to 5 seconds) for the thread to join.
        """
        self.logger.info("Shutdown signal received. Stopping server monitoring.")
        self._shutdown_event.set()
        # Optional: wait for the thread to finish
        self.monitoring_thread.join(timeout=5)

    def _monitor_servers(self):
        """Monitors server processes and restarts them if they crash.

        This method runs in a background thread. It periodically checks:
        1. If registered servers are running. If a server has crashed (stopped
           without ``intentionally_stopped`` flag), it attempts restart.
        2. Queries server status for player counts.
        3. Scans logs for player activity if enabled.
        """
        try:
            monitoring_interval = self.settings.get(
                "SERVER_MONITORING_INTERVAL_SEC", 10
            )
            player_log_monitoring_enabled = self.settings.get(
                "server_monitoring.player_log_monitoring_enabled", True
            )
            player_log_monitoring_interval_sec = self.settings.get(
                "server_monitoring.player_log_monitoring_interval_sec", 60
            )
        except Exception:
            monitoring_interval = 10
            player_log_monitoring_enabled = True
            player_log_monitoring_interval_sec = 60

        self.logger.info(
            f"Server monitoring thread started with a {monitoring_interval} second interval."
        )

        while not self._shutdown_event.is_set():
            if self._shutdown_event.wait(timeout=monitoring_interval):
                break  # Exit if event is set

            self.player_scan_counter += monitoring_interval
            for server_name, server in list(self.servers.items()):
                if not server.is_running():
                    if not server.intentionally_stopped:
                        self.logger.warning(
                            f"Monitored server '{server.server_name}' has crashed."
                        )
                        server.failure_count += 1
                        self._try_restart_server(server)
                    else:
                        self.logger.info(
                            f"Server '{server.server_name}' was stopped intentionally. Removing from monitoring."
                        )
                        self.remove_server(server_name)
                elif (
                    player_log_monitoring_enabled
                    and self.player_scan_counter >= player_log_monitoring_interval_sec
                ):
                    try:
                        bedrock_server = mc.lookup(
                            f"127.0.0.1:{server.get_server_property('server-port')}"
                        )
                        status = bedrock_server.status()
                        server.player_count = status.players.online
                        if status.players.online > 0:
                            self.logger.info(
                                f"Server '{server.server_name}' has {status.players.online} players online. Scanning for players."
                            )
                            players = server.scan_log_for_players()
                            if players:
                                self.app_context.manager.save_player_data(players)
                    except Exception as e:
                        server.player_count = 0
                        self.logger.error(
                            f"Error pinging server '{server.server_name}': {e}"
                        )
            if self.player_scan_counter >= player_log_monitoring_interval_sec:
                self.player_scan_counter = 0

    def _try_restart_server(self, server: "BedrockServer"):
        """Tries to restart a crashed server.

        Checks the restart retry limit before attempting to restart. If the
        limit is reached, marks the server status as 'ERROR' and stops monitoring.

        Args:
            server (BedrockServer): The server instance to restart.
        """
        max_retries = self.settings.get("SERVER_MAX_RESTART_RETRIES", 3)

        if server.failure_count > max_retries:
            self.logger.critical(
                f"Server '{server.server_name}' has reached the maximum restart limit of {max_retries}. Will not attempt to restart again."
            )
            self.write_error_status(server.server_name)
            self.remove_server(server.server_name)  # Stop monitoring
            return

        self.logger.info(
            f"Attempting to restart server '{server.server_name}'. Attempt {server.failure_count}/{max_retries}."
        )
        try:
            server.start()
            self.logger.info(f"Server '{server.server_name}' restarted successfully.")
        except ServerStartError as e:
            self.logger.critical(
                f"Failed to restart server '{server.server_name}': {e}", exc_info=True
            )
            time.sleep(5)

    def write_error_status(self, server_name: str):
        """Writes 'ERROR' to server config status.

        Args:
            server_name (str): The name of the server.

        Raises:
            FileOperationError: If writing to the config file fails.
        """
        server = self.app_context.get_server(server_name)
        try:
            server.set_status_in_config("ERROR")
        except BSMError as e:
            self.logger.error(f"Error writing status for server '{server_name}': {e}")
            raise FileOperationError(
                f"Failed to write status for server '{server_name}'."
            )

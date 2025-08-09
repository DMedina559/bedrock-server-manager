# src/bedrock_server_manager/core/bedrock_process_manager.py
import os
import platform
import subprocess
import threading
import time
import logging
from typing import Dict, Optional

from ..core.system import process as core_process
from ..error import (
    BSMError,
    ServerNotRunningError,
    ServerStartError,
    FileOperationError,
)
from ..config.settings import Settings
from ..context import AppContext
from ..instances import get_server_instance, get_settings_instance


class BedrockProcessManager:
    """
    Manages Bedrock server processes, including starting, stopping, and monitoring.
    """

    def __init__(
        self,
        settings_instance: Optional[Settings] = None,
        app_context: Optional[AppContext] = None,
    ):
        """Initializes the BedrockProcessManager."""
        self.servers: Dict[str, subprocess.Popen] = {}
        self.intentionally_stopped: Dict[str, bool] = {}
        self.failure_counts: Dict[str, int] = {}
        self.start_times: Dict[str, float] = {}
        self.logger = logging.getLogger(__name__)
        self.app_context = app_context

        if self.app_context:
            self.settings = self.app_context.settings
        elif settings_instance:
            self.settings = settings_instance
        else:
            self.settings = get_settings_instance()

        self.monitoring_thread = threading.Thread(
            target=self._monitor_servers, daemon=True
        )
        self.monitoring_thread.start()
        self.logger.info("BedrockProcessManager initialized.")

    def add_server(self, server_name: str, process: subprocess.Popen):
        """
        Adds a server to be managed by the process manager.

        Args:
            server_name (str): The name of the server.
            process (subprocess.Popen): The server's process object.
        """
        self.logger.info(f"Adding server '{server_name}' to process manager.")
        self.servers[server_name] = process
        self.intentionally_stopped[server_name] = False
        self.start_times[server_name] = time.time()
        # Do not reset failure count here, only after a successful start

    def start_server(self, server_name: str):
        """
        Starts a Bedrock server.

        Args:
            server_name (str): The name of the server to start.

        Raises:
            ServerStartError: If the server is already running or fails to start.
        """
        self.logger.info(f"Attempting to start server '{server_name}'.")
        if server_name in self.servers and self.servers[server_name].poll() is None:
            self.logger.warning(f"Server '{server_name}' is already running.")
            raise ServerStartError(f"Server '{server_name}' is already running.")

        if self.app_context:
            server = self.app_context.get_server(server_name)
        else:
            server = get_server_instance(server_name, self.settings)
        output_file = os.path.join(server.server_dir, "server_output.txt")
        pid_file_path = server.get_pid_file_path()

        try:
            with open(output_file, "ab") as f:
                process = subprocess.Popen(
                    [server.bedrock_executable_path],
                    cwd=server.server_dir,
                    stdin=subprocess.PIPE,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW if platform == "Windows" else 0
                    ),
                )

            core_process.write_pid_to_file(pid_file_path, process.pid)
            self.add_server(server_name, process)
            self.logger.info(
                f"Server '{server_name}' started successfully with PID {process.pid}."
            )
            return process
        except FileNotFoundError:
            self.logger.error(
                f"Executable not found for server '{server_name}' at path '{server.bedrock_executable_path}'."
            )
            raise ServerStartError(f"Executable not found for server '{server_name}'.")
        except Exception as e:
            self.logger.error(
                f"Failed to start server '{server_name}': {e}", exc_info=True
            )
            raise ServerStartError(f"Failed to start server '{server_name}': {e}")

    def stop_server(self, server_name: str):
        """
        Stops a Bedrock server.

        Args:
            server_name (str): The name of the server to stop.

        Raises:
            ServerNotRunningError: If the server is not running.
        """
        self.logger.info(f"Attempting to stop server '{server_name}'.")
        if (
            server_name not in self.servers
            or self.servers[server_name].poll() is not None
        ):
            self.logger.warning(
                f"Attempted to stop server '{server_name}', but it was not running."
            )
            raise ServerNotRunningError(f"Server '{server_name}' is not running.")

        process = self.servers[server_name]
        try:
            self.logger.info(f"Sending 'stop' command to server '{server_name}'.")
            process.stdin.write(b"stop\n")
            process.stdin.flush()
            timeout = self.settings.get("SERVER_STOP_TIMEOUT_SEC", 60)
            process.wait(timeout=timeout)
            self.logger.info(f"Server '{server_name}' stopped gracefully.")
        except subprocess.TimeoutExpired:
            self.logger.warning(
                f"Server '{server_name}' did not stop gracefully within the timeout. Killing process."
            )
            process.kill()
        except Exception as e:
            self.logger.error(
                f"An error occurred while stopping server '{server_name}': {e}",
                exc_info=True,
            )
            process.kill()  # Ensure process is terminated even if other errors occur

        del self.servers[server_name]
        self.intentionally_stopped[server_name] = True
        self.logger.info(
            f"Server '{server_name}' has been marked as intentionally stopped."
        )

    def send_command(self, server_name: str, command: str):
        """
        Sends a command to a running Bedrock server.

        Args:
            server_name (str): The name of the server.
            command (str): The command to send.

        Raises:
            ServerNotRunningError: If the server is not running.
        """
        if (
            server_name not in self.servers
            or self.servers[server_name].poll() is not None
        ):
            self.logger.warning(
                f"Cannot send command to '{server_name}'; server is not running."
            )
            raise ServerNotRunningError(f"Server '{server_name}' is not running.")

        self.logger.info(f"Sending command '{command}' to server '{server_name}'.")
        process = self.servers[server_name]
        process.stdin.write(f"{command}\n".encode())
        process.stdin.flush()

    def get_server_process(self, server_name: str) -> Optional[subprocess.Popen]:
        """
        Gets the process object for a running server.

        Args:
            server_name (str): The name of the server.

        Returns:
            Optional[subprocess.Popen]: The server's process object, or None if not found.
        """
        return self.servers.get(server_name)

    def _monitor_servers(self):
        """Monitors server processes and restarts them if they crash."""
        try:
            monitoring_interval = self.settings.get(
                "SERVER_MONITORING_INTERVAL_SEC", 10
            )
        except Exception:
            monitoring_interval = 10

        self.logger.info(
            f"Server monitoring thread started with a {monitoring_interval} second interval."
        )
        while True:
            time.sleep(monitoring_interval)
            for server_name, process in list(self.servers.items()):
                if process.poll() is not None:
                    # Server has terminated
                    if not self.intentionally_stopped.get(server_name, False):
                        self.logger.warning(
                            f"Server '{server_name}' (PID: {process.pid}) has crashed with exit code {process.returncode}."
                        )
                        self.failure_counts[server_name] = (
                            self.failure_counts.get(server_name, 0) + 1
                        )
                        del self.servers[server_name]
                        self._try_restart_server(server_name)
                    else:
                        # Server was stopped intentionally
                        self.logger.info(
                            f"Server '{server_name}' was stopped intentionally. Removing from monitoring."
                        )
                        del self.intentionally_stopped[server_name]

    def _try_restart_server(self, server_name: str):
        """
        Tries to restart a crashed server.

        Args:
            server_name (str): The name of the server to restart.
        """
        max_retries = self.settings.get("SERVER_MAX_RESTART_RETRIES", 3)
        failure_count = self.failure_counts.get(server_name, 0)

        if failure_count >= max_retries:
            self.logger.critical(
                f"Server '{server_name}' has reached the maximum restart limit of {max_retries}. Will not attempt to restart again."
            )
            self.write_error_status(server_name)
            return

        self.logger.info(
            f"Attempting to restart server '{server_name}'. Attempt {failure_count}/{max_retries}."
        )
        try:
            self.start_server(server_name)
            self.logger.info(f"Server '{server_name}' restarted successfully.")
        except ServerStartError as e:
            self.logger.critical(
                f"Failed to restart server '{server_name}': {e}", exc_info=True
            )
            time.sleep(5)

    def reset_failure_count(self, server_name: str):
        """
        Resets the failure count for a server.

        Args:
            server_name (str): The name of the server.
        """
        if server_name in self.failure_counts:
            self.logger.info(f"Resetting failure count for server '{server_name}'.")
            self.failure_counts[server_name] = 0

    def write_error_status(self, server_name: str):
        """
        Wites 'ERROR' to server config status.

        Args:
            server_name (str): The name of the server to start.

        Raises:
            ServerStartError: If the server is already running or fails to start.
        """
        if self.app_context:
            server = self.app_context.get_server(server_name)
        else:
            server = get_server_instance(server_name, self.settings)

        try:
            server.set_status_in_config("ERROR")
        except BSMError:
            self.logger.error(f"Error writing status for server '{server_name}'.")
            raise FileOperationError(
                f"Failed to write status for server '{server_name}'."
            )
        except Exception as e:
            self.logger.error(
                f"Failed to write status for server '{server_name}': {e}", exc_info=True
            )
            raise ServerStartError(
                f"Failed to write status for server '{server_name}': {e}"
            )

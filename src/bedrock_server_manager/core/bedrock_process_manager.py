# src/bedrock_server_manager/core/bedrock_process_manager.py
import os
import platform
import subprocess
import threading
import time
from typing import Dict, Optional

from ..core.system import process as core_process
from ..error import ServerNotRunningError, ServerStartError
from ..instances import get_server_instance, get_settings_instance


class BedrockProcessManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(BedrockProcessManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.servers: Dict[str, subprocess.Popen] = {}
            self.intentionally_stopped: Dict[str, bool] = {}
            self.failure_counts: Dict[str, int] = {}
            self.monitoring_thread = threading.Thread(
                target=self._monitor_servers, daemon=True
            )
            self.monitoring_thread.start()
            self.initialized = True

    def start_server(self, server_name: str):
        if server_name in self.servers and self.servers[server_name].poll() is None:
            raise ServerStartError(f"Server '{server_name}' is already running.")

        server = get_server_instance(server_name)
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
            self.servers[server_name] = process
            self.intentionally_stopped[server_name] = False
            return process
        except FileNotFoundError:
            raise ServerStartError(f"Executable not found for server '{server_name}'.")
        except Exception as e:
            raise ServerStartError(f"Failed to start server '{server_name}': {e}")

    def stop_server(self, server_name: str):
        if (
            server_name not in self.servers
            or self.servers[server_name].poll() is not None
        ):
            raise ServerNotRunningError(f"Server '{server_name}' is not running.")

        process = self.servers[server_name]
        process.stdin.write(b"stop\n")
        process.stdin.flush()
        try:
            process.wait(
                timeout=get_settings_instance().get("SERVER_STOP_TIMEOUT_SEC", 60)
            )
        except subprocess.TimeoutExpired:
            process.kill()

        del self.servers[server_name]
        self.intentionally_stopped[server_name] = True

    def send_command(self, server_name: str, command: str):
        if (
            server_name not in self.servers
            or self.servers[server_name].poll() is not None
        ):
            raise ServerNotRunningError(f"Server '{server_name}' is not running.")

        process = self.servers[server_name]
        process.stdin.write(f"{command}\n".encode())
        process.stdin.flush()

    def get_server_process(self, server_name: str) -> Optional[subprocess.Popen]:
        return self.servers.get(server_name)

    def _monitor_servers(self):
        monitoring_interval = get_settings_instance().get(
            "SERVER_MONITORING_INTERVAL_SEC", 10
        )
        while True:
            time.sleep(monitoring_interval)
            for server_name, process in list(self.servers.items()):
                if process.poll() is not None:
                    # Server has crashed
                    if not self.intentionally_stopped.get(server_name, False):
                        self.failure_counts[server_name] = (
                            self.failure_counts.get(server_name, 0) + 1
                        )
                        del self.servers[server_name]
                        self._try_restart_server(server_name)
                    else:
                        # Server was stopped intentionally, so we can remove it from the tracking dict
                        del self.intentionally_stopped[server_name]

    def _try_restart_server(self, server_name: str):
        max_retries = get_settings_instance().get("SERVER_MAX_RESTART_RETRIES", 3)
        failure_count = self.failure_counts.get(server_name, 0)

        if failure_count >= max_retries:
            return

        try:
            self.start_server(server_name)
            self.failure_counts[server_name] = 0  # Reset on success
        except ServerStartError as e:
            time.sleep(5)


def get_bedrock_process_manager() -> BedrockProcessManager:
    return BedrockProcessManager()

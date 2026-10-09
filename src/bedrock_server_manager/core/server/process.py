"""Bedrock process component."""

import asyncio
import inspect
import logging
import platform
import subprocess
from io import BufferedWriter
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union, cast

import aiofiles
import aiofiles.ospath

from ...error import (
    BSMError,
    MissingArgumentError,
    SendCommandError,
    ServerNotRunningError,
    ServerStartError,
    ServerStopError,
)
from ...logging import log_operation_error
from ...utils.threads import run_in_thread
from ..data import ProcessRecord
from ..system import base as system_base
from ..system import process as system_process

if TYPE_CHECKING:
    import psutil

    from ..bedrock_server import BedrockServer


class ServerProcess:
    """Process operations for one Bedrock server."""

    def __init__(self, server: "BedrockServer") -> None:
        self.server = server
        self.logger = logging.LoggerAdapter(
            logging.getLogger(__name__), {"server_name": server.server_name}
        )
        self._process: Optional[
            Union[subprocess.Popen[Any], asyncio.subprocess.Process, "psutil.Process"]
        ] = None
        self.intentionally_stopped = True
        self._log_file_handle: BufferedWriter | None = None
        self._resource_monitor = system_base.ResourceMonitor()

    _process: Optional[
        Union[subprocess.Popen[Any], asyncio.subprocess.Process, "psutil.Process"]
    ]
    intentionally_stopped: bool
    failure_count: int
    _log_file_handle: BufferedWriter | None

    async def is_running(self) -> bool:
        """Checks if the Bedrock server process is currently running and verified asynchronously."""
        self.logger.debug(
            "Checking if server '%s' is running.", self.server.server_name
        )
        if (
            self._process is not None
            and hasattr(self._process, "poll")
            and (self._process.poll() is None)
        ):
            return self._publish_running(True)
        elif (
            self._process is not None
            and hasattr(self._process, "is_running")
            and self._process.is_running()
        ):
            return self._publish_running(True)
        elif (
            self._process is not None
            and hasattr(self._process, "returncode")
            and (self._process.returncode is None)
        ):
            return self._publish_running(True)
        running = await system_base.is_server_running(
            self.server.server_name,
            self.server.paths.server_dir,
            self.server.paths.app_config_dir,
        )
        self._process = None
        if running:
            self._process = await system_process.get_verified_bedrock_process(
                self.server.server_name,
                self.server.paths.server_dir,
                self.server.paths.app_config_dir,
            )
        return self._publish_running(running)

    async def send_command(self, command: str) -> None:
        """Sends a command string to the running Bedrock server process asynchronously."""
        if not command:
            raise MissingArgumentError("Command cannot be empty.")
        if not await self.is_running():
            raise ServerNotRunningError(
                f"Cannot send command: Server '{self.server.server_name}' is not running."
            )
        if self._process is None or self._process.stdin is None:
            raise SendCommandError(
                f"Cannot send command to '{self.server.server_name}': no process handle or stdin."
            )
        self.logger.debug("Sending command to server '%s'.", self.server.server_name)
        try:
            if hasattr(self._process.stdin, "drain"):
                self._process.stdin.write(f"{command}\n".encode())
                await self._process.stdin.drain()
            else:

                def _write_stdin():
                    self._process.stdin.write(f"{command}\n".encode())
                    self._process.stdin.flush()

                await run_in_thread(_write_stdin)
            self.logger.debug(
                "Command delivered to server '%s'.", self.server.server_name
            )
        except Exception as e_unexp:
            raise SendCommandError(
                f"An unexpected error occurred while sending command to '{self.server.server_name}': {e_unexp}"
            ) from e_unexp

    async def start(self) -> None:
        """Starts the Bedrock server process asynchronously."""
        async with self.server.operation_lock:
            is_inst = await self.server.is_installed()
            if not is_inst:
                raise ServerStartError(
                    f"Cannot start server '{self.server.server_name}': Not installed or invalid installation at {self.server.paths.server_dir} (is_installed check failed or method missing)."
                )
            if await self.is_running():
                self.logger.debug(
                    "Attempted to start server '%s' but it is already running.",
                    self.server.server_name,
                )
                raise ServerStartError(
                    f"Server '{self.server.server_name}' is already running."
                )
            try:
                await self.server.set_status_in_config("STARTING")
            except Exception as e_status:
                self.logger.warning(
                    "Failed to set status to STARTING for '%s': %s",
                    self.server.server_name,
                    e_status,
                )
            self.logger.debug(
                "Attempting to start server '%s'...", self.server.server_name
            )
            output_file = self.server.paths.server_log_path
            pid_file_path = self.server.get_pid_file_path()
            if await aiofiles.ospath.exists(pid_file_path):
                self.logger.error(
                    "Attempted to start server '%s', but a PID file already exists at '%s'.",
                    self.server.server_name,
                    pid_file_path,
                )
                raise ServerStartError(
                    f"Server '{self.server.server_name}' has a stale PID file."
                )
            try:
                async with aiofiles.open(output_file, "w") as f:
                    await f.truncate(0)
                self._log_file_handle = open(output_file, "ab")
                spawn = asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        self.server.paths.bedrock_executable_path,
                        cwd=self.server.paths.server_dir,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=self._log_file_handle,
                        stderr=asyncio.subprocess.STDOUT,
                        creationflags=(
                            getattr(subprocess, "CREATE_NO_WINDOW", 134217728)
                            if platform.system() == "Windows"
                            else 0
                        ),
                    )
                )
                try:
                    self._process = await asyncio.shield(spawn)
                except asyncio.CancelledError:
                    while not spawn.done():
                        try:
                            await asyncio.shield(spawn)
                        except asyncio.CancelledError:
                            continue
                    self._process = spawn.result()
                    raise
                await system_process.write_pid_to_file(pid_file_path, self._process.pid)
                self._publish_running(True)
                self.intentionally_stopped = False
                setattr(self.server, "players", [])
                self.server.player_tracker.reset()
                await self.server.set_status_in_config("RUNNING")
                self.logger.info(
                    "Server '%s' started (PID %s).",
                    self.server.server_name,
                    self._process.pid,
                )
            except asyncio.CancelledError:
                await self._rollback_start()
                raise
            except FileNotFoundError:
                await self._rollback_start()
                await self.server.set_status_in_config("ERROR")
                self.logger.error(
                    "Executable not found for server '%s' at path '%s'.",
                    self.server.server_name,
                    self.server.paths.bedrock_executable_path,
                )
                raise ServerStartError(
                    f"Executable not found for server '{self.server.server_name}'."
                )
            except Exception as e:
                await self._rollback_start()
                await self.server.set_status_in_config("ERROR")
                log_operation_error(
                    self.logger,
                    "Failed to start server '%s': %s",
                    self.server.server_name,
                    e,
                    error=e,
                )
                raise ServerStartError(
                    f"Failed to start server '{self.server.server_name}': {e}"
                )

    async def _rollback_start(self) -> None:
        """Release resources acquired by a startup that did not complete."""
        process = self._process
        try:
            if process is not None:
                try:
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
                    if inspect.iscoroutinefunction(process.wait):
                        await asyncio.wait_for(process.wait(), timeout=5)
                    else:
                        await run_in_thread(
                            cast(Callable[[float], int], process.wait), 5
                        )
                except Exception:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    if inspect.iscoroutinefunction(process.wait):
                        await asyncio.wait_for(process.wait(), timeout=5)
                    else:
                        await run_in_thread(
                            cast(Callable[[float], int], process.wait), 5
                        )
            self._process = None
        finally:
            if self._log_file_handle is not None:
                self._log_file_handle.close()
                self._log_file_handle = None
        self.intentionally_stopped = True
        self._publish_running(False)
        await system_process.remove_pid_file_if_exists(self.server.get_pid_file_path())

    async def stop(self) -> None:
        """Stops the Bedrock server process gracefully, with a forceful fallback asynchronously."""
        async with self.server.operation_lock:
            self.intentionally_stopped = True
            if not await self.is_running():
                self.logger.debug(
                    "Attempted to stop server '%s', but it is not currently running.",
                    self.server.server_name,
                )
                status = await self.server.get_status_from_config()
                if status != "STOPPED":
                    try:
                        await self.server.set_status_in_config("STOPPED")
                    except Exception as e_stat:
                        self.logger.warning(
                            "Failed to reset status to STOPPED for '%s': %s",
                            self.server.server_name,
                            e_stat,
                        )
                return
            if self._process is None:
                verified_process = await system_process.get_verified_bedrock_process(
                    self.server.server_name,
                    self.server.paths.server_dir,
                    self.server.paths.app_config_dir,
                )
                if verified_process:
                    self._process = verified_process
                else:
                    raise ServerStopError(
                        f"Cannot stop server '{self.server.server_name}': process handle not found and could not be verified."
                    )
            try:
                await self.server.set_status_in_config("STOPPING")
            except Exception as e_stat:
                self.logger.warning(
                    "Failed to set status to STOPPING for '%s': %s",
                    self.server.server_name,
                    e_stat,
                )
            self.logger.debug(
                "Attempting to stop server '%s'...", self.server.server_name
            )
            try:
                self.logger.debug(
                    "Sending 'stop' command to server '%s'.", self.server.server_name
                )
                if hasattr(self._process, "stdin") and self._process.stdin:
                    if hasattr(self._process.stdin, "drain"):
                        self._process.stdin.write(b"stop\n")
                        await self._process.stdin.drain()
                    else:

                        def _write_stop():
                            self._process.stdin.write(b"stop\n")
                            self._process.stdin.flush()

                        await run_in_thread(_write_stop)
                elif isinstance(self._process, system_process.psutil.Process):
                    self.logger.debug(
                        "Cannot write to stdin of recovered psutil process '%s'. Sending terminate signal.",
                        self.server.server_name,
                    )
                    self._process.terminate()
                timeout = int(
                    self.server.settings.get("monitor.server_stop_timeout", 10)
                )
                if hasattr(self._process, "wait") and inspect.iscoroutinefunction(
                    self._process.wait
                ):
                    try:
                        await asyncio.wait_for(self._process.wait(), timeout=timeout)
                    except asyncio.TimeoutError:
                        raise subprocess.TimeoutExpired(
                            getattr(
                                self._process,
                                "args",
                                getattr(self._process, "_args", ["bedrock_server"]),
                            ),
                            timeout,
                        )
                elif hasattr(self._process, "wait"):

                    def _wait() -> None:
                        if self._process is not None:
                            cast(Callable[..., None], self._process.wait)(
                                timeout=timeout
                            )

                    await run_in_thread(_wait)
                self.logger.debug(
                    "Server '%s' stopped gracefully.", self.server.server_name
                )
            except (subprocess.TimeoutExpired, OSError, BrokenPipeError) as e:
                self.logger.warning(
                    "Server '%s' did not stop gracefully or pipe was already closed. Killing process. Error: %s",
                    self.server.server_name,
                    e,
                )
                if self._process is not None:
                    self._process.kill()
            except system_process.psutil.TimeoutExpired as e:
                self.logger.warning(
                    "Server '%s' psutil process did not stop gracefully. Killing process. Error: %s",
                    self.server.server_name,
                    e,
                )
                if self._process is not None:
                    self._process.kill()
            except Exception as e:
                log_operation_error(
                    self.logger,
                    "An error occurred while stopping server '%s': %s",
                    self.server.server_name,
                    e,
                    error=e,
                )
                try:
                    if self._process is not None:
                        self._process.kill()
                except Exception as kill_e:
                    log_operation_error(
                        self.logger,
                        "Failed to kill process after error: %s",
                        kill_e,
                        error=kill_e,
                    )
            finally:
                if (
                    hasattr(self, "_log_file_handle")
                    and self._log_file_handle is not None
                ):
                    try:
                        self._log_file_handle.close()
                    except Exception as close_e:
                        self.logger.warning(
                            "Failed to close log file handle: %s", close_e
                        )
                    self._log_file_handle = None
            self._process = None
            self._publish_running(False)
            pid_file_path = self.server.get_pid_file_path()
            await system_process.remove_pid_file_if_exists(pid_file_path)
            await self.server.set_status_in_config("STOPPED")
            setattr(self.server, "players", [])
            self.server.player_tracker.reset()
            self.logger.info("Server '%s' stopped.", self.server.server_name)

    async def get_process_info(self) -> Optional[Dict[str, Any]]:
        """Gets resource usage information (PID, CPU, Memory, Uptime) for the running server process asynchronously.

        This method first uses
        :func:`~.core.system.process.get_verified_bedrock_process` to locate and
        verify the Bedrock server process associated with this server instance.
        If a valid process is found, it then uses the :attr:`._resource_monitor`
        (an instance of :class:`~.core.system.base.ResourceMonitor` from the base
        mixin) to calculate its current resource statistics.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing process information
            if the server is running, verified, and ``psutil`` is available.
            The dictionary has keys: "pid", "cpu_percent", "memory_mb", "uptime".
            Returns ``None`` if the server is not running, cannot be verified,
            ``psutil`` is unavailable, or if an error occurs during statistics retrieval.
            Example: ``{"pid": 1234, "cpu_percent": 15.2, "memory_mb": 256.5, "uptime": "0:10:30"}``
        """
        try:
            process_obj = await system_process.get_verified_bedrock_process(
                self.server.server_name,
                self.server.paths.server_dir,
                self.server.paths.app_config_dir,
            )
            if process_obj is None:
                self.logger.debug(
                    "No verified process found for server '%s' to get info.",
                    self.server.server_name,
                )
                await self.is_running()
                return None
            data = await run_in_thread(self._resource_monitor.get_stats, process_obj)
            if data is None:
                return None
            record = ProcessRecord.model_validate(data)
            self.server._runtime_state.update_server_runtime(
                self.server.server_name,
                running=True,
                pid=record.pid,
                cpu_percent=record.cpu_percent,
                memory_mb=record.memory_mb,
            )
            return record.model_dump(mode="json")
        except BSMError as e_bsm:
            self.logger.warning(
                "Known error while trying to get process info for '%s': %s",
                self.server.server_name,
                e_bsm,
            )
            return None
        except Exception as e_unexp:
            log_operation_error(
                self.logger,
                "Unexpected error getting process info for '%s': %s",
                self.server.server_name,
                e_unexp,
                error=e_unexp,
            )
            return None

    def _publish_running(self, running: bool) -> bool:
        process = self._process
        pid = getattr(process, "pid", None)
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            pid = None
        self.server._runtime_state.update_server_runtime(
            self.server.server_name, running=running, pid=pid
        )
        return running

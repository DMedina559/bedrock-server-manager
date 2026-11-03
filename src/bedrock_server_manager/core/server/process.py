"""Bedrock process component."""

import asyncio
import contextlib
import json
import logging
import os
import platform
import subprocess
import time
from io import BufferedWriter
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union

import aiofiles
import aiofiles.os
import aiofiles.ospath

from ...error import (
    DependencyUnavailableError,
    SendCommandError,
    ServerNotRunningError,
    ServerStartError,
    ServerStopError,
)
from ...logging import log_operation_error, prepare_server_log_path
from ...utils.threads import run_in_thread
from ..data import ProcessRecord
from ..system import base as system_base
from ..system import process as system_process
from .runtime import OwnedBDSRun, validate_command

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
        self._process: Optional[Union[asyncio.subprocess.Process, "psutil.Process"]] = (
            None
        )
        self._run: OwnedBDSRun | None = None
        self._draining_runs: set[OwnedBDSRun] = set()
        self.on_exit: Callable[[], None] | None = None
        self.intentionally_stopped = True
        self._recovery_state = system_process.ProcessRecoveryState()
        self._log_file_handle: BufferedWriter | None = None
        self._resource_monitor = system_base.ProcessResourceMonitor()
        self._sample_lock = asyncio.Lock()
        self._sampled_at = 0.0
        self._sample_identity: tuple[object, object] | None = None
        self._sample_cache: dict[str, Any] | None = None

    _process: Optional[Union[asyncio.subprocess.Process, "psutil.Process"]]
    intentionally_stopped: bool
    failure_count: int
    _log_file_handle: BufferedWriter | None

    async def is_running(self, *, force_scan: bool = False) -> bool:
        """Check if the Bedrock server process is currently running and verified
        asynchronously.
        """
        self.logger.debug(
            "Checking if server '%s' is running.", self.server.server_name
        )
        process = self._process
        if isinstance(process, asyncio.subprocess.Process):
            if process.returncode is None:
                return self._publish_running(True)
            if self._run is not None and self._run.process is process:
                self._run.ready = False
                self._run.phase = "ERROR" if self._run.failure else "STOPPED"
                self._run.publish()
                return False
        elif isinstance(process, system_process.psutil.Process):
            try:
                running = await run_in_thread(
                    lambda: process.is_running()
                    and process.status() != system_process.psutil.STATUS_ZOMBIE
                )
            except system_process.psutil.NoSuchProcess:
                running = False
            if self._process is not process:
                return await self.is_running(force_scan=force_scan)
            if running:
                return self._publish_running(True)
        # Probes do not hold operation_lock: discard results from before a
        # concurrent start or another probe installed a different handle.
        observed_process = self._process
        scan_interval = self.server.settings.get(
            "monitoring.untracked_process_interval_sec", 5
        )
        recover = self.server.settings.get(
            "monitoring.recover_untracked_processes", True
        )
        verified_process = await system_process.get_verified_bedrock_process(
            self.server.server_name,
            self.server.paths.server_dir,
            self.server.paths.app_config_dir,
            scan_interval_sec=float(scan_interval),
            recover_untracked=bool(recover),
            recovery_state=self._recovery_state,
            force_scan=force_scan,
        )
        if self._process is not observed_process:
            return await self.is_running(force_scan=force_scan)
        self._process = verified_process
        return self._publish_running(verified_process is not None)

    @property
    def run(self) -> OwnedBDSRun | None:
        return (
            self._run
            if self._run is not None and self._process is self._run.process
            else None
        )

    @property
    def log_path(self) -> str:
        return (
            self._run.log_path
            if self._run is not None
            else self.server.paths.server_log_path
        )

    async def send_command(self, command: str) -> None:
        validate_command(command)
        run = self._run
        if run is None or not run.current():
            if not await self.is_running():
                raise ServerNotRunningError(
                    f"Server '{self.server.server_name}' is not running."
                )
            raise SendCommandError(
                "Recovered process has no console command channel; stop/start it to restore ownership."
            )
        await run.send(command)

    def _record_path(self) -> str:
        return self.server.get_pid_file_path() + ".json"

    def _finish_run(self, run: OwnedBDSRun) -> None:
        if self._run is not run:
            return
        self._run = None
        self._process = None
        self._log_file_handle = None
        self._draining_runs.add(run)

        task = asyncio.create_task(
            self._remove_identity(run), name="bds-identity-cleanup"
        )
        run.tasks.append(task)
        if self.on_exit is not None:
            self.on_exit()

    async def _remove_identity(self, run: OwnedBDSRun) -> None:
        def remove() -> None:
            try:
                with open(self._record_path(), encoding="utf-8") as file:
                    record = json.load(file)
                if record.get("generation") != run.generation:
                    return
                os.remove(self._record_path())
                with contextlib.suppress(FileNotFoundError):
                    os.remove(self.server.get_pid_file_path())
            except (FileNotFoundError, ValueError):
                return

        await run_in_thread(remove)

    async def drain(self) -> None:
        for run in list(self._draining_runs):
            results = await asyncio.gather(*run.tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    raise result
            if run.exit_task is not None:
                await asyncio.shield(run.exit_task)
            for task in (run._stop_task, run._failure_task):
                if task is not None:
                    await asyncio.gather(task, return_exceptions=True)
            self._draining_runs.discard(run)

    async def start(self) -> None:
        """Start the Bedrock server process asynchronously."""
        async with self.server.operation_lock:
            from ...backups.recovery import RestoreJournal

            await run_in_thread(RestoreJournal(self.server).ensure_clear)
            is_inst = await self.server.is_installed()
            if not is_inst:
                raise ServerStartError(
                    f"Cannot start server '{self.server.server_name}': Not installed or invalid installation at {self.server.paths.server_dir} (is_installed check failed or method missing)."
                )
            if await self.is_running(force_scan=True):
                self.logger.debug(
                    "Attempted to start server '%s' but it is already running.",
                    self.server.server_name,
                )
                raise ServerStartError(
                    f"Server '{self.server.server_name}' is already running."
                )
            if self._run is not None:
                await asyncio.shield(self._run.closed.wait())
            await self.drain()
            try:
                await self.server.set_status_in_config("STARTING")
            except Exception as e_status:
                self.logger.warning(
                    "Failed to set status to STARTING for '%s': %s",
                    self.server.server_name,
                    e_status,
                    exc_info=True,
                )
            self.logger.debug(
                "Attempting to start server '%s'...", self.server.server_name
            )
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
            started_process = None
            try:
                output_file = await run_in_thread(
                    prepare_server_log_path,
                    self.server.paths.server_log_dir,
                    self.server.server_name,
                )
                async with aiofiles.open(output_file, "w") as f:
                    await f.truncate(0)
                self._log_file_handle = await run_in_thread(open, output_file, "ab")
                spawn = asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        self.server.paths.bedrock_executable_path,
                        cwd=self.server.paths.server_dir,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                        creationflags=(
                            getattr(subprocess, "CREATE_NO_WINDOW", 134217728)
                            if platform.system() == "Windows"
                            else 0
                        ),
                    )
                )
                try:
                    started_process = await asyncio.shield(spawn)
                    self._process = started_process
                    self._run = OwnedBDSRun(
                        self.server,
                        started_process,
                        output_file,
                        self._log_file_handle,
                        self._finish_run,
                    )
                    self.intentionally_stopped = False
                    self._run.start()
                except asyncio.CancelledError:
                    while not spawn.done():
                        try:
                            await asyncio.shield(spawn)
                        except asyncio.CancelledError:
                            continue
                    started_process = spawn.result()
                    self._process = started_process
                    self._run = OwnedBDSRun(
                        self.server,
                        started_process,
                        output_file,
                        self._log_file_handle,
                        self._finish_run,
                    )
                    self._run.start()
                    raise
                run = self._run
                if run is None or started_process.returncode is not None:
                    raise ServerStartError("BDS exited before startup publication.")
                created_at = await run_in_thread(
                    lambda: system_process.psutil.Process(
                        started_process.pid
                    ).create_time()
                )

                await system_process.write_process_record(
                    self._record_path(),
                    {
                        "generation": run.generation,
                        "pid": started_process.pid,
                        "created_at": created_at,
                        "executable": self.server.paths.bedrock_executable_path,
                        "cwd": self.server.paths.server_dir,
                        "log_path": output_file,
                    },
                )
                await system_process.write_pid_to_file(
                    pid_file_path, started_process.pid
                )
                if self._run is not run or started_process.returncode is not None:
                    raise ServerStartError("BDS exited during startup publication.")
                self._recovery_state.clear()
                self._publish_running(True)
                self.intentionally_stopped = False
                self.server.player_tracker.reset()
                self.logger.info(
                    "Server '%s' started (PID %s).",
                    self.server.server_name,
                    started_process.pid,
                )
            except asyncio.CancelledError:
                await self._rollback_start(started_process)
                raise
            except FileNotFoundError as error:
                await self._rollback_start(started_process)
                await self.server.set_status_in_config("ERROR")
                if started_process is not None:
                    raise ServerStartError(
                        "A required startup resource became unavailable."
                    ) from error
                self.logger.error(
                    "Executable not found for server '%s'.", self.server.server_name
                )
                raise ServerStartError(
                    f"Executable not found for server '{self.server.server_name}'."
                ) from error
            except Exception as e:
                await self._rollback_start(started_process)
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

    async def _rollback_start(self, process: asyncio.subprocess.Process | None) -> None:
        """Release resources acquired by a startup that did not complete."""
        run = self._run or next(
            (item for item in self._draining_runs if item.process is process), None
        )
        if run is not None and run.process is process:
            self.intentionally_stopped = True
            cleanup = asyncio.create_task(run.stop(), name="bds-startup-rollback")
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    continue
            cleanup.result()
            await self._remove_identity(run)
        else:
            if process is not None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                await asyncio.wait_for(process.wait(), 5)
            if self._log_file_handle is not None:
                await run_in_thread(self._log_file_handle.close)
                self._log_file_handle = None
            self._process = None
        self.intentionally_stopped = True
        await system_process.remove_pid_file_if_exists(self.server.get_pid_file_path())
        if self._run is None:
            self._publish_running(False)

    async def _wait_for_exit(
        self,
        process: Union[asyncio.subprocess.Process, "psutil.Process"],
        timeout: float,
    ) -> None:
        try:
            async with asyncio.timeout(timeout):
                if isinstance(process, asyncio.subprocess.Process):
                    await process.wait()
                else:
                    # A PID recovered after BSM restart is not our asyncio child.
                    # Poll without a blocking psutil.wait or a worker held until exit.
                    while await run_in_thread(process.is_running):
                        if (
                            await run_in_thread(process.status)
                            == system_process.psutil.STATUS_ZOMBIE
                        ):
                            break
                        await asyncio.sleep(0.1)
        except (ProcessLookupError, system_process.psutil.NoSuchProcess):
            return
        if (
            isinstance(process, asyncio.subprocess.Process)
            and process.returncode is None
        ):
            raise ServerStopError("Process remains running after waiting for exit.")

    async def stop(self) -> None:
        """Keep cleanup owned despite caller cancellation, with bounded escalation."""
        async with self.server.operation_lock:
            run = self.run
            if run is not None:
                self.intentionally_stopped = True
                cleanup = asyncio.create_task(run.stop(), name="bds-stop")
                cancelled = False
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        cancelled = True
                cleanup.result()
                self.logger.info("Server '%s' stopped.", self.server.server_name)
                if cancelled:
                    raise asyncio.CancelledError
                return
            if not await self.is_running(force_scan=True):
                self.intentionally_stopped = True
                await self.server.set_status_in_config("STOPPED")
                return
            process = self._process
            if not isinstance(process, system_process.psutil.Process):
                raise ServerStopError("No verified process handle.")
            self.intentionally_stopped = True
            timeout = self.server.settings.get(
                "lifecycle.server_stop_timeout_seconds", 10.0
            )
            created_at = await run_in_thread(process.create_time)
            try:
                # A survivor has no graceful console path; report termination honestly.
                with contextlib.suppress(
                    system_process.psutil.NoSuchProcess, ProcessLookupError
                ):
                    process.terminate()
                await self._wait_for_exit(process, timeout * 0.7)
            except TimeoutError:
                with contextlib.suppress(
                    system_process.psutil.NoSuchProcess, ProcessLookupError
                ):
                    process.kill()
                await self._wait_for_exit(process, timeout * 0.3)
            self._process = None
            self._publish_running(False)

            def remove_survivor_identity() -> None:
                record = system_process.read_process_record(self._record_path())
                if record is not None and (
                    record["pid"] != process.pid
                    or abs(record["created_at"] - created_at) > 0.001
                ):
                    return
                if record is not None:
                    with contextlib.suppress(FileNotFoundError):
                        os.remove(self._record_path())
                try:
                    with open(
                        self.server.get_pid_file_path(), encoding="utf-8"
                    ) as file:
                        pid = int(file.read().strip())
                    if pid == process.pid:
                        os.remove(self.server.get_pid_file_path())
                except (FileNotFoundError, ValueError):
                    pass

            await run_in_thread(remove_survivor_identity)
            await self.server.set_status_in_config("STOPPED")

    async def get_process_info(self) -> Optional[Dict[str, Any]]:
        if not await self.is_running():
            return None
        async with self._sample_lock:
            identity = (self._process, self._run)
            interval = self.server.settings.get(
                "monitoring.bedrock_metrics_interval_sec", 3
            )
            if (
                identity == self._sample_identity
                and self._sample_cache is not None
                and time.monotonic() - self._sampled_at < interval
            ):
                return dict(self._sample_cache)
            result = await self._sample_process_info()
            if identity != (self._process, self._run):
                return None
            self._sample_identity = identity
            self._sample_cache = result
            self._sampled_at = time.monotonic()
            return dict(result) if result is not None else None

    async def _sample_process_info(self) -> Optional[Dict[str, Any]]:
        """Return PID, CPU percentage, memory in MiB and uptime for the running process.

        Return ``None`` when no verified running process is available.
        """
        try:
            if not await self.is_running():
                return None
            process = self._process
            if process is None:
                return None
            process_obj = (
                process
                if isinstance(process, system_process.psutil.Process)
                else system_process.psutil.Process(process.pid)
            )
            observed_run = self._run
            data = await run_in_thread(self._resource_monitor.get_stats, process_obj)
            if (
                self._process is not process
                or self._run is not observed_run
                or (
                    isinstance(process, asyncio.subprocess.Process)
                    and process.returncode is not None
                )
            ):
                return None
            if data is None:
                raise DependencyUnavailableError("Process statistics are unavailable.")
            record = ProcessRecord.model_validate(data)
            self.server._runtime_state.update_server_runtime(
                self.server.server_name,
                cpu_percent=record.cpu_percent,
                memory_mb=record.memory_mb,
            )
            return record.model_dump(mode="json")
        except Exception as error:
            log_operation_error(
                self.logger,
                "Error getting process info for '%s': %s",
                self.server.server_name,
                error,
                error=error,
            )
            raise

    def _publish_running(self, running: bool) -> bool:
        if self._run is not None and self._run.process is self._process:
            self._run.publish()
            return running
        process = self._process
        pid = getattr(process, "pid", None)
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            pid = None
        if not running:
            self._recovery_state.recovered_pids.clear()
        key = self._recovery_state.key(
            self.server.server_name,
            self.server.paths.server_dir,
            self.server.paths.app_config_dir,
        )
        owned = running and isinstance(process, asyncio.subprocess.Process)
        command_available = (
            running
            and isinstance(process, asyncio.subprocess.Process)
            and process.stdin is not None
            and not process.stdin.is_closing()
        )
        self.server._runtime_state.update_server_runtime(
            self.server.server_name,
            running=running,
            pid=pid,
            recovered_untracked=running
            and self._recovery_state.recovered_pids.get(key) == pid,
            process_owned=owned,
            command_available=command_available,
            output_source="unknown",
            output_available=False,
            players_available=not running,
            ready=False,
            generation=(
                None
                if running
                else self.server._runtime_state.get_server_runtime(
                    self.server.server_name
                ).generation
            ),
            phase=(
                "RUNNING"
                if running
                else (
                    "ERROR"
                    if self.server._runtime_state.get_server_runtime(
                        self.server.server_name
                    ).phase
                    == "ERROR"
                    else "STOPPED"
                )
            ),
            process_observed_at=time.time(),
        )
        return running

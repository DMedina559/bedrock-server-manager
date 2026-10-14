"""Local CLI process control using runtime credentials and explicit paths."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psutil
from httpx2 import AsyncClient, TransportError
from pydantic import BaseModel, ConfigDict, ValidationError

from ..core.system import process as processes
from ..error import (
    OperationConflictError,
    ServerProcessError,
    ServerStartError,
    ServerStopError,
)
from .control import ControlFiles, ControlRecord
from .runtime import ShutdownResponse, WebRunOptions, WebRuntime

_detached_children: set[subprocess.Popen] = set()


class WebProcessPaths(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config_dir: str
    data_dir: str
    db_url: str

    @property
    def control_file(self) -> Path:
        return Path(self.config_dir) / "web_server.control.json"


def read_control(paths: WebProcessPaths) -> ControlRecord | None:
    try:
        return ControlRecord.model_validate_json(paths.control_file.read_text())
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, ValueError) as error:
        raise ServerProcessError("Invalid web runtime control file") from error


async def verify_web_owner(
    paths: WebProcessPaths, pid: int, record: ControlRecord | None = None
) -> psutil.Process:
    """Verify the host command, configuration and recorded process generation."""

    def verify():
        process = psutil.Process(pid)
        arguments = process.cmdline()
        command = any(
            Path(arg).name.lower()
            in {"bedrock-server-manager", "bedrock-server-manager.exe"}
            for arg in arguments
        ) or any(
            pair == ("-m", "bedrock_server_manager")
            for pair in zip(arguments, arguments[1:])
        )
        if not command or not any(
            pair == ("web", "start") for pair in zip(arguments, arguments[1:])
        ):
            raise ServerProcessError("PID does not identify a BSM web host")
        if record is not None:
            if record.created_at is None or record.config_dir is None:
                raise ServerProcessError(
                    "Control record lacks process-generation identity; refusing forced termination"
                )
            if (
                Path(record.config_dir).resolve() != Path(paths.config_dir).resolve()
                or abs(process.create_time() - record.created_at) > 0.001
            ):
                raise ServerProcessError(
                    "Web process generation or configuration differs"
                )
        else:
            if "--config-dir" not in arguments:
                raise ServerProcessError(
                    "Legacy process configuration cannot be verified"
                )
            index = arguments.index("--config-dir")
            if (
                index + 1 >= len(arguments)
                or Path(arguments[index + 1]).resolve()
                != Path(paths.config_dir).resolve()
            ):
                raise ServerProcessError("Legacy process configuration differs")
        return process

    try:
        return await asyncio.to_thread(verify)
    except (psutil.Error, OSError) as error:
        raise ServerProcessError("Could not verify web process identity") from error


async def force_stop_verified(
    paths: WebProcessPaths, pid: int, record: ControlRecord | None = None
) -> None:
    """Terminate the verified process object, retaining its PID-reuse protection."""
    process = await verify_web_owner(paths, pid, record)

    def terminate():
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        except psutil.NoSuchProcess:
            return
        except (psutil.Error, OSError) as error:
            raise ServerStopError(
                "Verified web process could not be stopped"
            ) from error

    await asyncio.to_thread(terminate)


async def start_detached(
    paths: WebProcessPaths, options: WebRunOptions, *, timeout: float = 30
) -> int:
    instance_id = uuid4().hex
    command = [
        sys.executable,
        "-m",
        "bedrock_server_manager",
        "--config-dir",
        paths.config_dir,
        "--data-dir",
        paths.data_dir,
        "--db-url",
        paths.db_url,
        "web",
        "start",
        "--mode",
        "direct",
        "--instance-id",
        instance_id,
    ]
    if options.host is not None:
        command.extend(["--host", options.host])
    if options.port is not None:
        command.extend(["--port", str(options.port)])
    if options.debug:
        command.append("--debug")
    probe = ControlFiles(paths.config_dir, WebRuntime())
    probe.acquire()
    probe.close()
    child = await asyncio.to_thread(
        processes.GuardedProcess(command).popen,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=(
            getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        ),
        start_new_session=os.name != "nt",
        close_fds=True,
    )
    try:
        async with AsyncClient(timeout=1, trust_env=False) as client:
            async with asyncio.timeout(timeout):
                while True:
                    if child.poll() is not None:
                        raise ServerStartError(
                            "Detached web runtime exited before HTTP readiness; inspect the application log"
                        )
                    record = read_control(paths)
                    if record is not None:
                        if record.instance_id != instance_id:
                            raise OperationConflictError(
                                "Another web runtime owns this configuration"
                            )
                        try:
                            response = await client.get(
                                record.url.removesuffix("/runtime/shutdown") + "/info"
                            )
                            if response.status_code == 200:
                                _detached_children.add(child)
                                return record.pid
                        except TransportError:
                            pass
                    await asyncio.sleep(0.05)
    except BaseException as error:
        if child.poll() is None:
            child.terminate()
            try:
                await asyncio.to_thread(child.wait, timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                await asyncio.to_thread(child.wait, timeout=5)
        if isinstance(error, TimeoutError):
            raise ServerStartError(
                "Detached web runtime did not become ready before the startup deadline"
            ) from error
        raise


async def stop_local(
    paths: WebProcessPaths, *, timeout: float = 180, force: bool = False
) -> str:
    record = read_control(paths)
    if record is None:
        pid_file = Path(paths.config_dir) / "web_server.pid"
        if not pid_file.exists():
            return "Web server not running."
        if not force:
            raise ServerStopError(
                "No graceful runtime control record; use --force only for a verified legacy process"
            )
        pid = await processes.read_pid_from_file(str(pid_file))
        if pid == os.getpid():
            raise ServerProcessError("Refusing to terminate the current process")
        if pid is None or not await processes.is_process_running(pid):
            pid_file.unlink(missing_ok=True)
            return "Web server not running (stale PID removed)."
        await force_stop_verified(paths, pid)
        pid_file.unlink(missing_ok=True)
        return "Web server stopped by forced termination."
    try:
        async with AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.post(
                record.url,
                json={},
                headers={"X-BSM-Shutdown-Token": record.token.get_secret_value()},
            )
        if response.status_code != 202:
            raise ServerStopError(f"Shutdown rejected (HTTP {response.status_code})")
        try:
            receipt = ShutdownResponse.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise ServerStopError(
                "Invalid shutdown response; runtime records retained"
            ) from error
        if receipt.instance_id != record.instance_id or receipt.pid != record.pid:
            raise ServerStopError("Shutdown response belongs to another runtime")
        async with asyncio.timeout(timeout):
            while True:
                current = read_control(paths)
                if current is None or current.instance_id != record.instance_id:
                    return "Web server stopped gracefully."
                await asyncio.sleep(0.05)
    except (TransportError, TimeoutError) as error:
        if not force:
            raise ServerStopError(
                "Graceful web shutdown failed; runtime records retained"
            ) from error
        if record.pid == os.getpid():
            raise ServerProcessError("Refusing to terminate the current process")
        await force_stop_verified(paths, record.pid, record)
        current = read_control(paths)
        if current is not None and current.instance_id == record.instance_id:
            paths.control_file.unlink(missing_ok=True)
            (Path(paths.config_dir) / "web_server.pid").unlink(missing_ok=True)
        return "Web server stopped by forced termination."

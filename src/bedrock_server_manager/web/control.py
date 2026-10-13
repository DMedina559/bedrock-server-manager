"""Private local control records and an OS-held single-instance lock."""

import json
import os
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import uuid4

import psutil
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..error import OperationConflictError
from .runtime import WebRuntime


class ControlRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    instance_id: str
    pid: int = Field(gt=0)
    host: str
    port: int = Field(ge=1, le=65535)
    token: SecretStr

    @property
    def url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.port}/api/runtime/shutdown"


class ControlFiles:
    def __init__(self, config_dir: str | Path, runtime: WebRuntime):
        self.directory = Path(config_dir)
        self.runtime = runtime
        self._file: Any = None

    def acquire(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / "web_server.lock"
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        self._file = os.fdopen(fd, "r+b")
        try:
            if os.name == "nt":
                msvcrt: Any = import_module("msvcrt")

                if path.stat().st_size == 0:
                    self._file.write(b"0")
                    self._file.flush()
                self._file.seek(0)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                fcntl: Any = import_module("fcntl")

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self._file.close()
            self._file = None
            raise OperationConflictError(
                "A web runtime already owns this configuration"
            ) from error

        legacy_pid = self.directory / "web_server.pid"
        if (
            legacy_pid.exists()
            and not (self.directory / "web_server.control.json").exists()
        ):
            try:
                pid = int(legacy_pid.read_text().strip())
            except ValueError:
                pid = 0
            if pid > 0 and psutil.pid_exists(pid):
                self._file.close()
                self._file = None
                raise OperationConflictError(
                    "A legacy web PID record is still live; stop it before starting a new runtime"
                )

    def publish(self, host: str, port: int) -> None:
        record = ControlRecord(
            instance_id=self.runtime.instance_id,
            pid=os.getpid(),
            host="127.0.0.1" if host == "0.0.0.0" else "::1" if host == "::" else host,
            port=port,
            token=self.runtime._token,
        )
        data = record.model_dump(mode="json", exclude={"token"})
        data["token"] = record.token.get_secret_value()
        self._write("web_server.control.json", json.dumps(data))
        self._write("web_server.pid", str(record.pid))

    def _write(self, name: str, data: str) -> None:
        temporary = self.directory / f".{name}.{uuid4().hex}"
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(data)
            os.replace(temporary, self.directory / name)
        finally:
            temporary.unlink(missing_ok=True)

    def close(self) -> None:
        if self._file is None:
            return
        # The OS lock prevents another runtime from publishing during cleanup.
        try:
            for name in ("web_server.control.json", "web_server.pid"):
                (self.directory / name).unlink(missing_ok=True)
        finally:
            self._file.close()
            self._file = None

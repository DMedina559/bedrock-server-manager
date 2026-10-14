"""Thread-safe web lifecycle control, independent of application services."""

import os
import secrets
from threading import RLock
from typing import Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..error import DependencyUnavailableError, OperationConflictError
from ..services.lifecycle import LifecyclePhase


class RuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance_id: str
    pid: int
    phase: LifecyclePhase
    shutdown_requested: bool
    shutdown_reason: (
        Literal["administrator", "local_cli", "service", "signal"] | None
    ) = None


class ShutdownRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShutdownResponse(RuntimeStatus):
    status: Literal["accepted"] = "accepted"


class WebRunOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    host: str | None = Field(default=None, min_length=1)
    port: int | None = Field(default=None, ge=1, le=65535)
    debug: bool = False
    instance_id: str | None = None


class WebRuntime:
    def __init__(self, instance_id: str | None = None):
        self.instance_id = instance_id or uuid4().hex
        self._token = secrets.token_urlsafe(32)
        self._lock = RLock()
        self._exit: Callable[[], None] | None = None
        self.on_ready: Callable[[], None] | None = None
        self._phase = LifecyclePhase.STARTING
        self._reason: (
            Literal["administrator", "local_cli", "service", "signal"] | None
        ) = None

    def attach(self, request_exit: Callable[[], None]) -> None:
        with self._lock:
            if self._exit is not None or self._phase in (
                LifecyclePhase.STOPPED,
                LifecyclePhase.FAILED,
            ):
                raise OperationConflictError("Web runtime cannot attach another server")
            self._exit = request_exit
            if self._reason is not None:
                request_exit()

    def ready(self) -> None:
        with self._lock:
            if self._phase == LifecyclePhase.STARTING and self._reason is None:
                if self.on_ready is not None:
                    self.on_ready()
                self._phase = LifecyclePhase.READY

    def authenticate_local(self, token: str) -> bool:
        return secrets.compare_digest(
            token.encode("utf-8"), self._token.encode("ascii")
        )

    def snapshot(self) -> RuntimeStatus:
        with self._lock:
            return RuntimeStatus(
                instance_id=self.instance_id,
                pid=os.getpid(),
                phase=self._phase,
                shutdown_requested=self._reason is not None,
                shutdown_reason=self._reason,
            )

    def accept_shutdown(
        self, reason: Literal["administrator", "local_cli", "service", "signal"]
    ) -> ShutdownResponse:
        with self._lock:
            if self._exit is None and reason != "service":
                raise DependencyUnavailableError(
                    "Web server lifecycle control is unavailable"
                )
            if self._phase in (LifecyclePhase.STOPPED, LifecyclePhase.FAILED):
                raise OperationConflictError("Web runtime has already stopped")
            if self._reason is None:
                self._reason = reason
                self._phase = LifecyclePhase.STOPPING
            return ShutdownResponse(**self.snapshot().model_dump())

    def signal_exit(self) -> None:
        with self._lock:
            if self._exit is not None:
                self._exit()

    def request_shutdown(
        self, reason: Literal["administrator", "local_cli", "service", "signal"]
    ) -> ShutdownResponse:
        receipt = self.accept_shutdown(reason)
        self.signal_exit()
        return receipt

    def finish(self, *, failed: bool = False) -> None:
        with self._lock:
            self._phase = LifecyclePhase.FAILED if failed else LifecyclePhase.STOPPED
            self._exit = None

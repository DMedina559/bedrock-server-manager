"""Bounded operation sequences, independent of event delivery and history."""

import asyncio
import functools
import inspect
import logging
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from time import time
from typing import Any, Awaitable, Callable, Iterator, Literal, ParamSpec, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class OperationName(StrEnum):
    SERVER_START = "server.start"
    SERVER_STOP = "server.stop"
    SERVER_RESTART = "server.restart"
    SERVER_UPDATE = "server.update"
    BACKUP_REQUEST = "backup.request"
    BACKUP_CREATE = "backup.create"
    BACKUP_RESTORE = "backup.restore"


class OperationSnapshot(BaseModel):
    """Immutable coordination metadata; response bodies and secrets are excluded."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    operation_id: str
    sequence_id: str
    root_operation_id: str
    parent_operation_id: str | None = None
    correlation_id: str
    name: str
    server_name: str | None = None
    owner: str = "application"
    source: str = "application"
    purpose: str | None = None
    status: Literal["running", "finished", "failed", "cancelled"] = "running"
    outcome: str | None = None
    scope: tuple[str, ...] = ()
    started_at: float
    finished_at: float | None = None


class OperationResultQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str | None = None
    server_name: str | None = None
    status: Literal["finished", "failed", "cancelled"] | None = None
    outcome: str | None = None
    purpose: str | None = None
    limit: int = Field(default=200, ge=1, le=10000)


class OperationSequence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    sequence_id: str
    root_operation_id: str
    ancestry: tuple[OperationSnapshot, ...]
    results_truncated: bool = False


@dataclass
class _Sequence:
    sequence_id: str
    root_operation_id: str
    task: asyncio.Task[Any] | None
    records: deque[OperationSnapshot]
    active: bool = True
    truncated: bool = False


@dataclass
class OperationHandle:
    """Application-only mutable handle; plugins receive frozen snapshots."""

    snapshot: OperationSnapshot

    def finish(self, outcome: str, *, scope: tuple[str, ...] = ()) -> None:
        self.snapshot = self.snapshot.model_copy(
            update={"outcome": outcome, "scope": scope}
        )


@dataclass
class _Frame:
    service: "OperationService"
    sequence: _Sequence
    handle: OperationHandle


_frames: ContextVar[tuple[_Frame, ...]] = ContextVar("operation_frames", default=())
_source: ContextVar[str] = ContextVar("operation_source", default="application")


def _task() -> asyncio.Task[Any] | None:
    try:
        return asyncio.current_task()
    except RuntimeError:
        return None


@contextmanager
def operation_source(source: str) -> Iterator[None]:
    token = _source.set(source)
    try:
        yield
    finally:
        _source.reset(token)


@contextmanager
def detached_operations() -> Iterator[None]:
    """Prevent submitted work from inheriting a caller's sequence."""
    token = _frames.set(())
    try:
        yield
    finally:
        _frames.reset(token)


class OperationService:
    """Own live sequences; release all result references when their root exits."""

    def __init__(self, *, max_sequences: int = 256, history_limit: int = 200):
        if max_sequences < 1 or history_limit < 1:
            raise ValueError("Operation limits must be positive")
        self.max_sequences = max_sequences
        self.history_limit = history_limit
        self._active: dict[str, _Sequence] = {}

    def _context(self) -> tuple[_Frame, ...]:
        task = _task()
        return tuple(
            frame
            for frame in _frames.get()
            if frame.service is self
            and frame.sequence.active
            and (task is None or frame.sequence.task is task)
        )

    def current(self) -> OperationSnapshot | None:
        frames = self._context()
        return frames[-1].handle.snapshot if frames else None

    def sequence(self) -> OperationSequence | None:
        frames = self._context()
        if not frames:
            return None
        sequence = frames[-1].sequence
        return OperationSequence(
            sequence_id=sequence.sequence_id,
            root_operation_id=sequence.root_operation_id,
            ancestry=tuple(frame.handle.snapshot for frame in frames),
            results_truncated=sequence.truncated,
        )

    def results(
        self, query: OperationResultQuery | None = None
    ) -> tuple[OperationSnapshot, ...]:
        frames = self._context()
        if not frames:
            return ()
        query = query or OperationResultQuery()
        records = tuple(frames[-1].sequence.records)
        filters = query.model_dump(exclude={"limit"})
        selected = tuple(
            record
            for record in records
            if all(
                value is None or getattr(record, key) == value
                for key, value in filters.items()
            )
        )
        start = max(0, len(selected) - query.limit)
        return selected[start:]

    @contextmanager
    def scope(
        self, name: str, *, server_name: str | None = None, purpose: str | None = None
    ) -> Iterator[OperationHandle]:
        from .events.bus import correlation_scope, current_correlation_id

        frames = self._context()
        parent = frames[-1].handle.snapshot if frames else None
        identifier = uuid4().hex
        if len(frames) >= 64:
            from .error import OperationConflictError

            raise OperationConflictError("Operation depth limit reached")
        if frames:
            sequence = frames[-1].sequence
        else:
            if len(self._active) >= self.max_sequences:
                from .error import OperationConflictError

                raise OperationConflictError("Operation sequence capacity reached")
            sequence = _Sequence(
                uuid4().hex, identifier, _task(), deque(maxlen=self.history_limit)
            )
        with correlation_scope():
            handle = OperationHandle(
                OperationSnapshot(
                    operation_id=identifier,
                    sequence_id=sequence.sequence_id,
                    root_operation_id=sequence.root_operation_id,
                    parent_operation_id=parent.operation_id if parent else None,
                    correlation_id=current_correlation_id() or uuid4().hex,
                    name=name,
                    server_name=server_name,
                    source=_source.get(),
                    owner=_source.get(),
                    purpose=purpose,
                    started_at=time(),
                )
            )
            if not frames:
                self._active[sequence.sequence_id] = sequence
            token = _frames.set(_frames.get() + (_Frame(self, sequence, handle),))
            status = "finished"
            try:
                yield handle
            except BaseException as error:
                from .error import APICancelledError

                status = (
                    "cancelled"
                    if isinstance(error, (asyncio.CancelledError, APICancelledError))
                    else "failed"
                )
                raise
            finally:
                handle.snapshot = handle.snapshot.model_copy(
                    update={
                        "status": status,
                        "finished_at": time(),
                        "outcome": handle.snapshot.outcome
                        or ("completed" if status == "finished" else status),
                    }
                )
                if len(sequence.records) == self.history_limit:
                    sequence.truncated = True
                sequence.records.append(handle.snapshot)
                _frames.reset(token)
                if not frames:
                    sequence.active = False
                    sequence.records.clear()
                    self._active.pop(sequence.sequence_id, None)
                logging.getLogger(__name__).debug(
                    "Operation %s finished: %s (%s)",
                    name,
                    status,
                    handle.snapshot.outcome,
                    extra={
                        "operation_id": identifier,
                        "sequence_id": sequence.sequence_id,
                        "server_name": server_name,
                    },
                )


P = ParamSpec("P")
R = TypeVar("R")


def track_operation(
    name: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Wrap an API operation outside its hooks without changing its signature."""

    def decorate(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        signature = inspect.signature(function)

        @functools.wraps(function)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            bound = signature.bind(*args, **kwargs)
            context = bound.arguments["app_context"]
            request = bound.arguments["request"]
            server_name = (
                request.get("server_name")
                if isinstance(request, dict)
                else request.server_name
            )
            with context.operations.scope(name, server_name=server_name) as operation:
                result = await function(*args, **kwargs)
                outcome = getattr(result, "outcome", None) or getattr(
                    result, "status", "completed"
                )
                if (
                    name == OperationName.SERVER_UPDATE
                    and getattr(result, "status", None) == "success"
                ):
                    outcome = (
                        "updated" if getattr(result, "updated", False) else "up_to_date"
                    )
                operation.finish(outcome)
                return result

        return wrapped

    return decorate

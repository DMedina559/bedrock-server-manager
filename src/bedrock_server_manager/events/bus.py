"""Application-owned event delivery; no API, plugin, or web dependencies."""

import asyncio
import inspect
import logging
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
from time import monotonic, time
from typing import Any, Callable, Mapping
from uuid import uuid4

from pydantic import BaseModel

from .control import CancellableEvent
from .models import (
    EventDefinition,
    EventDelivery,
    EventDiagnostics,
    EventEnvelope,
    EventOptions,
    EventRecord,
    ListenerFailure,
)
from .registry import EventRegistry, builtin_events
from .serialization import PRIVATE_FIELDS, sanitize

logger = logging.getLogger(__name__)
_stack: ContextVar[tuple[tuple[int, str, EventEnvelope], ...]] = ContextVar(
    "event_dispatch_stack", default=()
)
_correlation: ContextVar[str | None] = ContextVar("event_correlation", default=None)


@contextmanager
def correlation_scope():
    token = _correlation.set(_correlation.get() or uuid4().hex)
    try:
        yield
    finally:
        _correlation.reset(token)


@dataclass(frozen=True)
class Subscription:
    token: str
    name: str
    owner: str
    callback: Callable[..., Any]
    observer: bool = False


class EventBus:
    def __init__(
        self,
        options: EventOptions | None = None,
        *,
        revision_provider: Callable[[], Mapping[str, Any]] | None = None,
    ):
        self.options = options or EventOptions()
        self.registry = EventRegistry(builtin_events)
        self._revision_provider = revision_provider
        self._subscriptions: dict[str, Subscription] = {}
        self._owners: set[str] = set()
        self._closed_owners: set[str] = set()
        self._generations: dict[str, int] = {}
        self._lock = RLock()
        self._recent: deque[EventRecord] = deque(maxlen=self.options.history_limit)
        self._active: dict[str, EventRecord] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        self._inflight: dict[
            str, dict[asyncio.Future[None], asyncio.Task[Any] | None]
        ] = {}
        self.accepting = True
        self.emitted = self.suppressed = self.failed_listeners = 0

    def subscribe(
        self,
        name: str,
        callback: Callable[..., Any],
        *,
        owner: str = "application",
        active: bool = True,
        observer: bool = False,
        generation: int | None = None,
    ) -> str:
        with self._lock:
            self.check_owner(owner, generation)
            if not callable(callback):
                raise TypeError("Event listener must be callable")
            if active:
                self.activate_owner(owner)
            for subscription in self._subscriptions.values():
                if (
                    subscription.name,
                    subscription.owner,
                    subscription.callback,
                    subscription.observer,
                ) == (name, owner, callback, observer):
                    return subscription.token
            token = uuid4().hex
            self._subscriptions[token] = Subscription(
                token, name, owner, callback, observer
            )
            return token

    def define(
        self,
        definition: EventDefinition,
        payload_model: type[BaseModel],
        *,
        generation: int | None = None,
    ) -> None:
        with self._lock:
            self.check_owner(definition.owner, generation)
            self.registry.register(definition, payload_model)

    def unsubscribe(self, token: str, *, owner: str | None = None) -> None:
        with self._lock:
            subscription = self._subscriptions.get(token)
            if (
                subscription is not None
                and owner is not None
                and subscription.owner != owner
            ):
                raise PermissionError("Subscription belongs to another owner")
            self._subscriptions.pop(token, None)

    def open_owner(self, owner: str) -> int:
        with self._lock:
            self._generations[owner] = self._generations.get(owner, 0) + 1
            self._closed_owners.discard(owner)
            return self._generations[owner]

    def owner_generation(self, owner: str) -> int:
        return self._generations.get(owner, 0)

    def check_owner(self, owner: str, generation: int | None = None) -> None:
        if (
            not self.accepting
            or owner in self._closed_owners
            or (generation is not None and generation != self.owner_generation(owner))
        ):
            raise RuntimeError("Event owner is no longer active")

    def activate_owner(self, owner: str) -> None:
        with self._lock:
            self._closed_owners.discard(owner)
            self._owners.add(owner)

    def deactivate_owner(self, owner: str) -> None:
        with self._lock:
            self._owners.discard(owner)

    def remove_owner(self, owner: str) -> None:
        with self._lock:
            self.deactivate_owner(owner)
            self._closed_owners.add(owner)
            for token, subscription in list(self._subscriptions.items()):
                if subscription.owner == owner:
                    self.unsubscribe(token)
            self.registry.remove_owner(owner)

    async def drain_owner(self, owner: str, timeout: float) -> None:
        current = asyncio.current_task()
        pending = {
            future
            for future, task in self._inflight.get(owner, {}).items()
            if task is not current
        }
        if pending:
            _, overdue = await asyncio.wait(pending, timeout=timeout)
            if overdue:
                raise TimeoutError("Event listeners did not drain before plugin unload")

    def events_for_owner(self, owner: str) -> list[str]:
        with self._lock:
            return sorted(
                {s.name for s in self._subscriptions.values() if s.owner == owner}
            )

    def _selected(
        self, name: str, observer: bool, owners: set[str] | None
    ) -> list[Subscription]:
        with self._lock:
            selected = []
            seen: set[tuple[str, Callable[..., Any]]] = set()
            for subscription in self._subscriptions.values():
                identity = (subscription.owner, subscription.callback)
                allowed = subscription.owner in (
                    owners if owners is not None else self._owners
                )
                if (
                    allowed
                    and subscription.observer == observer
                    and subscription.name in {name, "*"}
                    and identity not in seen
                ):
                    selected.append(subscription)
                    seen.add(identity)
            return selected

    async def _invoke(
        self,
        subscription: Subscription,
        envelope: EventEnvelope,
        args: tuple[Any, ...],
        data: dict[str, Any],
    ) -> Any:
        if subscription.observer:
            callback_args, callback_data = (envelope.model_copy(deep=True),), {}
        else:
            callback_args = deepcopy(args)
            callback_data = deepcopy(
                {key: value for key, value in data.items() if key not in PRIVATE_FIELDS}
            )
            for key in ("event", "_triggering_plugin"):
                if key in data:
                    callback_data[key] = data[key]
        if inspect.iscoroutinefunction(subscription.callback):
            return await subscription.callback(*callback_args, **callback_data)
        result = await asyncio.to_thread(
            subscription.callback, *callback_args, **callback_data
        )
        return await result if inspect.isawaitable(result) else result

    def _failure(self, record: EventRecord, owner: str, error: Exception) -> None:
        record.failures.append(
            ListenerFailure(
                owner=owner,
                error_type=type(error).__name__,
                code=(
                    "event_listener_timeout"
                    if isinstance(error, TimeoutError)
                    else "event_listener_failed"
                ),
            )
        )
        self.failed_listeners += 1
        logger.warning(
            "Event listener '%s' failed for '%s': %s",
            owner,
            record.name,
            type(error).__name__,
        )

    async def _deliver(
        self,
        subscription: Subscription,
        envelope: EventEnvelope,
        record: EventRecord,
        args: tuple[Any, ...],
        data: dict[str, Any],
        strict: bool,
    ) -> None:
        pending = asyncio.get_running_loop().create_future()
        owned = self._inflight.setdefault(subscription.owner, {})
        owned[pending] = asyncio.current_task()
        record.listeners_called += 1
        definition = self.registry.definition(envelope.name)
        try:
            timeout = (
                self.options.hook_timeout_seconds
                if definition.phase == "before"
                else self.options.listener_timeout_seconds
            )
            async with asyncio.timeout(timeout):
                result = await self._invoke(subscription, envelope, args, data)
            if subscription.observer and isinstance(result, BaseModel):
                delivery = EventDelivery(
                    owner=subscription.owner, **result.model_dump(mode="json")
                )
                record.deliveries.append(delivery)
                if delivery.failed:
                    self._failure(
                        record,
                        subscription.owner,
                        RuntimeError("Observer delivery failed"),
                    )
        except Exception as error:
            self._failure(record, subscription.owner, error)
            control = data.get("event")
            if definition.phase == "before" and isinstance(control, CancellableEvent):
                control.cancel("A before-operation listener did not complete")
            if strict:
                raise
        finally:
            owned.pop(pending, None)
            pending.set_result(None)
            if not owned:
                self._inflight.pop(subscription.owner, None)

    async def _dispatch(
        self,
        envelope: EventEnvelope,
        record: EventRecord,
        args: tuple[Any, ...],
        data: dict[str, Any],
        public: bool,
        owners: set[str] | None,
        strict: bool,
    ) -> None:
        for observer in (False, True):
            if observer and (
                not public or not self.registry.definition(envelope.name).public
            ):
                continue
            for subscription in self._selected(envelope.name, observer, owners):
                if subscription.token not in self._subscriptions or (
                    owners is None and subscription.owner not in self._owners
                ):
                    continue
                await self._deliver(subscription, envelope, record, args, data, strict)

    async def emit(
        self,
        name: str,
        payload: Mapping[str, Any] | None = None,
        *args: Any,
        source: str = "application",
        public: bool = True,
        revision: Mapping[str, Any] | None = None,
        target_owners: set[str] | None = None,
        strict: bool = False,
    ) -> EventRecord:
        if not self.accepting:
            raise RuntimeError("Event bus is closed")
        data = dict(payload or {})
        definition = self.registry.definition(name)
        public_data = {
            key: value for key, value in data.items() if key not in PRIVATE_FIELDS
        }
        prepared = self.registry.prepare(name, public_data)
        if isinstance(prepared, BaseModel):
            data = {
                **data,
                **{key: getattr(prepared, key) for key in type(prepared).model_fields},
                **(prepared.model_extra or {}),
            }
        public_payload = sanitize(prepared)
        if not isinstance(public_payload, dict):
            raise ValueError("Event payload must be an object")
        sanitize(args)
        stack = tuple(
            item
            for item in _stack.get()
            if item[0] == id(self) and item[2].event_id in self._active
        )
        identity = repr(
            (
                name,
                tuple((key, public_data.get(key)) for key in definition.identity_keys),
            )
        )
        parent = stack[-1][2] if stack else None
        stamp = (
            revision
            if revision is not None
            else self._revision_provider() if public and self._revision_provider else {}
        )
        envelope = EventEnvelope(
            event_id=uuid4().hex,
            correlation_id=(
                parent.correlation_id if parent else _correlation.get() or uuid4().hex
            ),
            parent_event_id=parent.event_id if parent else None,
            timestamp=time(),
            source=source,
            name=name,
            data=public_payload,
            **stamp,
        )
        record = EventRecord(
            **envelope.model_dump(exclude={"data", "epoch", "revision"}),
            status="dispatching",
        )
        self.emitted += 1
        if any(key == identity for _, key, _ in stack):
            record.status = "suppressed"
            self.suppressed += 1
            self._recent.append(record)
            return record.model_copy(deep=True)
        if (
            len(stack) >= self.options.max_depth
            or len(self._active) >= self.options.max_active
        ):
            record.status = "partial"
            self._failure(
                record, "event-bus", RuntimeError("Event dispatch capacity exceeded")
            )
            if isinstance(data.get("event"), CancellableEvent):
                data["event"].cancel("Event dispatch capacity exceeded")
            self._recent.append(record)
            return record.model_copy(deep=True)
        self._active[record.event_id] = record
        task = asyncio.current_task()
        already_owned = task in self._tasks
        if task is not None:
            self._tasks.add(task)
        token = _stack.set(_stack.get() + ((id(self), identity, envelope),))
        started = monotonic()
        try:
            await self._dispatch(
                envelope, record, args, data, public, target_owners, strict
            )
            control = data.get("event")
            record.status = (
                "cancelled"
                if isinstance(control, CancellableEvent) and control.is_cancelled
                else "partial" if record.failures else "completed"
            )
        except BaseException:
            record.status = "cancelled" if not record.failures else "partial"
            raise
        finally:
            if isinstance(data.get("event"), CancellableEvent):
                record.cancellation_reason = data["event"].cancel_reason
            record.duration_ms = (monotonic() - started) * 1000
            self._active.pop(record.event_id, None)
            self._recent.append(record.model_copy(deep=True))
            if task is not None and not already_owned:
                self._tasks.discard(task)
            _stack.reset(token)
        return record.model_copy(deep=True)

    def diagnostics(self) -> EventDiagnostics:
        return EventDiagnostics(
            accepting=self.accepting,
            emitted=self.emitted,
            suppressed=self.suppressed,
            failed_listeners=self.failed_listeners,
            subscriptions=len(self._subscriptions),
            active=list(self._active.values()),
            recent=list(self._recent),
        ).model_copy(deep=True)

    async def close(self) -> None:
        self.accepting = False
        tasks = self._tasks - {asyncio.current_task()}
        if tasks:
            _, pending = await asyncio.wait(
                tasks, timeout=self.options.listener_timeout_seconds
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.wait(pending, timeout=1)
        self._subscriptions.clear()
        self._owners.clear()

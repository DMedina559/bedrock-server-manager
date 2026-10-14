"""Application-owned event delivery; no API, plugin, or web dependencies."""

import asyncio
import inspect
import logging
from collections import Counter, deque
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from threading import Event as ThreadEvent
from threading import RLock
from time import monotonic, time
from typing import Any, Callable, Mapping
from uuid import uuid4

from pydantic import BaseModel

from .control import CancellableEvent
from .models import (
    EventActivityQuery,
    EventDefinition,
    EventDelivery,
    EventDiagnostics,
    EventEnvelope,
    EventOptions,
    EventRecord,
    ListenerFailure,
    ListenerRecord,
)
from .registry import EventRegistry, builtin_events
from .serialization import PRIVATE_FIELDS, sanitize

logger = logging.getLogger(__name__)
_stack: ContextVar[tuple[tuple[int, str, EventEnvelope], ...]] = ContextVar(
    "event_dispatch_stack", default=()
)
_correlation: ContextVar[str | None] = ContextVar("event_correlation", default=None)


@contextmanager
def correlation_scope(identifier: str | None = None):
    token = _correlation.set(_correlation.get() or identifier or uuid4().hex)
    try:
        yield
    finally:
        _correlation.reset(token)


def current_correlation_id() -> str | None:
    """Read the active operation's correlation identity."""
    return _correlation.get()


def _callback_identity(callback: Callable[..., Any]) -> tuple[int, int]:
    if inspect.ismethod(callback):
        return id(callback.__self__), id(callback.__func__)
    return id(callback), 0


@dataclass(frozen=True)
class Subscription:
    token: str
    name: str
    owner: str
    callback: Callable[..., Any]
    observer: bool = False
    once: bool = False
    priority: int = 0


class EventBus:
    def __init__(
        self,
        options: EventOptions | None = None,
        *,
        revision_provider: Callable[[], Mapping[str, Any]] | None = None,
    ):
        self.options = options or EventOptions()
        self.diagnostic_recorder: Callable[[EventRecord], None] | None = None
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
        self._waiters: dict[str, set[asyncio.Future[dict[str, Any]]]] = {}
        self._workers: dict[str, dict[asyncio.Task[Any], ThreadEvent]] = {}
        self._rejections: dict[str, int] = {}
        self._timeouts: dict[str, int] = {}
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
        once: bool = False,
        priority: int = 0,
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
                    _callback_identity(subscription.callback),
                    subscription.observer,
                    subscription.once,
                    subscription.priority,
                ) == (
                    name,
                    owner,
                    _callback_identity(callback),
                    observer,
                    once,
                    priority,
                ):
                    return subscription.token
            token = uuid4().hex
            self._subscriptions[token] = Subscription(
                token, name, owner, callback, observer, once, priority
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

    def once(self, name: str, callback: Callable[..., Any], **options: Any) -> str:
        """Consume the subscription before invoking its first callback."""
        return self.subscribe(name, callback, once=True, **options)

    async def wait_for(
        self,
        name: str,
        *,
        predicate: Callable[..., bool] | None = None,
        timeout: float = 30,
        owner: str = "application",
        generation: int | None = None,
        active: bool = True,
    ) -> dict[str, Any]:
        """Await the next matching payload; always remove the temporary listener."""
        if timeout <= 0 or not timeout < float("inf"):
            raise ValueError("Event wait timeout must be finite and positive")
        future: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )

        async def receive(*args: Any, **data: Any) -> None:
            if future.done():
                return
            try:
                matched = predicate is None or predicate(*args, **data)
                if inspect.isawaitable(matched):
                    if inspect.iscoroutine(matched):
                        matched.close()
                    raise TypeError("Event predicates must be synchronous")
                if matched:
                    self.unsubscribe(token, owner=owner)
                    future.set_result(data)
            except Exception as error:
                future.set_exception(error)
                self.unsubscribe(token, owner=owner)

        token = self.subscribe(
            name, receive, owner=owner, generation=generation, active=active
        )
        self._waiters.setdefault(owner, set()).add(future)
        try:
            async with asyncio.timeout(timeout):
                return await future
        finally:
            self.unsubscribe(token, owner=owner)
            owned = self._waiters.get(owner)
            if owned is not None:
                owned.discard(future)
                if not owned:
                    self._waiters.pop(owner, None)

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
            if self.owner_pending(owner):
                raise RuntimeError("Previous event owner generation is still draining")
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
            for future in self._waiters.pop(owner, set()):
                future.cancel()

    def owner_pending(self, owner: str) -> bool:
        return bool(self._inflight.get(owner) or self._workers.get(owner))

    async def drain_owner(self, owner: str, timeout: float) -> None:
        self.deactivate_owner(owner)
        for cancellation in self._workers.get(owner, {}).values():
            cancellation.set()
        current = asyncio.current_task()
        pending = {
            future
            for future, task in self._inflight.get(owner, {}).items()
            if task is not current
        }
        pending.update(self._workers.get(owner, {}))
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
            seen: set[tuple[str, tuple[int, int], bool]] = set()
            for subscription in sorted(
                self._subscriptions.values(), key=lambda item: -item.priority
            ):
                identity = (
                    subscription.owner,
                    _callback_identity(subscription.callback),
                    subscription.once,
                )
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
            return sorted(selected, key=lambda item: -item.priority)

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
        worker_limit = self.options.max_workers or self.options.max_active
        owner_limit = self.options.max_workers_per_owner or worker_limit
        if (
            sum(map(len, self._workers.values())) >= worker_limit
            or len(self._workers.get(subscription.owner, {})) >= owner_limit
        ):
            raise EventWorkerCapacityError("Outstanding event worker capacity reached")
        cancellation = ThreadEvent()
        try:
            signature = inspect.signature(subscription.callback)
            parameter = signature.parameters.get("cancellation_event")
            if (
                parameter is not None
                and parameter.kind != inspect.Parameter.POSITIONAL_ONLY
                and "cancellation_event"
                not in signature.bind_partial(*callback_args, **callback_data).arguments
            ):
                callback_data["cancellation_event"] = cancellation
        except (TypeError, ValueError):
            pass
        worker = asyncio.create_task(
            asyncio.to_thread(subscription.callback, *callback_args, **callback_data)
        )
        workers = self._workers.setdefault(subscription.owner, {})
        workers[worker] = cancellation
        abandoned = False

        def finished(task: asyncio.Task[Any]) -> None:
            workers.pop(task, None)
            if not workers:
                self._workers.pop(subscription.owner, None)
            if (
                not task.cancelled()
                and task.exception() is None
                and abandoned
                and inspect.iscoroutine(task.result())
            ):
                task.result().close()

        worker.add_done_callback(finished)
        try:
            result = await asyncio.shield(worker)
        except asyncio.CancelledError:
            abandoned = True
            cancellation.set()
            if (
                worker.done()
                and not worker.cancelled()
                and worker.exception() is None
                and inspect.iscoroutine(worker.result())
            ):
                worker.result().close()
            raise
        return await result if inspect.isawaitable(result) else result

    def _failure(self, record: EventRecord, owner: str, error: Exception) -> None:
        record.failures.append(
            ListenerFailure(
                owner=owner,
                error_type=type(error).__name__,
                code=(
                    "event_listener_timeout"
                    if isinstance(error, TimeoutError)
                    else (
                        "event_capacity"
                        if isinstance(error, EventWorkerCapacityError)
                        else "event_listener_failed"
                    )
                ),
            )
        )
        self.failed_listeners += 1
        if isinstance(error, TimeoutError):
            self._timeouts[owner] = self._timeouts.get(owner, 0) + 1
        if isinstance(error, EventWorkerCapacityError):
            self._rejections["worker_capacity"] = (
                self._rejections.get("worker_capacity", 0) + 1
            )
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
        listener = ListenerRecord(
            subscription_id=subscription.token,
            owner=subscription.owner,
            observer=subscription.observer,
            listener_name=getattr(
                subscription.callback,
                "__qualname__",
                type(subscription.callback).__name__,
            ),
        )
        record.listeners.append(listener)
        started = monotonic()
        try:
            timeout = (
                self.options.hook_timeout_seconds
                if definition.phase == "before" and not subscription.observer
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
                    listener.status = "failed"
                    self._failure(
                        record,
                        subscription.owner,
                        RuntimeError("Observer delivery failed"),
                    )
                    listener.failure = record.failures[-1]
            if listener.status == "running":
                listener.status = "completed"
        except asyncio.CancelledError:
            listener.status = "cancelled"
            raise
        except Exception as error:
            listener.status = (
                "timed_out" if isinstance(error, TimeoutError) else "failed"
            )
            self._failure(record, subscription.owner, error)
            listener.failure = record.failures[-1]
            control = data.get("event")
            if (
                not subscription.observer
                and definition.phase == "before"
                and isinstance(control, CancellableEvent)
            ):
                control.cancel("A before-operation listener did not complete")
            if strict and not subscription.observer:
                raise
        finally:
            listener.duration_ms = (monotonic() - started) * 1000
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
                if subscription.once:
                    self.unsubscribe(subscription.token, owner=subscription.owner)
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
            record = EventRecord(
                event_id=uuid4().hex,
                correlation_id=_correlation.get() or uuid4().hex,
                name=name,
                source=source,
                timestamp=time(),
                status="cancelled",
                rejection_reason="shutdown",
            )
            self._rejections["shutdown"] = self._rejections.get("shutdown", 0) + 1
            self._recent.append(record.model_copy(deep=True))
            if self.diagnostic_recorder is not None and record.failures:
                try:
                    self.diagnostic_recorder(record.model_copy(deep=True))
                except Exception:
                    logger.debug(
                        "Event diagnostics recording unavailable", exc_info=True
                    )
            raise EventDispatchRejected(record)
        data = dict(payload or {})
        definition = self.registry.definition(name)
        public_data = {
            key: value for key, value in data.items() if key not in PRIVATE_FIELDS
        }
        prepared = self.registry.prepare(name, public_data)
        if isinstance(prepared, BaseModel):
            data = {
                **{key: value for key, value in data.items() if key in PRIVATE_FIELDS},
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
            control = data.get("event")
            if definition.phase == "before" and isinstance(control, CancellableEvent):
                control.cancel("Recursive before-operation dispatch rejected")
                record.cancellation_reason = control.cancel_reason
                record.status = "cancelled"
            else:
                record.status = "suppressed"
            record.rejection_reason = "recursion"
            self._rejections["recursion"] = self._rejections.get("recursion", 0) + 1
            self.suppressed += 1
            self._recent.append(record)
            return record.model_copy(deep=True)
        if (
            len(stack) >= self.options.max_depth
            or len(self._active) >= self.options.max_active
        ):
            record.status = "partial"
            record.rejection_reason = (
                "depth_limit" if len(stack) >= self.options.max_depth else "capacity"
            )
            self._rejections[record.rejection_reason] = (
                self._rejections.get(record.rejection_reason, 0) + 1
            )
            record.failures.append(
                ListenerFailure(
                    owner="event-bus",
                    error_type="EventDispatchRejected",
                    code=(
                        "event_depth_limit"
                        if record.rejection_reason == "depth_limit"
                        else "event_capacity"
                    ),
                )
            )
            if isinstance(data.get("event"), CancellableEvent):
                data["event"].cancel(
                    f"Event dispatch rejected: {record.rejection_reason}"
                )
                record.cancellation_reason = data["event"].cancel_reason
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
            if self.diagnostic_recorder is not None and record.failures:
                try:
                    self.diagnostic_recorder(record.model_copy(deep=True))
                except Exception:
                    logger.debug(
                        "Event diagnostics recording unavailable", exc_info=True
                    )
            if task is not None and not already_owned:
                self._tasks.discard(task)
            _stack.reset(token)
        return record.model_copy(deep=True)

    def diagnostics(self, query: EventActivityQuery | None = None) -> EventDiagnostics:
        query = query or EventActivityQuery(limit=self.options.history_limit or 1)
        limit = query.limit

        def matches(record: EventRecord) -> bool:
            return (
                (query.name is None or record.name == query.name)
                and (
                    query.correlation_id is None
                    or record.correlation_id == query.correlation_id
                )
                and (query.status is None or record.status == query.status)
                and (
                    query.owner is None
                    or record.source == query.owner
                    or any(item.owner == query.owner for item in record.listeners)
                    or any(item.owner == query.owner for item in record.failures)
                )
            )

        active = [record for record in self._active.values() if matches(record)]
        recent = [record for record in self._recent if matches(record)]
        return EventDiagnostics(
            accepting=self.accepting,
            emitted=self.emitted,
            suppressed=self.suppressed,
            failed_listeners=self.failed_listeners,
            subscriptions=len(self._subscriptions),
            active_dispatches=len(self._active),
            subscriptions_by_owner=dict(
                Counter(
                    subscription.owner for subscription in self._subscriptions.values()
                )
            ),
            active_listeners_by_owner=dict(
                Counter(
                    listener.owner
                    for record in self._active.values()
                    for listener in record.listeners
                    if listener.status == "running"
                )
            ),
            pending_workers=sum(map(len, self._workers.values())),
            workers_by_owner={
                owner: len(workers) for owner, workers in self._workers.items()
            },
            pending_waits=sum(map(len, self._waiters.values())),
            rejections_by_reason=self._rejections,
            timeouts_by_owner=self._timeouts,
            active=active[:limit],
            recent=recent[-limit:],
            active_truncated=len(active) > limit,
            recent_truncated=len(recent) > limit,
        ).model_copy(deep=True)

    async def close(self) -> None:
        deadline = monotonic() + self.options.listener_timeout_seconds
        self.accepting = False
        for futures in self._waiters.values():
            for future in futures:
                future.cancel()
        self._waiters.clear()
        for workers in self._workers.values():
            for cancellation in workers.values():
                cancellation.set()
        tasks = self._tasks - {asyncio.current_task()}
        if tasks:
            _, pending = await asyncio.wait(
                tasks, timeout=max(0, deadline - monotonic())
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.wait(pending, timeout=1)
        pending_workers = {
            worker for owned in self._workers.values() for worker in owned
        }
        if pending_workers:
            await asyncio.wait(pending_workers, timeout=max(0, deadline - monotonic()))
        self._subscriptions.clear()
        self._owners.clear()


class EventWorkerCapacityError(RuntimeError):
    """No additional synchronous callback may be queued or started."""


class EventDispatchRejected(RuntimeError):
    def __init__(self, record: EventRecord):
        self.record = record.model_copy(deep=True)
        super().__init__(f"Event dispatch rejected: {record.rejection_reason}")

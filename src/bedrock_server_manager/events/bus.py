"""Application-owned event delivery; no API, plugin, or web dependencies."""

import asyncio
import inspect
import logging
from collections import Counter, deque
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, replace
from threading import Event as ThreadEvent
from threading import RLock
from time import monotonic, time
from typing import Any, Callable, Mapping
from uuid import uuid4

from pydantic import BaseModel

from ..operations import OperationService
from .context import EventNotification, EventPayload, PluginEvent, freeze
from .control import CancellableEvent
from .models import (
    EventActivityQuery,
    EventContext,
    EventDefinition,
    EventDelivery,
    EventDiagnostics,
    EventEnvelope,
    EventFilter,
    EventOptions,
    EventRecord,
    EventSubscriptionInfo,
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
    filters: EventFilter | None = None
    predicate: Callable[[EventNotification], bool] | None = None
    listener_id: str | None = None
    before: tuple[str, ...] = ()
    after: tuple[str, ...] = ()
    kind: str = "legacy"
    callback_identity: tuple[int, ...] | None = None


@dataclass
class CallbackState:
    subscription: Subscription
    envelope: EventEnvelope
    control: CancellableEvent | None
    deadline: float
    generation: int
    arguments: tuple[Any, ...] = ()
    active: bool = True
    once_claimed: bool = False
    clock: Callable[[], float] = monotonic


_FILTERED = object()


class EventBus:
    def __init__(
        self,
        options: EventOptions | None = None,
        *,
        revision_provider: Callable[[], Mapping[str, Any]] | None = None,
    ):
        self.options = options or EventOptions()
        self.operations = OperationService()
        self._current: ContextVar[
            tuple[EventEnvelope, asyncio.Task[Any] | None] | None
        ] = ContextVar("current_event", default=None)
        self._handler: ContextVar[CallbackState | None] = ContextVar(
            "event_handler", default=None
        )
        self._subscription_stats: dict[str, dict[str, Any]] = {}
        self._subscription_leases: Counter[str] = Counter()
        self._persistent_subscriptions: set[str] = set()
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
        filters: EventFilter | None = None,
        predicate: Callable[[EventNotification], bool] | None = None,
        listener_id: str | None = None,
        before: tuple[str, ...] = (),
        after: tuple[str, ...] = (),
        kind: str = "legacy",
        callback_identity: tuple[int, ...] | None = None,
        temporary: bool = False,
    ) -> str:
        with self._lock:
            self.check_owner(owner, generation)
            if not callable(callback):
                raise TypeError("Event listener must be callable")
            if filters is not None and not isinstance(filters, EventFilter):
                raise TypeError("Use an EventFilter for subscription filters")
            if predicate is not None and (
                not callable(predicate) or inspect.iscoroutinefunction(predicate)
            ):
                raise TypeError("Subscription predicates must be synchronous callables")
            before, after = tuple(before), tuple(after)
            if active:
                self.activate_owner(owner)
            for subscription in self._subscriptions.values():
                if (
                    subscription.name,
                    subscription.owner,
                    subscription.callback_identity
                    or _callback_identity(subscription.callback),
                    subscription.observer,
                    subscription.once,
                    subscription.priority,
                    subscription.filters,
                    subscription.predicate,
                    subscription.listener_id,
                    subscription.before,
                    subscription.after,
                    subscription.kind,
                ) == (
                    name,
                    owner,
                    callback_identity or _callback_identity(callback),
                    observer,
                    once,
                    priority,
                    filters,
                    predicate,
                    listener_id,
                    before,
                    after,
                    kind,
                ):
                    if temporary:
                        self._subscription_leases[subscription.token] += 1
                    else:
                        self._persistent_subscriptions.add(subscription.token)
                    return subscription.token
            token = uuid4().hex
            if listener_id is not None and any(
                item.listener_id == listener_id for item in self._subscriptions.values()
            ):
                raise ValueError("Listener ID is already registered")
            self._subscriptions[token] = Subscription(
                token,
                name,
                owner,
                callback,
                observer,
                once,
                priority,
                filters,
                predicate,
                listener_id,
                before,
                after,
                kind,
                callback_identity,
            )
            try:
                if listener_id or before or after:
                    by_id = {
                        item.listener_id or item.token: item
                        for item in self._subscriptions.values()
                    }
                    for item in self._subscriptions.values():
                        for reference in item.before + item.after:
                            target = by_id.get(reference)
                            if (
                                target is not None
                                and item.observer != target.observer
                                and (
                                    item.name == target.name
                                    or "*" in {item.name, target.name}
                                )
                            ):
                                raise ValueError(
                                    "Ordering cannot cross hook and observer stages"
                                )
                    for event_name in {
                        item.name for item in self._subscriptions.values()
                    }:
                        for stage in (False, True):
                            candidates = [
                                item
                                for item in self._subscriptions.values()
                                if item.name in {event_name, "*"}
                                and item.observer == stage
                            ]
                            self._ordered(candidates)
            except Exception:
                self._subscriptions.pop(token, None)
                raise
            self._subscription_stats[token] = dict(
                calls=0, failures=0, timeouts=0, last_status=None, last_duration_ms=0
            )
            if temporary:
                self._subscription_leases[token] += 1
            else:
                self._persistent_subscriptions.add(token)
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
            self._subscription_stats.pop(token, None)
            self._subscription_leases.pop(token, None)
            self._persistent_subscriptions.discard(token)

    def release_subscription(self, token: str, *, owner: str) -> None:
        """Release one temporary registration without removing another owner's lease."""
        with self._lock:
            subscription = self._subscriptions.get(token)
            if subscription is None:
                return
            if subscription.owner != owner:
                raise PermissionError("Subscription belongs to another owner")
            if self._subscription_leases.get(token, 0) == 0:
                return
            self._subscription_leases[token] -= 1
            if not self._subscription_leases[token]:
                self._subscription_leases.pop(token, None)
                if token not in self._persistent_subscriptions:
                    self.unsubscribe(token, owner=owner)

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

    def subscriptions(self, owner: str) -> tuple[EventSubscriptionInfo, ...]:
        with self._lock:
            by_id = {
                item.listener_id or item.token: item
                for item in self._subscriptions.values()
            }

            def unresolved(
                item: Subscription, references: tuple[str, ...]
            ) -> tuple[str, ...]:
                return tuple(
                    reference
                    for reference in references
                    if (target := by_id.get(reference)) is None
                    or target.observer != item.observer
                    or (
                        item.name != target.name and "*" not in {item.name, target.name}
                    )
                )

            return tuple(
                EventSubscriptionInfo(
                    subscription_id=item.token,
                    listener_id=item.listener_id or item.token,
                    name=item.name,
                    owner=item.owner,
                    kind="observer" if item.observer else item.kind,
                    priority=item.priority,
                    before=item.before,
                    after=item.after,
                    unresolved_before=unresolved(item, item.before),
                    unresolved_after=unresolved(item, item.after),
                    filters=item.filters,
                    once=item.once,
                    active=owner in self._owners,
                    **self._subscription_stats.get(item.token, {}),
                )
                for item in self._subscriptions.values()
                if item.owner == owner
            )

    @staticmethod
    def _ordered(items: list[Subscription]) -> list[Subscription]:
        if not any(item.before or item.after for item in items):
            return sorted(items, key=lambda item: -item.priority)
        by_id = {item.listener_id or item.token: item for item in items}
        edges: dict[str, set[str]] = {key: set() for key in by_id}
        for key, item in by_id.items():
            for target in item.before:
                if target in by_id:
                    edges[key].add(target)
            for target in item.after:
                if target in by_id:
                    edges[target].add(key)
        remaining = list(items)
        ordered = []
        while remaining:
            ready = [
                item
                for item in remaining
                if not any(
                    (item.listener_id or item.token) in targets
                    for targets in edges.values()
                )
            ]
            if not ready:
                raise ValueError("Event listener ordering contains a cycle")
            chosen = max(ready, key=lambda item: item.priority)
            ordered.append(chosen)
            remaining.remove(chosen)
            edges.pop(chosen.listener_id or chosen.token)
        return ordered

    def _matches(
        self, subscription: Subscription, envelope: EventEnvelope, data: dict[str, Any]
    ) -> bool:
        filters = subscription.filters
        if filters is None:
            return True
        operation = self.operations.current()
        actual = dict(
            server_name=data.get("server_name"),
            source=envelope.source,
            plugin_name=data.get("_triggering_plugin")
            or (
                envelope.source.removeprefix("plugin:")
                if envelope.source.startswith("plugin:")
                else None
            ),
            operation_name=operation.name if operation else None,
            sequence_id=operation.sequence_id if operation else None,
            correlation_id=envelope.correlation_id,
        )
        return all(
            value is None or actual[key] == value
            for key, value in filters.model_dump().items()
        )

    def _selected(
        self, name: str, observer: bool, owners: set[str] | None
    ) -> list[Subscription]:
        with self._lock:
            selected = []
            seen: set[tuple[Any, ...]] = set()
            for subscription in sorted(
                self._subscriptions.values(), key=lambda item: -item.priority
            ):
                identity = (
                    subscription.owner,
                    subscription.callback_identity
                    or _callback_identity(subscription.callback),
                    subscription.once,
                    subscription.filters,
                    (
                        id(subscription.predicate)
                        if subscription.predicate is not None
                        else None
                    ),
                    subscription.listener_id,
                    subscription.before,
                    subscription.after,
                    subscription.kind,
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
            return self._ordered(selected)

    def current(self) -> EventEnvelope | None:
        """Return copied metadata only for an active callback in this bus."""
        entry = self._current.get()
        if entry is None:
            return None
        event, owner = entry
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None
        if (
            task is not None and task is not owner
        ) or event.event_id not in self._active:
            return None
        return event.model_copy(update={"data": {}})

    def event_context(self) -> EventContext | None:
        event = self.current()
        state = self._handler.get()
        if event is None or state is None or not state.active:
            return None
        operation = self.operations.current()
        return EventContext(
            **event.model_dump(
                include={
                    "event_id",
                    "name",
                    "parent_event_id",
                    "correlation_id",
                    "source",
                }
            ),
            phase=self.registry.definition(event.name).phase,
            observer=state.subscription.observer,
            operation_id=operation.operation_id if operation else None,
            sequence_id=operation.sequence_id if operation else None,
        )

    def notification(self) -> EventNotification:
        context = self.event_context()
        state = self._handler.get()
        if context is None or state is None:
            raise RuntimeError("Event context requires a live callback")
        return EventNotification(
            context,
            freeze(state.envelope.data),
            self.operations.current(),
            self.operations.sequence(),
            freeze(state.arguments),
        )

    def handler(self, payload_model: type[BaseModel] | None = None) -> PluginEvent[Any]:
        notification = self.notification()
        state = self._handler.get()
        assert state is not None

        def can_cancel() -> bool:
            return (
                state.active
                and self._handler.get() is state
                and self.current() is not None
                and not state.subscription.observer
                and notification.context.phase == "before"
                and state.clock() < state.deadline
                and state.control is not None
                and not state.control.is_sealed
            )

        def cancel(reason: str) -> None:
            self.check_owner(state.subscription.owner, state.generation)
            if not can_cancel():
                raise RuntimeError("Cancellation requires a live before-hook")
            assert state.control is not None
            state.control.cancel(reason)

        def cancelled() -> tuple[bool, str | None]:
            control = state.control
            return (
                (control.is_cancelled, control.cancel_reason)
                if control
                else (False, None)
            )

        model = payload_model or EventPayload
        payload = model.model_validate(deepcopy(state.envelope.data))
        return PluginEvent(
            notification.context,
            notification.data,
            notification.operation,
            notification.sequence,
            notification.arguments,
            payload,
            state.deadline,
            can_cancel,
            cancel,
            cancelled,
            state.clock,
        )

    async def _invoke(
        self,
        subscription: Subscription,
        envelope: EventEnvelope,
        args: tuple[Any, ...],
        data: dict[str, Any],
        *,
        targeted: bool = False,
    ) -> Any:
        previous = self._current.get()
        token = self._current.set((envelope, asyncio.current_task()))
        parent = self._handler.get()
        timeout = (
            self.options.hook_timeout_seconds
            if self.registry.definition(envelope.name).phase == "before"
            and not subscription.observer
            else self.options.listener_timeout_seconds
        )
        clock = asyncio.get_running_loop().time
        deadline = clock() + timeout
        if (
            parent is not None
            and parent.active
            and previous is not None
            and previous[1] is asyncio.current_task()
        ):
            deadline = min(deadline, parent.deadline)
        state = CallbackState(
            subscription,
            envelope,
            data.get("event"),
            deadline,
            self.owner_generation(subscription.owner),
            arguments=tuple(sanitize(argument) for argument in args),
            clock=clock,
        )
        handler_token = self._handler.set(state)
        try:
            if subscription.predicate is not None:

                def evaluate(_event: EventEnvelope) -> bool:
                    assert subscription.predicate is not None
                    result = subscription.predicate(self.notification())
                    if inspect.isawaitable(result):
                        if inspect.iscoroutine(result):
                            result.close()
                        raise TypeError("Subscription predicates must be synchronous")
                    return bool(result)

                matched = await self._invoke_callback(
                    replace(subscription, callback=evaluate, observer=True),
                    envelope,
                    args,
                    data,
                )
                if not matched:
                    return _FILTERED
            with self._lock:
                if (
                    self._subscriptions.get(subscription.token) is not subscription
                    or not self.accepting
                    or subscription.owner in self._closed_owners
                    or state.generation != self.owner_generation(subscription.owner)
                    or (not targeted and subscription.owner not in self._owners)
                ):
                    return _FILTERED
                if subscription.once and not state.once_claimed:
                    self.unsubscribe(subscription.token, owner=subscription.owner)
                    state.once_claimed = True
            return await self._invoke_callback(subscription, envelope, args, data)
        finally:
            state.active = False
            self._handler.reset(handler_token)
            self._current.reset(token)

    async def _invoke_callback(
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
        *,
        targeted: bool = False,
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
        stats = self._subscription_stats.get(subscription.token)
        try:
            timeout = (
                self.options.hook_timeout_seconds
                if definition.phase == "before" and not subscription.observer
                else self.options.listener_timeout_seconds
            )
            async with asyncio.timeout(timeout):
                result = await self._invoke(
                    subscription, envelope, args, data, targeted=targeted
                )
            if result is _FILTERED:
                record.listeners_called -= 1
                record.listeners.remove(listener)
                return
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
            if stats is not None and listener in record.listeners:
                stats["calls"] += 1
                stats["failures"] += int(listener.status in {"failed", "timed_out"})
                stats["timeouts"] += int(listener.status == "timed_out")
                stats["last_status"] = listener.status
                stats["last_duration_ms"] = listener.duration_ms
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
            private = not public or not self.registry.definition(envelope.name).public
            for subscription in self._selected(envelope.name, observer, owners):
                definition = self.registry.definition(envelope.name)
                visible = (
                    subscription.owner == definition.owner
                    or (
                        definition.owner == "application"
                        and definition.phase == "lifecycle"
                    )
                    or (owners is not None and subscription.owner in owners)
                )
                if private and (
                    (observer and not (subscription.kind == "observer" and visible))
                    or (not observer and subscription.kind == "hook" and not visible)
                ):
                    continue
                if subscription.token not in self._subscriptions or (
                    owners is None and subscription.owner not in self._owners
                ):
                    continue
                if not self._matches(subscription, envelope, data):
                    continue
                await self._deliver(
                    subscription,
                    envelope,
                    record,
                    args,
                    data,
                    strict,
                    targeted=owners is not None,
                )

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
        correlation_token = _correlation.set(envelope.correlation_id)
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
            _correlation.reset(correlation_token)
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

    @property
    def has_pending_work(self) -> bool:
        current = asyncio.current_task()
        return any(
            not task.done() for task in self._tasks if task is not current
        ) or any(
            not worker.done() for owned in self._workers.values() for worker in owned
        )

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
        self._subscription_stats.clear()
        self._subscription_leases.clear()
        self._persistent_subscriptions.clear()
        self._owners.clear()


class EventWorkerCapacityError(RuntimeError):
    """No additional synchronous callback may be queued or started."""


class EventDispatchRejected(RuntimeError):
    def __init__(self, record: EventRecord):
        self.record = record.model_copy(deep=True)
        super().__init__(f"Event dispatch rejected: {record.rejection_reason}")

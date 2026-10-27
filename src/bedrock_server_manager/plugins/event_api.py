"""Plugin event capabilities backed by an owner-scoped closure."""

from typing import Any, Callable, TypeVar, cast

from pydantic import BaseModel

from ..events.context import PluginEvent
from ..events.models import (
    EventActivityQuery,
    EventCatalog,
    EventContext,
    EventDefinition,
    EventDiagnostics,
    EventFilter,
    EventRecord,
    EventSubscriptionInfo,
)
from .subscription import EventSubscriptionScope

T = TypeVar("T", bound=BaseModel)


class PluginEventAPI:
    def __init__(self, dispatch: Callable[..., Any]):
        self._dispatch = dispatch

    def current(self) -> EventContext | None:
        """Read immutable current-event metadata without retaining payloads."""
        return cast(EventContext | None, self._dispatch("current"))

    def listen(
        self,
        name: str,
        callback: Callable[..., Any],
        *,
        priority: int = 0,
        filters: EventFilter | None = None,
        predicate: Callable[..., bool] | None = None,
        listener_id: str | None = None,
        before: tuple[str, ...] = (),
        after: tuple[str, ...] = (),
        timeout_seconds: float | None = None,
    ) -> str:
        """Register a listener automatically removed when this plugin unloads."""
        return cast(
            str,
            self._dispatch(
                "listen",
                name,
                callback,
                priority=priority,
                filters=filters,
                predicate=predicate,
                listener_id=listener_id,
                before=before,
                after=after,
                timeout_seconds=timeout_seconds,
            ),
        )

    def once(
        self,
        name: str,
        callback: Callable[..., Any],
        *,
        priority: int = 0,
        filters: EventFilter | None = None,
        predicate: Callable[..., bool] | None = None,
        listener_id: str | None = None,
        before: tuple[str, ...] = (),
        after: tuple[str, ...] = (),
        timeout_seconds: float | None = None,
    ) -> str:
        """Listen once, including when callback dispatch overlaps another event."""
        return cast(
            str,
            self._dispatch(
                "once",
                name,
                callback,
                priority=priority,
                filters=filters,
                predicate=predicate,
                listener_id=listener_id,
                before=before,
                after=after,
                timeout_seconds=timeout_seconds,
            ),
        )

    def catalog(self) -> EventCatalog:
        """Discover public contracts, owned private events, and application lifecycle hooks."""
        return cast(EventCatalog, self._dispatch("catalog"))

    def describe(self, name: str) -> EventDefinition:
        """Read a copied contract; reject unknown or other-plugin private events."""
        return cast(EventDefinition, self._dispatch("describe", name))

    def subscriptions(self) -> tuple[EventSubscriptionInfo, ...]:
        """Inspect only this plugin's current subscriptions and delivery statistics."""
        return cast(tuple[EventSubscriptionInfo, ...], self._dispatch("subscriptions"))

    def handler(self, payload_model: type[T] | None = None) -> PluginEvent[T]:
        """Read typed context inside a callback without changing its arguments."""
        return cast(PluginEvent[T], self._dispatch("handler", payload_model))

    def hook(
        self,
        name: str,
        callback: Callable[[PluginEvent[T]], Any],
        *,
        payload_model: type[T] | None = None,
        priority: int = 0,
        filters: EventFilter | None = None,
        predicate: Callable[..., bool] | None = None,
        listener_id: str | None = None,
        before: tuple[str, ...] = (),
        after: tuple[str, ...] = (),
        timeout_seconds: float | None = None,
        once: bool = False,
    ) -> str:
        """Opt into a single typed context argument; before-hooks can cancel work."""
        return cast(
            str,
            self._dispatch(
                "hook",
                name,
                callback,
                payload_model=payload_model,
                priority=priority,
                filters=filters,
                predicate=predicate,
                listener_id=listener_id,
                before=before,
                after=after,
                timeout_seconds=timeout_seconds,
                once=once,
            ),
        )

    def listen_typed(
        self,
        name: str,
        payload_model: type[T],
        callback: Callable[[PluginEvent[T]], Any],
        **options: Any,
    ) -> str:
        """Register an opt-in typed hook with a specific payload contract."""
        return self.hook(name, callback, payload_model=payload_model, **options)

    def observe(
        self,
        name: str,
        callback: Callable[[PluginEvent[T]], Any],
        *,
        payload_model: type[T] | None = None,
        priority: int = 0,
        filters: EventFilter | None = None,
        predicate: Callable[..., bool] | None = None,
        listener_id: str | None = None,
        before: tuple[str, ...] = (),
        after: tuple[str, ...] = (),
        timeout_seconds: float | None = None,
        once: bool = False,
    ) -> str:
        """Observe immutable notification data without cancellation access."""
        return cast(
            str,
            self._dispatch(
                "observe",
                name,
                callback,
                payload_model=payload_model,
                priority=priority,
                filters=filters,
                predicate=predicate,
                listener_id=listener_id,
                before=before,
                after=after,
                timeout_seconds=timeout_seconds,
                once=once,
            ),
        )

    def observe_all(
        self, callback: Callable[[PluginEvent[T]], Any], **options: Any
    ) -> str:
        """Observe live public events across all chains; private visibility is unchanged."""
        return self.observe("*", callback, **options)

    def activity(self, query: EventActivityQuery | None = None) -> EventDiagnostics:
        """Read active and recent metadata across all chains, without retaining payloads."""
        return self.diagnostics(query)

    def subscription(
        self,
        name: str,
        callback: Callable[..., Any],
        *,
        mode: str = "legacy",
        **options: Any,
    ) -> EventSubscriptionScope:
        """Temporarily register with `with` or `async with`; always clean up on exit."""
        if mode not in {"legacy", "hook", "observer"}:
            raise ValueError("Subscription mode must be legacy, hook, or observer")
        return EventSubscriptionScope(
            lambda: self._dispatch(
                "subscription", name, callback, mode=mode, **options
            ),
            lambda token: self._dispatch("cleanup_subscription", token),
        )

    async def wait_for(
        self,
        name: str,
        *,
        predicate: Callable[..., bool] | None = None,
        timeout: float = 30,
    ) -> dict[str, Any]:
        """Await a matching payload with timeout and unload cancellation."""
        return cast(
            dict[str, Any],
            await self._dispatch(
                "wait_for", name, predicate=predicate, timeout=timeout
            ),
        )

    def unsubscribe(self, token: str) -> None:
        self._dispatch("unsubscribe", token)

    def define(
        self,
        name: str,
        payload_model: type[BaseModel],
        *,
        description: str = "",
        public: bool = True,
    ) -> EventDefinition:
        """Declare a typed event under this plugin's colon namespace."""
        return cast(
            EventDefinition,
            self._dispatch(
                "define", name, payload_model, description=description, public=public
            ),
        )

    async def emit(self, name: str, *args: Any, **data: Any) -> EventRecord:
        return cast(EventRecord, await self._dispatch("emit", name, *args, **data))

    def diagnostics(self, query: EventActivityQuery | None = None) -> EventDiagnostics:
        """Read copied metadata; event payloads are not retained in history."""
        return cast(EventDiagnostics, self._dispatch("diagnostics", query))

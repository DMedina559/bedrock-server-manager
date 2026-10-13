"""Plugin event capabilities backed by an owner-scoped closure."""

from typing import Any, Callable, cast

from pydantic import BaseModel

from ..events.models import (
    EventActivityQuery,
    EventDefinition,
    EventDiagnostics,
    EventRecord,
)


class PluginEventAPI:
    def __init__(self, dispatch: Callable[..., Any]):
        self._dispatch = dispatch

    def listen(self, name: str, callback: Callable[..., Any]) -> str:
        """Register a listener automatically removed when this plugin unloads."""
        return cast(str, self._dispatch("listen", name, callback))

    def once(self, name: str, callback: Callable[..., Any]) -> str:
        """Listen once, including when callback dispatch overlaps another event."""
        return cast(str, self._dispatch("once", name, callback))

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

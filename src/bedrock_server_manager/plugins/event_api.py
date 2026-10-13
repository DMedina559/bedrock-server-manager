"""Plugin event capabilities backed by an owner-scoped closure."""

from typing import Any, Callable, cast

from pydantic import BaseModel

from ..events.models import EventDefinition, EventDiagnostics, EventRecord


class PluginEventAPI:
    def __init__(self, dispatch: Callable[..., Any]):
        self._dispatch = dispatch

    def listen(self, name: str, callback: Callable[..., Any]) -> str:
        """Register a listener automatically removed when this plugin unloads."""
        return cast(str, self._dispatch("listen", name, callback))

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

    def diagnostics(self) -> EventDiagnostics:
        """Read copied metadata; event payloads are not retained in history."""
        return cast(EventDiagnostics, self._dispatch("diagnostics"))

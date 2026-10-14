"""The publication capability required by core event producers."""

from typing import Any, Mapping, Protocol

from .models import EventRecord


class EventPublisher(Protocol):
    @property
    def accepting(self) -> bool: ...

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
    ) -> EventRecord: ...

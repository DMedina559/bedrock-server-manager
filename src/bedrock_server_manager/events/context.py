"""Typed callback views with immutable notification data and scoped cancellation."""

from dataclasses import dataclass
from time import monotonic
from types import MappingProxyType
from typing import Any, Callable, Generic, Mapping, TypeVar

from pydantic import BaseModel, ConfigDict

from ..operations import OperationSequence, OperationSnapshot
from .models import EventContext


def freeze(value: Any) -> Any:
    """Freeze JSON containers without sharing mutable event payloads."""
    if isinstance(value, dict):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    return value


class EventPayload(BaseModel):
    """Default typed view; callers can supply a specific Pydantic payload model."""

    model_config = ConfigDict(extra="allow", frozen=True)


@dataclass(frozen=True)
class EventNotification:
    context: EventContext
    data: Mapping[str, Any]
    operation: OperationSnapshot | None
    sequence: OperationSequence | None
    arguments: tuple[Any, ...]


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class PluginEvent(EventNotification, Generic[T]):
    """Typed payloads are detached copies; data is recursively immutable."""

    payload: T
    _deadline: float
    _can_cancel: Callable[[], bool]
    _cancel: Callable[[str], None]
    _cancelled: Callable[[], tuple[bool, str | None]]

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self._deadline - monotonic())

    @property
    def can_cancel(self) -> bool:
        return self._can_cancel()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled()[0]

    @property
    def cancel_reason(self) -> str | None:
        return self._cancelled()[1]

    def cancel(self, reason: str = "Cancelled by plugin") -> None:
        """Cancel only during this live before-hook; observers cannot veto work."""
        self._cancel(reason)

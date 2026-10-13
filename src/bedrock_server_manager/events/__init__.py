"""Application event subsystem; usable without plugins or a web server."""

from .bus import EventBus, EventDispatchRejected
from .control import CancellableEvent
from .decorator import trigger_event
from .models import (
    EventActivityQuery,
    EventDefinition,
    EventDiagnostics,
    EventEnvelope,
    EventOptions,
)
from .registry import EventRegistry
from .server import StatusRequest, StatusResult

__all__ = [
    "EventBus",
    "EventActivityQuery",
    "EventDispatchRejected",
    "EventRegistry",
    "EventDefinition",
    "EventDiagnostics",
    "EventEnvelope",
    "EventOptions",
    "CancellableEvent",
    "trigger_event",
    "StatusRequest",
    "StatusResult",
]

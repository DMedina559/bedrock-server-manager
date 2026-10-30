"""Application event subsystem; usable without plugins or a web server."""

from .bus import EventBus, EventDispatchRejected
from .context import EventNotification, EventPayload, PluginEvent
from .control import CancellableEvent
from .decorator import trigger_event
from .models import (
    EventActivityQuery,
    EventDefinition,
    EventDiagnostics,
    EventEnvelope,
    EventFilter,
    EventOptions,
    EventSubscriptionInfo,
    EventSubscriptions,
)
from .operations import (
    OperationActivity,
    OperationActivityQuery,
    OperationName,
    OperationResultQuery,
    OperationSequence,
    OperationSnapshot,
)
from .player import PlayerSnapshot
from .publisher import EventPublisher
from .registry import EventRegistry
from .server import StatusRequest, StatusResult

__all__ = [
    "EventBus",
    "EventFilter",
    "EventSubscriptionInfo",
    "EventSubscriptions",
    "EventNotification",
    "EventPayload",
    "PluginEvent",
    "EventPublisher",
    "PlayerSnapshot",
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
    "OperationActivity",
    "OperationActivityQuery",
    "OperationName",
    "OperationResultQuery",
    "OperationSequence",
    "OperationSnapshot",
]

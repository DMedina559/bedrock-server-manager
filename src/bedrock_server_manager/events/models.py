"""Public event contracts and bounded diagnostic metadata."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from ..results import DeliveryResult


class EventModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventDefinition(EventModel):
    name: str = Field(
        min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_][a-zA-Z0-9_.:-]*$"
    )
    phase: Literal["before", "after", "custom", "lifecycle"] = "custom"
    description: str = ""
    owner: str = "application"
    identity_keys: tuple[str, ...] = ()
    public: bool = True
    payload_schema: dict[str, JsonValue] = Field(default_factory=dict)


class EventFilter(EventModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    server_name: str | None = None
    source: str | None = None
    plugin_name: str | None = None
    operation_name: str | None = None
    sequence_id: str | None = None
    correlation_id: str | None = None


class EventSubscriptionInfo(EventModel):
    subscription_id: str
    listener_id: str
    name: str
    owner: str
    kind: Literal["legacy", "hook", "observer"]
    priority: int
    before: tuple[str, ...] = ()
    after: tuple[str, ...] = ()
    unresolved_before: tuple[str, ...] = ()
    unresolved_after: tuple[str, ...] = ()
    filters: EventFilter | None = None
    once: bool
    active: bool
    calls: int = 0
    failures: int = 0
    timeouts: int = 0
    last_status: str | None = None
    last_duration_ms: float = 0


class EventSubscriptions(EventModel):
    items: list[EventSubscriptionInfo] = Field(default_factory=list)
    total: int = 0
    truncated: bool = False


class EventContext(EventModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_id: str
    name: str
    parent_event_id: str | None = None
    correlation_id: str
    source: str
    phase: Literal["before", "after", "custom", "lifecycle"] = "custom"
    observer: bool = False
    operation_id: str | None = None
    sequence_id: str | None = None


class EventEnvelope(EventModel):
    event_id: str
    correlation_id: str
    parent_event_id: str | None = None
    timestamp: float
    source: str
    name: str
    epoch: str | None = None
    revision: int | None = Field(default=None, ge=1, le=2**53 - 1)
    data: dict[str, JsonValue]

    @model_validator(mode="after")
    def coherent_revision(self) -> Self:
        if (self.epoch is None) != (self.revision is None):
            raise ValueError("Epoch and revision must be supplied together")
        if self.epoch is not None and not self.epoch.strip():
            raise ValueError("Epoch must not be empty")
        return self


class ListenerFailure(EventModel):
    owner: str
    error_type: str
    code: Literal[
        "event_listener_failed",
        "event_listener_timeout",
        "event_depth_limit",
        "event_capacity",
    ]


class EventDelivery(DeliveryResult):
    owner: str

    @classmethod
    def combine(cls, items: list[DeliveryResult]) -> "EventDelivery":
        owners = {item.owner for item in items if isinstance(item, cls)}
        if len(owners) != 1 or any(not isinstance(item, cls) for item in items):
            raise ValueError("Event delivery aggregation requires one explicit owner")
        counts = DeliveryResult.combine(items)
        return cls(owner=owners.pop(), **counts.model_dump())


class ListenerRecord(EventModel):
    subscription_id: str
    owner: str
    observer: bool
    listener_name: str
    failure: ListenerFailure | None = None
    status: Literal["running", "completed", "failed", "timed_out", "cancelled"] = (
        "running"
    )
    duration_ms: float = Field(default=0, ge=0)


EventStatus = Literal["dispatching", "completed", "partial", "cancelled", "suppressed"]
RejectionReason = Literal["recursion", "depth_limit", "capacity", "shutdown"]


class EventRecord(EventModel):
    operation_id: str | None = None
    sequence_id: str | None = None
    operation_name: str | None = None
    server_name: str | None = None
    phase: Literal["before", "after", "custom", "lifecycle"] = "custom"
    event_id: str
    correlation_id: str
    parent_event_id: str | None = None
    name: str
    source: str
    timestamp: float
    status: EventStatus
    rejection_reason: RejectionReason | None = None
    listeners: list[ListenerRecord] = Field(default_factory=list)
    duration_ms: float = 0
    listeners_called: int = 0
    failures: list[ListenerFailure] = Field(default_factory=list)
    deliveries: list[EventDelivery] = Field(default_factory=list)
    cancellation_reason: str | None = None


class EventDiagnostics(EventModel):
    active_truncated: bool = False
    recent_truncated: bool = False
    accepting: bool
    emitted: int
    suppressed: int
    failed_listeners: int
    subscriptions: int
    active_dispatches: int = 0
    subscriptions_by_owner: dict[str, int] = Field(default_factory=dict)
    active_listeners_by_owner: dict[str, int] = Field(default_factory=dict)
    notification_delivery: Literal["inline"] = "inline"
    pending_workers: int = 0
    workers_by_owner: dict[str, int] = Field(default_factory=dict)
    pending_waits: int = 0
    rejections_by_reason: dict[str, int] = Field(default_factory=dict)
    timeouts_by_owner: dict[str, int] = Field(default_factory=dict)
    active: list[EventRecord]
    recent: list[EventRecord]


class EventCatalog(EventModel):
    events: list[EventDefinition]


class EventOptions(EventModel):
    history_limit: int = Field(default=200, ge=0, le=10000)
    max_active: int = Field(default=256, ge=1, le=10000)
    max_workers: int | None = Field(default=None, ge=1, le=10000)
    max_workers_per_owner: int | None = Field(default=None, ge=1, le=10000)
    max_depth: int = Field(default=32, ge=1, le=128)
    listener_timeout_seconds: float = Field(default=30, gt=0, le=3600)
    hook_timeout_seconds: float = Field(default=120, gt=0, le=3600)


class EventActivityQuery(EventModel):
    operation_id: str | None = None
    sequence_id: str | None = None
    operation_name: str | None = None
    server_name: str | None = None
    source: str | None = None
    phase: Literal["before", "after", "custom", "lifecycle"] | None = None
    name: str | None = None
    owner: str | None = None
    correlation_id: str | None = None
    status: EventStatus | None = None
    limit: int = Field(default=200, ge=1, le=10000)

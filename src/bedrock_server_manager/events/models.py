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
    accepting: bool
    emitted: int
    suppressed: int
    failed_listeners: int
    subscriptions: int
    active: list[EventRecord]
    recent: list[EventRecord]


class EventCatalog(EventModel):
    events: list[EventDefinition]


class EventOptions(EventModel):
    history_limit: int = Field(default=200, ge=0, le=10000)
    max_active: int = Field(default=256, ge=1, le=10000)
    max_depth: int = Field(default=32, ge=1, le=128)
    listener_timeout_seconds: float = Field(default=30, gt=0, le=3600)
    hook_timeout_seconds: float = Field(default=120, gt=0, le=3600)


class EventActivityQuery(EventModel):
    name: str | None = None
    owner: str | None = None
    correlation_id: str | None = None
    status: EventStatus | None = None
    limit: int = Field(default=200, ge=1, le=10000)

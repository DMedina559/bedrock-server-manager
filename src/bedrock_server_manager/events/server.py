"""Server status mutation hooks shared by core and API adapters."""

from typing import Literal

from pydantic import ConfigDict, Field

from .models import EventDefinition, EventModel
from .registry import builtin_events


class StatusRequest(EventModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    server_name: str = Field(min_length=1)
    status: str = Field(min_length=1)


class StatusResult(EventModel):
    status: Literal["success"] = "success"
    message: str
    server_name: str
    previous_status: str | None
    new_status: str


class BeforeStatusChange(StatusRequest):
    request: StatusRequest


class AfterStatusChange(BeforeStatusChange):
    result: StatusResult


for name, phase, model in (
    ("before_server_status_change", "before", BeforeStatusChange),
    ("after_server_status_change", "after", AfterStatusChange),
):
    builtin_events.register(
        EventDefinition(
            name=name,
            phase=phase,
            identity_keys=("server_name", "status"),
            description="Server status configuration change.",
        ),
        model,
    )

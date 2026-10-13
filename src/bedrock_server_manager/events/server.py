"""Server status mutation hooks shared by core and API adapters."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from ..error import APICancelledError
from ..state_revision import revision_clock
from .bus import correlation_scope
from .control import CancellableEvent
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


async def change_server_status(server: Any, status: str) -> StatusResult:
    request = StatusRequest(server_name=server.server_name, status=status)
    context = server.app_context
    data = {**request.model_dump(), "request": request}
    control = CancellableEvent()
    with correlation_scope():
        if context is not None:
            try:
                await context.events.emit(
                    "before_server_status_change",
                    {**data, "event": control},
                    revision=dict(revision_clock.capture()),
                )
            finally:
                control.seal()
            if control.is_cancelled:
                raise APICancelledError(
                    control.cancel_reason or "Status change cancelled"
                )
        previous = await server.get_status_from_config()
        await server.configuration.update("server_info.status", request.status)
        result = StatusResult(
            message=f"Server status set to {status}.",
            server_name=request.server_name,
            previous_status=previous,
            new_status=request.status,
        )
        if context is not None:
            await context.events.emit(
                "after_server_status_change",
                {**data, "result": result},
                revision=dict(revision_clock.capture()),
            )
        return result

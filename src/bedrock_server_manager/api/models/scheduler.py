"""Serializable scheduler configuration and bounded run metadata."""

from pydantic import Field, JsonValue

from ...state.settings import ScheduledTask
from .common import APIRequest, APIResponse


class ScheduleEntry(APIResponse):
    schedule_id: str
    configuration: ScheduledTask
    available: bool
    legacy: bool = False
    next_run_at: str | None = None
    last_status: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None
    attempts: int = 0
    runs: list[dict[str, JsonValue]] = Field(default_factory=list)


class ListSchedulesRequest(APIRequest):
    server_name: str | None = None


class ListSchedulesResponse(APIResponse):
    server_time: str | None = None
    host_timezone: str | None = None
    timezone_database_available: bool = True
    timezones: list[str] = Field(default_factory=list)
    schedules: list[ScheduleEntry] = Field(default_factory=list)
    task_types: list[str] = Field(default_factory=list)


class SaveScheduleRequest(APIRequest):
    schedule_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")
    configuration: ScheduledTask


class DeleteScheduleRequest(APIRequest):
    schedule_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")
